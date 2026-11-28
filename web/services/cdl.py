"""CDL — Change Definition Language: consultas temporais sobre o Version Log (PocGov seção 6).

Gramática (palavras-chave sem diferenciar maiúsculas):

    VERSIONS
    HISTORY <conceito>
    WHO CHANGED <conceito>
    STATE <conceito> AT <versão>
    CHANGES [FROM <versão>] [TO <versão>] [SINCE <AAAA-MM-DD>] [WHERE <cond> (AND <cond>)*]
        <cond> ::= impact=major|minor|patch | type=added|removed|modified
                 | kind=asserted|inferred | concept=<conceito>

<conceito> é um IRI entre <...> ou um nome local (casado pelo final do IRI: #Nome ou /Nome).
"""
import re
from datetime import date

from services.semantics import concept_triples, version_key


class CDLError(ValueError):
    pass


TOKEN_RE = re.compile(r"<[^>]*>|[A-Za-z_][\w.:-]*=\S+|\S+")
VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+$")
CONDITION_FIELDS = {
    "impact": {"major", "minor", "patch"},
    "type": {"added", "removed", "modified"},
    "kind": {"asserted", "inferred"},
    "concept": None,
}


def _concept(token):
    if token.startswith("<") and token.endswith(">"):
        return {"iri": token[1:-1]}
    if not token or token.upper() in {"AT", "FROM", "TO", "WHERE", "AND", "SINCE"}:
        raise CDLError("Conceito esperado.")
    return {"local": token}


def _version(token):
    if not token or not VERSION_RE.match(token):
        raise CDLError(f"Versão inválida: {token!r} (use X.Y.Z).")
    return token.lstrip("v")


def parse(query):
    tokens = TOKEN_RE.findall((query or "").strip())
    if not tokens:
        raise CDLError("Consulta vazia.")
    head = tokens[0].upper()
    rest = tokens[1:]

    if head == "VERSIONS" and not rest:
        return {"op": "versions"}
    if head == "HISTORY" and len(rest) == 1:
        return {"op": "history", "concept": _concept(rest[0])}
    if head == "WHO" and len(rest) == 2 and rest[0].upper() == "CHANGED":
        return {"op": "who", "concept": _concept(rest[1])}
    if head == "STATE" and len(rest) == 3 and rest[1].upper() == "AT":
        return {"op": "state", "concept": _concept(rest[0]), "version": _version(rest[2])}
    if head == "CHANGES":
        q = {"op": "changes", "from": None, "to": None, "since": None, "where": {}}
        i = 0
        while i < len(rest):
            kw = rest[i].upper()
            if kw in ("FROM", "TO") and i + 1 < len(rest):
                q[kw.lower()] = _version(rest[i + 1])
                i += 2
            elif kw == "SINCE" and i + 1 < len(rest):
                try:
                    q["since"] = date.fromisoformat(rest[i + 1]).isoformat()
                except ValueError:
                    raise CDLError("Data inválida em SINCE (use AAAA-MM-DD).")
                i += 2
            elif kw in ("WHERE", "AND") and i + 1 < len(rest):
                field, _, value = rest[i + 1].partition("=")
                field = field.lower()
                if field not in CONDITION_FIELDS or not value:
                    raise CDLError(f"Condição inválida: {rest[i + 1]!r}.")
                allowed = CONDITION_FIELDS[field]
                if allowed is not None and value.lower() not in allowed:
                    raise CDLError(f"Valor inválido para {field}: {value!r}.")
                q["where"][field] = _concept(value) if field == "concept" else value.lower()
                i += 2
            else:
                raise CDLError(f"Trecho não reconhecido: {rest[i]!r}.")
        return q
    raise CDLError("Comando não reconhecido. Use VERSIONS, HISTORY, WHO CHANGED, STATE ... AT ou CHANGES.")


def concept_matches(spec, iri):
    if "iri" in spec:
        return iri == spec["iri"]
    name = spec["local"]
    return iri == name or iri.endswith("#" + name) or iri.endswith("/" + name)


def _in_range(version, q):
    k = version_key(version)
    if q.get("from") and k <= version_key(q["from"]):  # FROM é exclusivo: mudanças depois dela
        return False
    if q.get("to") and k > version_key(q["to"]):
        return False
    return True


def execute(q, log_rows, versions):
    """Executa a consulta já parseada sobre as linhas do Version Log e as versões publicadas.

    log_rows: dicts com version, concept_iri, change_type, kind, impact, triples_added,
              triples_removed, proposal_id, author, approver, created_at.
    versions: dicts com version, prior_version, impact, published_at, publisher, content.
    """
    op = q["op"]
    if op == "versions":
        rows = sorted(versions, key=lambda v: version_key(v["version"]))
        return {"columns": ["version", "prior_version", "impact", "published_at", "publisher"],
                "rows": [{k: v.get(k) for k in ("version", "prior_version", "impact", "published_at", "publisher")}
                         for v in rows]}

    if op in ("history", "who"):
        rows = [r for r in log_rows if concept_matches(q["concept"], r["concept_iri"])]
        rows.sort(key=lambda r: (version_key(r["version"]), r["kind"]))
        if op == "who":
            seen, out = set(), []
            for r in rows:
                key = (r["version"], r.get("author"), r.get("approver"))
                if key not in seen:
                    seen.add(key)
                    out.append({"version": r["version"], "author": r.get("author"),
                                "approver": r.get("approver"), "proposal_id": r.get("proposal_id"),
                                "created_at": r.get("created_at")})
            return {"columns": ["version", "author", "approver", "proposal_id", "created_at"], "rows": out}
        return {"columns": ["version", "concept_iri", "change_type", "kind", "impact", "triples_added",
                            "triples_removed", "proposal_id", "author", "approver"],
                "rows": rows}

    if op == "state":
        match = [v for v in versions if v["version"] == q["version"]]
        if not match:
            raise CDLError(f"Versão {q['version']} não encontrada.")
        content = match[0]["content"]
        concept = q["concept"]
        if "local" in concept:
            candidates = {r["concept_iri"] for r in log_rows if concept_matches(concept, r["concept_iri"])}
            iri = sorted(candidates)[0] if candidates else None
            if not iri:
                raise CDLError(f"Conceito '{concept['local']}' não aparece no Version Log; use o IRI completo <...>.")
        else:
            iri = concept["iri"]
        triples = concept_triples(content, iri)
        return {"columns": ["subject", "predicate", "object"],
                "rows": [{"subject": s, "predicate": p, "object": o} for s, p, o in triples],
                "description": f"Estado de {iri} na versão {q['version']} ({len(triples)} tripla(s))."}

    if op == "changes":
        where = q["where"]
        rows = []
        for r in log_rows:
            if not _in_range(r["version"], q):
                continue
            if q.get("since") and str(r.get("created_at", ""))[:10] < q["since"]:
                continue
            if "impact" in where and r.get("impact") != where["impact"]:
                continue
            if "type" in where and r["change_type"] != where["type"]:
                continue
            if "kind" in where and r["kind"] != where["kind"]:
                continue
            if "concept" in where and not concept_matches(where["concept"], r["concept_iri"]):
                continue
            rows.append(r)
        rows.sort(key=lambda r: (version_key(r["version"]), r["concept_iri"]))
        return {"columns": ["version", "concept_iri", "change_type", "kind", "impact", "proposal_id",
                            "author", "approver"],
                "rows": rows}

    raise CDLError("Operação desconhecida.")
