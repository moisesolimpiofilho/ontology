"""Agente LLM de Ontology Learning (PocGov seção 1.4).

Pipeline: ingestão do texto -> extração de candidatos com Claude (saída estruturada) ->
filtragem por similaridade vetorial -> anotações FAIR -> proposta (issue) aberta pelo agente.
O agente nunca altera a versão oficial: só propõe.
"""
import json
import re
import unicodedata

import anthropic
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from services.semantics import parse_owl
from services.similarity import filter_candidates

AGENT_CREATOR = "Agente LLM (OntoCube)"
DATATYPES = ["string", "integer", "decimal", "boolean", "date", "dateTime", "anyURI"]


class AgentError(RuntimeError):
    pass


class AgentNotConfigured(AgentError):
    pass


def _item(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_STR = {"type": "string"}
CANDIDATES_SCHEMA = _item({
    "classes": {"type": "array", "items": _item({
        "name": _STR, "label": _STR, "definition": _STR, "parent": _STR, "evidence": _STR})},
    "object_properties": {"type": "array", "items": _item({
        "name": _STR, "label": _STR, "definition": _STR, "domain": _STR, "range": _STR, "evidence": _STR})},
    "datatype_properties": {"type": "array", "items": _item({
        "name": _STR, "label": _STR, "definition": _STR, "domain": _STR,
        "datatype": {"type": "string", "enum": DATATYPES}, "evidence": _STR})},
})

SYSTEM_PROMPT = """Você é o Agente de Ontology Learning de uma plataforma de governança de ontologias OWL.
A partir de um texto do domínio, proponha candidatos a novas classes (com taxonomia), relações
(ObjectProperty) e atributos (DatatypeProperty), cada um com uma definição textual curta e a evidência.

Regras:
- Proponha apenas conceitos realmente sustentados pelo texto; a evidência deve ser um trecho curto copiado do texto.
- "name" é o identificador: classes em UpperCamelCase, propriedades em lowerCamelCase, sem acentos nem espaços.
- "label" é o nome legível em português; "definition" é uma definição de uma ou duas frases.
- Reaproveite entidades existentes da ontologia (pelo identificador) como superclasse, domínio ou imagem
  sempre que fizer sentido; não proponha de novo uma entidade que já existe.
- "parent" vazio significa que a classe fica na raiz (owl:Thing).
- Domínio e imagem devem ser classes existentes ou propostas nesta mesma resposta.
- Suas saídas são candidatos: um Engenheiro de Conhecimento e um Especialista de Domínio vão revisá-los."""


def is_configured(config):
    return bool(config.get("ANTHROPIC_API_KEY"))


def _ident(text, upper_first):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", text) if p]
    if not parts:
        return ""
    if len(parts) == 1 and not upper_first:
        word = parts[0]
        return word[0].lower() + word[1:]
    head = parts[0][0].upper() + parts[0][1:] if upper_first else parts[0][0].lower() + parts[0][1:]
    return head + "".join(p[0].upper() + p[1:] for p in parts[1:])


def existing_entities(content):
    """Entidades nomeadas da versão atual (para contexto do LLM e para a filtragem vetorial)."""
    g = parse_owl(content)
    out = []
    kinds = ((OWL.Class, "classe"), (OWL.ObjectProperty, "relação"),
             (OWL.DatatypeProperty, "atributo"), (OWL.NamedIndividual, "indivíduo"))
    for rdf_type, kind in kinds:
        for s in g.subjects(RDF.type, rdf_type):
            if not isinstance(s, URIRef):
                continue
            iri = str(s)
            name = re.split(r"[#/]", iri.rstrip("#/"))[-1]
            label = next((str(o) for o in g.objects(s, RDFS.label)), "")
            out.append({"iri": iri, "name": name, "label": label, "kind": kind})
    return out


def _normalize_candidates(data, source):
    out = []
    for c in data.get("classes", []):
        name = _ident(c.get("name") or c.get("label"), True)
        if not name:
            continue
        parent = _ident(c.get("parent"), True) if c.get("parent") else ""
        out.append({"kind": "class", "name": name, "label": c.get("label") or name,
                    "definition": c.get("definition", ""), "parent": parent,
                    "evidence": c.get("evidence", ""), "triple": [name, "subClassOf", parent or "owl:Thing"]})
    for p in data.get("object_properties", []):
        name = _ident(p.get("name") or p.get("label"), False)
        dom, rng = _ident(p.get("domain"), True), _ident(p.get("range"), True)
        if not (name and dom and rng):
            continue
        out.append({"kind": "object_property", "name": name, "label": p.get("label") or name,
                    "definition": p.get("definition", ""), "domain": dom, "range": rng,
                    "evidence": p.get("evidence", ""), "triple": [dom, name, rng]})
    for p in data.get("datatype_properties", []):
        name = _ident(p.get("name") or p.get("label"), False)
        dom = _ident(p.get("domain"), True)
        if not (name and dom):
            continue
        dt = p.get("datatype") if p.get("datatype") in DATATYPES else "string"
        out.append({"kind": "datatype_property", "name": name, "label": p.get("label") or name,
                    "definition": p.get("definition", ""), "domain": dom, "datatype": f"xsd:{dt}",
                    "evidence": p.get("evidence", ""), "triple": [dom, name, f"xsd:{dt}"]})
    for c in out:  # anotações FAIR anexadas a cada candidato
        c["fair"] = {"rdfs:label": c["label"], "rdfs:comment": c["definition"],
                     "dcterms:source": source, "dcterms:creator": AGENT_CREATOR}
    return out


def generate_candidates(config, ontology, current_content, text, source, max_candidates=20, client=None):
    if not is_configured(config) and client is None:
        raise AgentNotConfigured("Agente LLM desativado: defina ANTHROPIC_API_KEY no .env.")
    text = (text or "").strip()
    if not text:
        raise AgentError("Informe o texto do domínio para a ingestão.")
    limit = config.get("LLM_MAX_INPUT_CHARS", 60000)
    if len(text) > limit:
        raise AgentError(f"Texto com {len(text)} caracteres excede o limite de {limit}. Divida o material em partes.")

    existing = existing_entities(current_content)
    existing_list = "\n".join(f"- {e['name']} ({e['kind']}){': ' + e['label'] if e['label'] else ''}"
                              for e in existing[:400]) or "(ontologia vazia)"
    prompt = (
        f"Ontologia: {ontology['name']} <{ontology['iri']}>\n"
        f"Proponha no máximo {max_candidates} candidatos no total.\n\n"
        f"Entidades existentes:\n{existing_list}\n\n"
        f"Fonte do texto: {source or 'não informada'}\n"
        f"<texto>\n{text}\n</texto>"
    )

    client = client or anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])
    try:
        response = client.beta.messages.create(
            model=config.get("LLM_MODEL", "claude-opus-5-5"),
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": config.get("LLM_EFFORT", "high"),
                "format": {"type": "json_schema", "schema": CANDIDATES_SCHEMA},
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise AgentError("Chave da API Anthropic inválida.") from exc
    except anthropic.RateLimitError as exc:
        raise AgentError("Limite de requisições da API atingido; tente novamente em instantes.") from exc
    except anthropic.APIStatusError as exc:
        raise AgentError(f"Erro da API Anthropic ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AgentError("Não foi possível conectar à API Anthropic.") from exc

    if response.stop_reason == "refusal":
        raise AgentError("O modelo recusou processar este texto.")
    if response.stop_reason == "max_tokens":
        raise AgentError("A resposta do modelo foi truncada; reduza o texto ou o número de candidatos.")
    raw = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError("Resposta do modelo não é um JSON válido.") from exc

    candidates = _normalize_candidates(data, source)[:max_candidates]
    kept, rejected = filter_candidates(candidates, existing, config.get("LLM_SIMILARITY_THRESHOLD", 0.82))
    usage = getattr(response, "usage", None)
    return {
        "candidates": kept,
        "filtered_out": rejected,
        "model": getattr(response, "model", config.get("LLM_MODEL")),
        "request_id": getattr(response, "_request_id", None),
        "usage": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None)},
        "raw": data,
    }
