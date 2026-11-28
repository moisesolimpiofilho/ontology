from rdflib import Graph, RDF, RDFS, OWL, URIRef

DEFAULT_ONTOLOGY_IRI = "http://example.org/ontocube#"


class OntologyParseError(ValueError):
    """Conteúdo enviado não é um RDF/XML válido."""


def _uri(node):
    """Retorna a URI como string, ou None para nós anônimos (BNodes) e literais."""
    return str(node) if isinstance(node, URIRef) else None


def _text(g, subject, predicate):
    value = g.value(subject, predicate)
    return str(value) if value is not None else ""


def _ontology_iri(g):
    """IRI declarado em owl:Ontology (o identificador do Graph é um BNode aleatório)."""
    iris = sorted(str(s) for s in g.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef))
    return iris[0] if iris else DEFAULT_ONTOLOGY_IRI


def _properties(g, prop_type):
    props = []
    for p in g.subjects(RDF.type, prop_type):
        uri = _uri(p)
        if not uri:
            continue
        props.append({
            "uri": uri,
            "label": _text(g, p, RDFS.label),
            "domain": _uri(g.value(p, RDFS.domain)) or "",
            "range": _uri(g.value(p, RDFS.range)) or "",
        })
    return props


def extract_ontology_data(raw_content):
    """Faz o parse do XML OWL e retorna (iri_da_ontologia, dicionário estruturado)."""
    g = Graph()
    try:
        g.parse(data=raw_content, format="xml")
    except Exception as exc:  # rdflib lança exceções variadas (SAX, BadSyntax, ...)
        raise OntologyParseError(f"Arquivo OWL/RDF (RDF/XML) inválido: {exc}") from exc

    classes = []
    for cls in set(g.subjects(RDF.type, OWL.Class)):
        uri = _uri(cls)
        if not uri:  # classes anônimas (unionOf, restrições) não viram nós
            continue
        classes.append({
            "uri": uri,
            "label": _text(g, cls, RDFS.label),
            "comment": _text(g, cls, RDFS.comment),
            "parents": sorted({p for p in map(_uri, g.objects(cls, RDFS.subClassOf)) if p}),
        })

    individuals = []
    for ind in set(g.subjects(RDF.type, OWL.NamedIndividual)):
        uri = _uri(ind)
        if not uri:
            continue
        individuals.append({
            "uri": uri,
            "label": _text(g, ind, RDFS.label),
            "types": sorted({
                t for t in map(_uri, g.objects(ind, RDF.type))
                if t and t != str(OWL.NamedIndividual)
            }),
        })

    return _ontology_iri(g), {
        "classes": classes,
        "obj_props": _properties(g, OWL.ObjectProperty),
        "data_props": _properties(g, OWL.DatatypeProperty),
        "individuals": individuals,
    }
