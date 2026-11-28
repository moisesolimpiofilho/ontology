"""Operações semânticas sobre OWL (RDF/XML) com rdflib.

- semantic_diff: diff por conceito entre duas versões e classificação do impacto
  (major / minor / patch, PocGov seção 6).
- apply_editor_delta: aplica na cópia de trabalho apenas o que o usuário mudou no editor 3D.
  O editor só representa parte do OWL (não vê restrições anônimas, anotações extras etc.);
  por isso nunca substituímos o arquivo inteiro pelo export do editor: calculamos a
  diferença entre o export do que foi carregado e o export atual, e aplicamos só ela.
- apply_version_header / bump_version: metadados obrigatórios da ontologia (seção 5).
"""
from datetime import date

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from rdflib.namespace import OWL, RDF, RDFS, XSD

DCTERMS = Namespace("http://purl.org/dc/terms/")
DC = Namespace("http://purl.org/dc/elements/1.1/")
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
VS_NS = "http://www.w3.org/2003/06/sw-vocab-status/ns#"

DECLARATION_TYPES = frozenset({
    OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
    OWL.AnnotationProperty, OWL.NamedIndividual, RDF.Property,
})
ANNOTATION_PREDICATES = frozenset({
    RDFS.label, RDFS.comment, RDFS.seeAlso, RDFS.isDefinedBy, OWL.versionInfo, OWL.deprecated,
})
ANNOTATION_NAMESPACES = (str(DCTERMS), str(DC), SKOS_NS, VS_NS)
# Axiomas que, acrescentados a uma entidade já existente, podem invalidar dados/inferências
RESTRICTING_PREDICATES = frozenset({
    RDFS.domain, RDFS.range, OWL.disjointWith, OWL.propertyDisjointWith, OWL.disjointUnionOf,
})
RESTRICTING_TYPES = frozenset({
    OWL.FunctionalProperty, OWL.InverseFunctionalProperty, OWL.IrreflexiveProperty, OWL.AsymmetricProperty,
})
IMPACT_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}

LICENSES = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}


class SemanticError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def parse_owl(text):
    g = Graph()
    try:
        g.parse(data=text, format="xml")
    except Exception as exc:
        raise SemanticError(f"OWL/RDF (RDF/XML) inválido: {exc}") from exc
    return g


def serialize_owl(graph):
    return graph.serialize(format="xml")


def ontology_iris(graph):
    return {s for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef)}


def declared_entities(graph, include_annotation_props=True):
    types = DECLARATION_TYPES if include_annotation_props else DECLARATION_TYPES - {OWL.AnnotationProperty}
    return {s for s, o in graph.subject_objects(RDF.type) if o in types and isinstance(s, URIRef)}


def _without_header(graph):
    headers = ontology_iris(graph)
    g = Graph()
    for t in graph:
        if t[0] not in headers:
            g.add(t)
    return g


def _bnode_owners(graph):
    """Mapeia cada BNode para o conceito nomeado que o referencia (ex.: restrições, listas)."""
    owners = {}
    changed = True
    while changed:
        changed = False
        for s, _, o in graph:
            if isinstance(o, BNode) and o not in owners:
                owner = s if isinstance(s, URIRef) else owners.get(s)
                if owner is not None:
                    owners[o] = owner
                    changed = True
    return owners


def _is_annotation(pred, *graphs):
    if pred in ANNOTATION_PREDICATES or str(pred).startswith(ANNOTATION_NAMESPACES):
        return True
    return any((pred, RDF.type, OWL.AnnotationProperty) in g for g in graphs)


def triple_text(t):
    return [term.n3() for term in t]


def max_impact(*impacts):
    return max(impacts, key=lambda i: IMPACT_ORDER[i]) if impacts else "none"


# ---------------------------------------------------------------------------
# Diff semântico e classificação de impacto (seção 6)
# ---------------------------------------------------------------------------
def semantic_diff(base_text, new_text):
    g_old = _without_header(parse_owl(base_text))
    g_new = _without_header(parse_owl(new_text))
    _, only_old, only_new = graph_diff(to_isomorphic(g_old), to_isomorphic(g_new))

    owners_old, owners_new = _bnode_owners(only_old), _bnode_owners(only_new)
    declared_old, declared_new = declared_entities(g_old), declared_entities(g_new)
    concepts = {}

    def bucket(subject, owners):
        key = str(subject) if isinstance(subject, URIRef) else str(owners.get(subject, "_:anonimo"))
        return concepts.setdefault(key, {"concept": key, "added": [], "removed": [], "reasons": set(), "impact": "none"})

    def mark(b, impact, reason):
        b["impact"] = max_impact(b["impact"], impact)
        b["reasons"].add(reason)

    for t in only_old:
        s, p, o = t
        b = bucket(s, owners_old)
        b["removed"].append(triple_text(t))
        if p == RDF.type and o in DECLARATION_TYPES:
            mark(b, "major", "Remoção de entidade")
        elif _is_annotation(p, g_old, g_new):
            mark(b, "patch", "Anotação/metadado alterado")
        else:
            mark(b, "major", f"Axioma removido ou alterado ({g_old.qname(p)})")

    for t in only_new:
        s, p, o = t
        b = bucket(s, owners_new)
        b["added"].append(triple_text(t))
        if p == RDF.type and o in DECLARATION_TYPES:
            mark(b, "minor", "Nova entidade")
        elif _is_annotation(p, g_old, g_new):
            mark(b, "patch", "Anotação/metadado alterado")
        elif isinstance(s, URIRef) and s in declared_old and (
            p in RESTRICTING_PREDICATES or (p == RDF.type and o in RESTRICTING_TYPES)
        ):
            mark(b, "major", f"Nova restrição em entidade existente ({g_new.qname(p)})")
        else:
            mark(b, "minor", "Novo axioma/tripla compatível")

    result = []
    for key, b in concepts.items():
        uri = URIRef(key)
        if uri in declared_new and uri not in declared_old:
            change_type = "added"
        elif uri in declared_old and uri not in declared_new:
            change_type = "removed"
        else:
            change_type = "modified"
        result.append({
            "concept": key,
            "change_type": change_type,
            "impact": b["impact"],
            "reasons": sorted(b["reasons"]),
            "added": sorted(b["added"]),
            "removed": sorted(b["removed"]),
        })
    result.sort(key=lambda c: (-IMPACT_ORDER[c["impact"]], c["concept"]))

    return {
        "impact": max_impact(*(c["impact"] for c in result)) if result else "none",
        "concepts": result,
        "counts": {
            "triples_added": len(only_new),
            "triples_removed": len(only_old),
            "concepts_added": sum(c["change_type"] == "added" for c in result),
            "concepts_removed": sum(c["change_type"] == "removed" for c in result),
            "concepts_modified": sum(c["change_type"] == "modified" for c in result),
        },
    }


def bump_version(version, impact):
    major, minor, patch = (int(x) for x in version.split("."))
    if impact == "major":
        return f"{major + 1}.0.0"
    if impact == "minor":
        return f"{major}.{minor + 1}.0"
    if impact == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SemanticError("Nenhuma alteração para publicar.")


def version_key(version):
    try:
        return tuple(int(x) for x in str(version).split("."))
    except ValueError:
        return (0, 0, 0)


# ---------------------------------------------------------------------------
# Edição vinda do editor 3D
# ---------------------------------------------------------------------------
def apply_editor_delta(current_text, base_export, new_export):
    """Aplica em `current_text` só as triplas que mudaram entre os dois exports do editor."""
    cur = parse_owl(current_text)
    g_base, g_new = parse_owl(base_export), parse_owl(new_export)
    headers = ontology_iris(cur) | ontology_iris(g_base) | ontology_iris(g_new)

    removed = [t for t in g_base if t not in g_new and t[0] not in headers]
    added = [t for t in g_new if t not in g_base and t[0] not in headers]

    for s, p, o in removed:
        if isinstance(o, Literal):
            # "x" e "x"^^xsd:string (ou com idioma) representam o mesmo valor no editor
            for o2 in list(cur.objects(s, p)):
                if isinstance(o2, Literal) and str(o2) == str(o):
                    cur.remove((s, p, o2))
        else:
            cur.remove((s, p, o))

    # Entidades excluídas no editor: remove também o que o editor não enxerga (anotações extras,
    # restrições anônimas) e as referências a elas.
    gone = declared_entities(g_base) - declared_entities(g_new)
    for entity in gone:
        if (entity, None, None) in g_new:
            continue
        _purge_subject(cur, entity)
        for s, p in list(cur.subject_predicates(entity)):
            if isinstance(s, URIRef):
                cur.remove((s, p, entity))

    for t in added:
        cur.add(t)
    return serialize_owl(cur), {"removed": len(removed), "added": len(added), "entities_removed": len(gone)}


def _purge_subject(graph, subject):
    for p, o in list(graph.predicate_objects(subject)):
        graph.remove((subject, p, o))
        if isinstance(o, BNode) and not any(True for _ in graph.subjects(None, o)):
            _purge_subject(graph, o)


# ---------------------------------------------------------------------------
# Cabeçalho da ontologia (metadados obrigatórios, seção 5)
# ---------------------------------------------------------------------------
def version_iri(ontology_iri, version):
    return ontology_iri.rstrip("#/") + "/" + version


def license_iri(license_value):
    return LICENSES.get(license_value, license_value)


def apply_version_header(text, ontology_iri, version, prior_version, license_value, title=None):
    g = parse_owl(text)
    onto = URIRef(ontology_iri)
    for other in ontology_iris(g) - {onto}:
        # normaliza: um único owl:Ontology, o IRI cadastrado
        for p, o in list(g.predicate_objects(other)):
            g.remove((other, p, o))
            g.add((onto, p, o))
    g.add((onto, RDF.type, OWL.Ontology))
    for p in (OWL.versionInfo, OWL.versionIRI, OWL.priorVersion, DCTERMS.license, DCTERMS.modified):
        g.remove((onto, p, None))
    g.add((onto, OWL.versionInfo, Literal(version)))
    g.add((onto, OWL.versionIRI, URIRef(version_iri(ontology_iri, version))))
    if prior_version:
        g.add((onto, OWL.priorVersion, URIRef(version_iri(ontology_iri, prior_version))))
    lic = license_iri(license_value)
    g.add((onto, DCTERMS.license, URIRef(lic) if lic.startswith("http") else Literal(lic)))
    g.add((onto, DCTERMS.modified, Literal(date.today().isoformat(), datatype=XSD.date)))
    if title and not any(g.objects(onto, DCTERMS.title)):
        g.add((onto, DCTERMS.title, Literal(title)))
    return serialize_owl(g)


def ontology_header_check(text, ontology_iri):
    """Confere os metadados obrigatórios da ontologia após a publicação."""
    g = parse_owl(text)
    onto = URIRef(ontology_iri)
    required = {
        "owl:versionInfo": OWL.versionInfo,
        "owl:versionIRI": OWL.versionIRI,
        "dcterms:license": DCTERMS.license,
    }
    missing = [name for name, p in required.items() if not any(g.objects(onto, p))]
    return {"ok": not missing, "missing": missing,
            "has_prior_version": any(g.objects(onto, OWL.priorVersion))}


def empty_ontology(ontology_iri, title):
    g = Graph()
    onto = URIRef(ontology_iri)
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, DCTERMS.title, Literal(title)))
    return serialize_owl(g)


def concept_triples(text, concept_iri):
    """Triplas de um conceito (incluindo estruturas anônimas dele) — usado por STATE ... AT."""
    g = parse_owl(text)
    subject = URIRef(concept_iri)
    out, stack, seen = [], [subject], set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for p, o in g.predicate_objects(node):
            out.append(triple_text((node, p, o)))
            if isinstance(o, BNode):
                stack.append(o)
    return sorted(out)
