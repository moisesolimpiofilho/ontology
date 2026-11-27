from rdflib import Graph, RDF, RDFS, OWL

def extract_ontology_data(raw_content):
    """Faz o parse do XML OWL e retorna um dicionário estruturado."""
    g = Graph()
    g.parse(data=raw_content, format="xml")
    
    base_iri = str(g.identifier) or "http://example.org/ontocube#"

    classes = []
    for cls in g.subjects(RDF.type, OWL.Class):
        classes.append({
            "uri": str(cls),
            "label": str(g.value(cls, RDFS.label) or ""),
            "comment": str(g.value(cls, RDFS.comment) or ""),
            "parents": [str(p) for p in g.objects(cls, RDFS.subClassOf)],
        })

    obj_props = []
    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        obj_props.append({
            "uri": str(p),
            "label": str(g.value(p, RDFS.label) or ""),
            "domain": str(g.value(p, RDFS.domain) or ""),
            "range": str(g.value(p, RDFS.range) or ""),
        })

    data_props = []
    for p in g.subjects(RDF.type, OWL.DatatypeProperty):
        data_props.append({
            "uri": str(p),
            "label": str(g.value(p, RDFS.label) or ""),
            "domain": str(g.value(p, RDFS.domain) or ""),
            "range": str(g.value(p, RDFS.range) or ""),
        })

    individuals = []
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        individuals.append({
            "uri": str(ind),
            "label": str(g.value(ind, RDFS.label) or ""),
            "types": [str(t) for t in g.objects(ind, RDF.type)],
        })

    return base_iri, {
        "classes": classes,
        "obj_props": obj_props,
        "data_props": data_props,
        "individuals": individuals,
    }