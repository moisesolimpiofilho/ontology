"""Checagem dos metadados FAIR obrigatórios por elemento (PocGov seção 5)."""
from rdflib import URIRef
from rdflib.namespace import RDFS

from services.semantics import DC, DCTERMS, declared_entities, parse_owl

# (nome exibido, predicados aceitos)
REQUIRED_ELEMENT_METADATA = (
    ("rdfs:label", (RDFS.label,)),
    ("rdfs:comment", (RDFS.comment,)),
    ("dcterms:source", (DCTERMS.source, DC.source)),
    ("dcterms:creator", (DCTERMS.creator, DC.creator)),
)


def missing_metadata(graph, entity):
    return [name for name, preds in REQUIRED_ELEMENT_METADATA
            if not any(any(True for _ in graph.objects(entity, p)) for p in preds)]


def fair_check(text, changed_concepts):
    """Bloqueia (erro) elementos novos/alterados sem metadados; elementos legados viram aviso.

    `changed_concepts`: IRIs adicionados ou modificados na proposta.
    """
    g = parse_owl(text)
    entities = declared_entities(g, include_annotation_props=False)
    changed = {URIRef(c) for c in changed_concepts} & entities

    errors = []
    for entity in sorted(changed):
        missing = missing_metadata(g, entity)
        if missing:
            errors.append({"concept": str(entity), "missing": missing})

    legacy = []
    for entity in sorted(entities - changed):
        missing = missing_metadata(g, entity)
        if missing:
            legacy.append({"concept": str(entity), "missing": missing})

    return {
        "ok": not errors,
        "checked": len(changed),
        "errors": errors,
        "legacy_missing_count": len(legacy),
        "legacy_examples": legacy[:15],
        "required": [name for name, _ in REQUIRED_ELEMENT_METADATA],
    }
