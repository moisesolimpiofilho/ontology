"""Orquestração da camada de governança (PocGov seções 3, 4 e 6).

Fonte da verdade: PostgreSQL (metadados, propostas, auditoria, Version Log) + Git (conteúdo,
branches por proposta, tags por versão). MongoDB e Neo4j são projeções da versão publicada.
"""
import re
import shutil
import unicodedata
from datetime import datetime, timezone

from flask import current_app

from services import auth, db, llm_agent, workflow
from services import database as projections
from services.db import Json
from services.docs import generate_documentation
from services.fair import fair_check
from services.gitrepo import GitError, OntologyRepo, branch_name, tag_name
from services.parser import extract_ontology_data
from services.reasoner import run_reasoner
from services.semantics import (
    LICENSES, SemanticError, apply_editor_delta, apply_version_header, bump_version, empty_ontology,
    ontology_header_check, ontology_iris, parse_owl, semantic_diff, version_key,
)

INITIAL_VERSION = "1.0.0"
MAX_INFERRED_IN_REPORT = 300


class GovernanceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _now():
    return datetime.now(timezone.utc)


def _repo(ontology):
    return OntologyRepo(current_app.config["REPOS_DIR"], ontology["slug"])


def _slugify(name):
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "ontologia"


def _user_name(user_id):
    if not user_id:
        return None
    row = db.fetch_one("SELECT display_name FROM users WHERE id = %s", (user_id,))
    return row["display_name"] if row else None


# ---------------------------------------------------------------------------
# Ontologias e versões
# ---------------------------------------------------------------------------
def list_ontologies():
    return db.fetch_all(
        "SELECT o.id, o.slug, o.name, o.iri, o.description, o.license, o.current_version, o.created_at, "
        "u.display_name AS created_by_name, "
        "(SELECT count(*) FROM proposals p WHERE p.ontology_id = o.id "
        " AND p.status NOT IN ('publicada', 'rejeitada')) AS open_proposals "
        "FROM ontologies o LEFT JOIN users u ON u.id = o.created_by ORDER BY o.name"
    )


def get_ontology(ontology_id):
    row = db.fetch_one("SELECT * FROM ontologies WHERE id = %s", (ontology_id,))
    if not row:
        raise GovernanceError("Ontologia não encontrada.", 404)
    return row


def list_versions(ontology_id):
    return db.fetch_all(
        "SELECT v.id, v.version, v.prior_version, v.impact, v.git_tag, v.git_commit, v.proposal_id, "
        "v.published_at, pu.display_name AS publisher, ap.display_name AS approver, "
        "jsonb_array_length(v.inferred) AS inferred_count, v.reasoner->>'status' AS reasoner_status "
        "FROM ontology_versions v LEFT JOIN users pu ON pu.id = v.published_by "
        "LEFT JOIN users ap ON ap.id = v.approved_by WHERE v.ontology_id = %s ORDER BY v.published_at DESC",
        (ontology_id,),
    )


def get_version(ontology_id, version):
    row = db.fetch_one(
        "SELECT v.*, pu.display_name AS publisher, ap.display_name AS approver FROM ontology_versions v "
        "LEFT JOIN users pu ON pu.id = v.published_by LEFT JOIN users ap ON ap.id = v.approved_by "
        "WHERE v.ontology_id = %s AND v.version = %s",
        (ontology_id, version),
    )
    if not row:
        raise GovernanceError("Versão não encontrada.", 404)
    return row


def _version_log_rows(cur, ontology_id, version, diff, inferred_prev, inferred_new,
                      proposal_id, author_id, approver_id, impact_override=None):
    rows = 0
    for c in diff["concepts"]:
        cur.execute(
            "INSERT INTO version_log (ontology_id, version, concept_iri, change_type, kind, impact, "
            "triples_added, triples_removed, proposal_id, author_id, approver_id) "
            "VALUES (%s, %s, %s, %s, 'asserted', %s, %s, %s, %s, %s, %s)",
            (ontology_id, version, c["concept"], c["change_type"], impact_override or c["impact"],
             Json(c["added"]), Json(c["removed"]), proposal_id, author_id, approver_id),
        )
        rows += 1
    # Inferências materializadas: diferença entre o que o raciocinador inferia antes e agora
    prev = {tuple(t) for t in inferred_prev}
    new = {tuple(t) for t in inferred_new}
    by_subject = {}
    for t in new - prev:
        by_subject.setdefault(t[0], {"added": [], "removed": []})["added"].append(list(t))
    for t in prev - new:
        by_subject.setdefault(t[0], {"added": [], "removed": []})["removed"].append(list(t))
    for subject, ch in sorted(by_subject.items()):
        change_type = "added" if ch["added"] and not ch["removed"] else "removed" if ch["removed"] and not ch["added"] else "modified"
        cur.execute(
            "INSERT INTO version_log (ontology_id, version, concept_iri, change_type, kind, impact, "
            "triples_added, triples_removed, proposal_id, author_id, approver_id) "
            "VALUES (%s, %s, %s, %s, 'inferred', NULL, %s, %s, %s, %s, %s)",
            (ontology_id, version, subject, change_type, Json(sorted(ch["added"])), Json(sorted(ch["removed"])),
             proposal_id, author_id, approver_id),
        )
        rows += 1
    return rows


def _project_version(ontology, version, content, reasoner):
    """Atualiza MongoDB e Neo4j. Falhas aqui não desfazem a publicação (são projeções)."""
    try:
        _, parsed = extract_ontology_data(content)
        projections.save_version_snapshot(current_app.config["MONGO_DB"], ontology, version, content, parsed,
                                          {k: v for k, v in (reasoner or {}).items() if k != "inferred"})
        projections.save_to_neo4j(parsed, ontology["iri"], replace=True)
    except Exception:
        current_app.logger.exception("Falha ao atualizar projeções (Mongo/Neo4j) da versão %s", version)


def register_ontology(user, name, iri, description, license_value, content=None):
    name = (name or "").strip()
    if not name:
        raise GovernanceError("Informe o nome da ontologia.")
    if license_value not in LICENSES and not str(license_value or "").startswith("http"):
        raise GovernanceError("Licença inválida: use CC-BY-4.0, CC0-1.0 ou o IRI de uma licença.")
    iri = (iri or "").strip()

    if content:
        try:
            file_iris = ontology_iris(parse_owl(content))
        except SemanticError as e:
            raise GovernanceError(str(e))
        if not iri and len(file_iris) == 1:
            iri = str(next(iter(file_iris)))
        if file_iris and iri not in {str(i) for i in file_iris}:
            raise GovernanceError(f"O IRI informado difere do owl:Ontology do arquivo ({', '.join(map(str, file_iris))}).")
    if not re.match(r"^https?://\S+$", iri):
        raise GovernanceError("Informe um IRI http(s) válido para a ontologia.")
    if db.fetch_one("SELECT id FROM ontologies WHERE iri = %s", (iri,)):
        raise GovernanceError("Já existe uma ontologia cadastrada com este IRI.", 409)

    slug = _slugify(name)
    suffix = 1
    while db.fetch_one("SELECT id FROM ontologies WHERE slug = %s", (slug,)):
        suffix += 1
        slug = f"{_slugify(name)}-{suffix}"

    base = content or empty_ontology(iri, name)
    final = apply_version_header(base, iri, INITIAL_VERSION, None, license_value, title=name)
    reasoner = run_reasoner(final, current_app.config["REASONER_TIMEOUT"])
    diff = semantic_diff(empty_ontology(iri, name), final)
    ontology = {"name": name, "iri": iri, "license": license_value, "description": description or "", "slug": slug}
    documentation = generate_documentation(ontology, INITIAL_VERSION, None, "initial", final, diff,
                                           publisher=user["display_name"], published_at=_now().date().isoformat())

    repo = _repo(ontology)
    try:
        sha = repo.init({
            "ontology.owl": final,
            "README.md": f"# {name}\n\nIRI: {iri}\n\nRepositório governado pelo OntoCube 3D. "
                         "A branch `main` contém a versão oficial; cada versão publicada tem uma tag.\n",
            f"docs/{INITIAL_VERSION}.md": documentation,
            "VERSION_LOG.md": f"# Version Log — {name}\n\n## {INITIAL_VERSION} (versão inicial)\n\n"
                              f"- Cadastro por {user['display_name']}; {len(diff['concepts'])} conceito(s).\n",
        }, f"Cadastro da ontologia {name} (versão {INITIAL_VERSION})", user, INITIAL_VERSION)
    except GitError as e:
        shutil.rmtree(repo.path, ignore_errors=True)
        raise GovernanceError(f"Falha ao criar o repositório Git: {e}", 500)

    inferred = reasoner.get("inferred", []) if reasoner.get("status") == "consistent" else []
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO ontologies (slug, name, iri, description, license, current_version, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (slug, name, iri, description or "", license_value, INITIAL_VERSION, user["id"]),
            )
            ontology = dict(cur.fetchone())
            cur.execute(
                "INSERT INTO ontology_versions (ontology_id, version, prior_version, impact, git_tag, git_commit, "
                "published_by, content, inferred, reasoner, documentation) "
                "VALUES (%s, %s, NULL, 'initial', %s, %s, %s, %s, %s, %s, %s)",
                (ontology["id"], INITIAL_VERSION, tag_name(INITIAL_VERSION), sha, user["id"], final,
                 Json(inferred), Json(_compact_reasoner(reasoner)), documentation),
            )
            _version_log_rows(cur, ontology["id"], INITIAL_VERSION, diff, [], inferred, None, user["id"], None,
                              impact_override="initial")
    except Exception:
        shutil.rmtree(repo.path, ignore_errors=True)
        raise

    _project_version(ontology, INITIAL_VERSION, final, reasoner)
    return {**ontology, "reasoner": _compact_reasoner(reasoner)}


def _compact_reasoner(report):
    out = dict(report or {})
    inferred = out.get("inferred", [])
    out["inferred_count"] = len(inferred)
    out["inferred"] = inferred[:MAX_INFERRED_IN_REPORT]
    return out


# ---------------------------------------------------------------------------
# Propostas (issues)
# ---------------------------------------------------------------------------
PROPOSAL_SELECT = (
    "SELECT p.*, o.name AS ontology_name, o.iri AS ontology_iri, o.current_version AS ontology_version, "
    "rq.display_name AS requester_name, rq.role AS requester_role, "
    "asg.display_name AS assignee_name, dec.display_name AS decided_by_name "
    "FROM proposals p JOIN ontologies o ON o.id = p.ontology_id "
    "JOIN users rq ON rq.id = p.requester_id "
    "LEFT JOIN users asg ON asg.id = p.assignee_id "
    "LEFT JOIN users dec ON dec.id = p.decided_by "
)


def get_proposal(proposal_id):
    row = db.fetch_one(PROPOSAL_SELECT + "WHERE p.id = %s", (proposal_id,))
    if not row:
        raise GovernanceError("Proposta não encontrada.", 404)
    return row


def list_proposals(ontology_id=None, status=None, mine_user=None):
    where, params = [], []
    if ontology_id:
        where.append("p.ontology_id = %s")
        params.append(ontology_id)
    if status:
        where.append("p.status = ANY(%s)")
        params.append(status if isinstance(status, list) else [status])
    if mine_user:
        where.append("(p.requester_id = %s OR p.assignee_id = %s)")
        params += [mine_user["id"], mine_user["id"]]
    sql = PROPOSAL_SELECT + (("WHERE " + " AND ".join(where)) if where else "") + " ORDER BY p.updated_at DESC LIMIT 200"
    rows = db.fetch_all(sql, tuple(params))
    for r in rows:  # lista leve: sem conteúdo OWL
        r.pop("working_copy", None)
        r["candidates_count"] = len(r.pop("candidates", []) or [])
        report = r.pop("check_report", None) or {}
        r["check_ok"] = report.get("ok")
        r.pop("diff_summary", None)
    return rows


def _event(cur, proposal_id, actor_id, action, from_status, to_status, note=None):
    cur.execute(
        "INSERT INTO proposal_events (proposal_id, actor_id, action, from_status, to_status, note) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (proposal_id, actor_id, action, from_status, to_status, note),
    )


def proposal_detail(proposal_id, user):
    p = get_proposal(proposal_id)
    comments = db.fetch_all(
        "SELECT c.id, c.body, c.created_at, u.display_name AS author, u.role AS author_role "
        "FROM proposal_comments c JOIN users u ON u.id = c.author_id WHERE c.proposal_id = %s ORDER BY c.created_at",
        (proposal_id,),
    )
    events = db.fetch_all(
        "SELECT e.action, e.from_status, e.to_status, e.note, e.created_at, u.display_name AS actor, u.role AS actor_role "
        "FROM proposal_events e JOIN users u ON u.id = e.actor_id WHERE e.proposal_id = %s ORDER BY e.created_at, e.id",
        (proposal_id,),
    )
    has_working_copy = bool(p.get("working_copy"))
    p.pop("working_copy", None)
    actions = {a: {"label": workflow.ACTIONS[a], "allowed": ok, "reason": reason}
               for a in workflow.ACTIONS for ok, reason in [workflow.check(a, user, {**p, "working_copy": has_working_copy})]}
    return {**p, "has_working_copy": has_working_copy, "status_label": workflow.STATUSES[p["status"]],
            "comments": comments, "events": events, "actions": actions,
            "base_outdated": bool(p.get("base_version")) and p["base_version"] != p["ontology_version"]}


def create_proposal(user, ontology_id, title, description, justification, affected_elements=None,
                    source="", evidence="", candidates=None, note=None):
    if not auth.has_permission(user, "solicitar_alteracao"):
        raise GovernanceError("Seu papel não permite registrar solicitações.", 403)
    get_ontology(ontology_id)
    title, description, justification = (title or "").strip(), (description or "").strip(), (justification or "").strip()
    if not title or not description or not justification:
        raise GovernanceError("Título, descrição e justificativa são obrigatórios.")
    affected = [str(a).strip() for a in (affected_elements or []) if str(a).strip()]
    origin = "automatica" if user["role"] == "agente" else "humana"
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO proposals (ontology_id, title, description, justification, origin, requester_id, "
            "affected_elements, source, evidence, candidates) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (ontology_id, title, description, justification, origin, user["id"], Json(affected),
             (source or "").strip(), (evidence or "").strip(), Json(candidates or [])),
        )
        pid = cur.fetchone()["id"]
        _event(cur, pid, user["id"], "criada", None, "pendente", note)
    return get_proposal(pid)


def add_comment(user, proposal_id, body):
    p = get_proposal(proposal_id)
    ok, reason = workflow.check("comentar", user, p)
    if not ok:
        raise GovernanceError(reason, 403)
    body = (body or "").strip()
    if not body:
        raise GovernanceError("Comentário vazio.")
    with db.transaction() as cur:
        cur.execute("INSERT INTO proposal_comments (proposal_id, author_id, body) VALUES (%s, %s, %s)",
                    (proposal_id, user["id"], body))
        cur.execute("UPDATE proposals SET updated_at = now() WHERE id = %s", (proposal_id,))


def _require(action, user, p):
    ok, reason = workflow.check(action, user, p)
    if not ok:
        raise GovernanceError(reason, 403 if "papel" in reason or "login" in reason.lower() else 409)


def _set_status(cur, p, user, to_status, action, note=None, **fields):
    sets = ["status = %s", "updated_at = now()"] + [f"{k} = %s" for k in fields]
    values = [to_status] + [Json(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
    cur.execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id = %s", (*values, p["id"]))
    _event(cur, p["id"], user["id"], action, p["status"], to_status, note)


def start_analysis(user, proposal_id):
    p = get_proposal(proposal_id)
    _require("iniciar_analise", user, p)
    with db.transaction() as cur:
        _set_status(cur, p, user, "em_analise", "iniciar_analise",
                    assignee_id=user["id"], base_version=p["ontology_version"], branch=branch_name(p["id"]))
    return get_proposal(proposal_id)


def base_content(p):
    return get_version(p["ontology_id"], p["base_version"])["content"]


def working_content(p):
    full = db.fetch_one("SELECT working_copy FROM proposals WHERE id = %s", (p["id"],))
    return (full or {}).get("working_copy") or base_content(p)


def verify(p, working_text):
    """Raciocinador SHOIN(D) + metadados FAIR + diff semântico contra a versão base."""
    base = base_content(p)
    diff = semantic_diff(base, working_text)
    if diff["impact"] == "none":
        raise GovernanceError("A cópia de trabalho não tem alterações em relação à versão base.")
    changed = [c["concept"] for c in diff["concepts"]
               if c["change_type"] != "removed" and not c["concept"].startswith("_:")]
    fair = fair_check(working_text, changed)
    reasoner = run_reasoner(working_text, current_app.config["REASONER_TIMEOUT"])
    problems = []
    if reasoner["status"] != "consistent":
        problems.append(reasoner["message"])
    if reasoner.get("unsatisfiable"):
        problems.append(f"{len(reasoner['unsatisfiable'])} classe(s) insatisfatível(is).")
    if not fair["ok"]:
        problems.append(f"{len(fair['errors'])} elemento(s) sem metadados FAIR obrigatórios.")
    report = {
        "ok": not problems,
        "problems": problems,
        "reasoner": _compact_reasoner(reasoner),
        "inferred_full": reasoner.get("inferred", []),
        "fair": fair,
        "impact": diff["impact"],
        "checked_at": _now().isoformat(),
    }
    return report, diff


def save_working_copy(user, proposal_id, base_export, new_export, submit=False):
    p = get_proposal(proposal_id)
    _require("salvar_copia", user, p)
    if not base_export or not new_export:
        raise GovernanceError("Envie o export carregado e o export atual do editor.")
    if p["base_version"] != p["ontology_version"] and user["role"] == "engenheiro":
        raise GovernanceError(
            f"A versão base ({p['base_version']}) ficou desatualizada: a oficial agora é {p['ontology_version']}. "
            "Reabra a cópia de trabalho para continuar sobre a versão atual.", 409)
    try:
        new_text, stats = apply_editor_delta(working_content(p), base_export, new_export)
    except SemanticError as e:
        raise GovernanceError(str(e))

    is_specialist = user["role"] == "especialista"
    message = (f"Proposta #{p['id']}: correção de triplas pelo Especialista" if is_specialist
               else f"Proposta #{p['id']}: cópia de trabalho atualizada")
    ontology = get_ontology(p["ontology_id"])
    branch, sha = _repo(ontology).save_working_copy(p["id"], p["base_version"], new_text, message, user)
    note = f"+{stats['added']} / -{stats['removed']} tripla(s) (commit {sha[:8]})"

    to_status = p["status"]
    if not is_specialist and p["status"] in ("inconsistente", "aguardando_ajustes"):
        to_status = "em_analise"
    with db.transaction() as cur:
        _set_status(cur, p, user, to_status, "correcao_especialista" if is_specialist else "salvar_copia", note,
                    working_copy=new_text, working_commit=sha, branch=branch)

    p = get_proposal(proposal_id)
    if is_specialist:
        # Correção do Especialista passa de novo pela verificação automática
        return _run_and_record_verification(user, p, new_text, "reverificacao")
    if submit:
        return submit_for_verification(user, proposal_id)
    return p


def _run_and_record_verification(user, p, working_text, action):
    report, diff = verify(p, working_text)
    report["working_commit"] = p["working_commit"]
    to_status = "em_validacao" if report["ok"] else "inconsistente"
    note = "Consistente e com metadados FAIR." if report["ok"] else " ".join(report["problems"])
    with db.transaction() as cur:
        _set_status(cur, p, user, to_status, action, note,
                    check_report=report, diff_summary=diff, impact=diff["impact"])
    return get_proposal(p["id"])


def submit_for_verification(user, proposal_id):
    p = get_proposal(proposal_id)
    full = db.fetch_one("SELECT working_copy FROM proposals WHERE id = %s", (proposal_id,))
    _require("submeter", user, {**p, "working_copy": full["working_copy"]})
    return _run_and_record_verification(user, p, full["working_copy"], "submeter")


def decide(user, proposal_id, action, reason=None):
    p = get_proposal(proposal_id)
    _require(action, user, p)
    reason = (reason or "").strip()
    if action in ("rejeitar", "solicitar_ajustes") and not reason:
        raise GovernanceError("Informe a justificativa.")
    to_status = {"aprovar": "aprovada", "rejeitar": "rejeitada", "solicitar_ajustes": "aguardando_ajustes"}[action]
    fields = {}
    if action in ("aprovar", "rejeitar"):
        fields = {"decided_by": user["id"], "decision_reason": reason or None, "decided_at": _now()}
    with db.transaction() as cur:
        _set_status(cur, p, user, to_status, action, reason or None, **fields)
    return get_proposal(proposal_id)


def reopen_on_current_base(user, proposal_id):
    """Quando outra proposta foi publicada antes: arquiva a cópia antiga e recomeça da versão atual."""
    p = get_proposal(proposal_id)
    if user["role"] != "engenheiro" or p.get("assignee_id") != user["id"]:
        raise GovernanceError("Só o Engenheiro responsável pode reabrir a cópia de trabalho.", 403)
    if p["base_version"] == p["ontology_version"]:
        raise GovernanceError("A versão base já é a versão oficial atual.")
    if p["status"] in workflow.FINAL_STATUSES:
        raise GovernanceError("Proposta encerrada.")
    ontology = get_ontology(p["ontology_id"])
    repo = _repo(ontology)
    archived = f"{branch_name(p['id'])}-base-{p['base_version']}"
    try:
        repo._git("branch", "-m", branch_name(p["id"]), archived, check=False)
    except GitError:
        pass
    with db.transaction() as cur:
        _set_status(cur, p, user, "em_analise", "rebase",
                    f"Base {p['base_version']} → {p['ontology_version']}; cópia anterior em {archived}.",
                    base_version=p["ontology_version"], working_copy=None, working_commit=None,
                    check_report=None, diff_summary=None, impact=None)
    return get_proposal(proposal_id)


# ---------------------------------------------------------------------------
# Publicação (seção 3.5)
# ---------------------------------------------------------------------------
def publish(user, proposal_id):
    p = get_proposal(proposal_id)
    _require("publicar", user, p)
    ontology = get_ontology(p["ontology_id"])
    current = ontology["current_version"]
    if p["base_version"] != current:
        raise GovernanceError(
            f"A proposta foi feita sobre a versão {p['base_version']}, mas a oficial agora é {current}. "
            "O Engenheiro deve reabrir a cópia de trabalho sobre a versão atual.", 409)

    full = db.fetch_one("SELECT working_copy, check_report FROM proposals WHERE id = %s", (proposal_id,))
    working = full["working_copy"]
    prev_version = get_version(ontology["id"], current)
    diff = semantic_diff(prev_version["content"], working)
    version = bump_version(current, diff["impact"])
    final = apply_version_header(working, ontology["iri"], version, current, ontology["license"], title=ontology["name"])
    header = ontology_header_check(final, ontology["iri"])
    if not header["ok"]:
        raise GovernanceError(f"Metadados obrigatórios ausentes: {', '.join(header['missing'])}", 500)

    report = full["check_report"] or {}
    inferred = report.get("inferred_full", [])
    approver = _user_name(p["decided_by"])
    published_at = _now()
    documentation = generate_documentation(ontology, version, current, diff["impact"], final, diff, proposal=p,
                                           publisher=user["display_name"], approver=approver,
                                           published_at=published_at.date().isoformat())
    repo = _repo(ontology)
    try:
        version_log_md = repo.read("main", "VERSION_LOG.md")
    except GitError:
        version_log_md = f"# Version Log — {ontology['name']}\n"
    version_log_md += (
        f"\n## {version} ({diff['impact']}) — {published_at.date().isoformat()}\n\n"
        f"- Proposta #{p['id']}: {p['title']}\n- Engenheiro: {p['assignee_name']}; aprovada por: {approver}; "
        f"publicada por: {user['display_name']}\n"
        + "".join(f"- `{c['concept']}`: {c['change_type']} ({c['impact']})\n" for c in diff["concepts"])
    )

    previous_sha = repo.head()
    try:
        sha = repo.publish(p["id"], version, {
            "ontology.owl": final,
            f"docs/{version}.md": documentation,
            "VERSION_LOG.md": version_log_md,
        }, f"Publica versão {version} ({diff['impact']}) — proposta #{p['id']}: {p['title']}", user)
    except GitError as e:
        raise GovernanceError(f"Falha no Git ao publicar: {e}", 500)

    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO ontology_versions (ontology_id, version, prior_version, impact, git_tag, git_commit, "
                "proposal_id, published_by, approved_by, content, inferred, reasoner, documentation) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (ontology["id"], version, current, diff["impact"], tag_name(version), sha, p["id"], user["id"],
                 p["decided_by"], final, Json(inferred), Json(report.get("reasoner")), documentation),
            )
            _version_log_rows(cur, ontology["id"], version, diff, prev_version["inferred"] or [], inferred,
                              p["id"], p["assignee_id"], p["decided_by"])
            cur.execute("UPDATE ontologies SET current_version = %s WHERE id = %s", (version, ontology["id"]))
            _set_status(cur, p, user, "publicada", "publicar", f"Versão {version} ({diff['impact']}), tag {tag_name(version)}",
                        published_version=version)
    except Exception:
        repo.undo_publish(previous_sha, version)
        raise

    _project_version(ontology, version, final, report.get("reasoner"))
    return {"version": version, "impact": diff["impact"], "tag": tag_name(version), "commit": sha,
            "proposal": get_proposal(proposal_id)}


# ---------------------------------------------------------------------------
# Version Log e CDL
# ---------------------------------------------------------------------------
def version_log(ontology_id):
    return db.fetch_all(
        "SELECT l.version, l.concept_iri, l.change_type, l.kind, l.impact, l.triples_added, l.triples_removed, "
        "l.proposal_id, l.created_at, au.display_name AS author, ap.display_name AS approver "
        "FROM version_log l LEFT JOIN users au ON au.id = l.author_id LEFT JOIN users ap ON ap.id = l.approver_id "
        "WHERE l.ontology_id = %s ORDER BY l.id",
        (ontology_id,),
    )


def versions_with_content(ontology_id):
    rows = db.fetch_all(
        "SELECT v.version, v.prior_version, v.impact, v.published_at, v.content, u.display_name AS publisher "
        "FROM ontology_versions v LEFT JOIN users u ON u.id = v.published_by WHERE v.ontology_id = %s",
        (ontology_id,),
    )
    return sorted(rows, key=lambda r: version_key(r["version"]))


# ---------------------------------------------------------------------------
# Agente LLM
# ---------------------------------------------------------------------------
def run_agent(user, ontology_id, text, source, max_candidates=20):
    ontology = get_ontology(ontology_id)
    current = get_version(ontology_id, ontology["current_version"])["content"]
    config = current_app.config
    result = llm_agent.generate_candidates(config, ontology, current, text, source, max_candidates)
    agent = auth.agent_user()

    proposal = None
    if result["candidates"]:
        cands = result["candidates"]
        kinds = {"class": "classe", "object_property": "relação", "datatype_property": "atributo"}
        proposal = create_proposal(
            agent, ontology_id,
            title=f"Candidatos do Agente LLM: {len(cands)} elemento(s) de \"{(source or 'texto')[:60]}\"",
            description="Candidatos gerados por Ontology Learning:\n" + "\n".join(
                f"- [{kinds[c['kind']]}] {c['label']} ({c['name']}): {c['definition']}" for c in cands),
            justification=(f"Gerados automaticamente a partir de \"{source or 'texto informado'}\" e filtrados por "
                           f"similaridade vetorial (limiar {config['LLM_SIMILARITY_THRESHOLD']}); "
                           f"{len(result['filtered_out'])} candidato(s) descartado(s) como duplicata."),
            affected_elements=[c["name"] for c in cands],
            source=source or "",
            evidence="\n".join(f"{c['name']}: \"{c['evidence']}\"" for c in cands if c.get("evidence")),
            candidates=cands,
            note=f"Execução disparada por {user['display_name']} (modelo {result['model']}).",
        )

    try:
        projections.save_agent_run(config["MONGO_DB"], {
            "ontology_id": ontology_id, "triggered_by": user["username"], "source": source,
            "model": result["model"], "request_id": result["request_id"], "usage": result["usage"],
            "candidates": result["candidates"], "filtered_out": result["filtered_out"], "raw": result["raw"],
            "proposal_id": proposal["id"] if proposal else None,
        })
    except Exception:
        current_app.logger.exception("Falha ao registrar a execução do agente no Mongo")

    result.pop("raw", None)
    return {**result, "proposal": proposal}
