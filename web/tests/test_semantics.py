import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from conftest import BASE_OWL
from services.semantics import (
    DCTERMS, SemanticError, apply_editor_delta, apply_version_header, bump_version, concept_triples,
    ontology_header_check, parse_owl, semantic_diff, serialize_owl,
)

A = "http://example.org/aula#"


def _edit(text, add=(), remove=()):
    g = parse_owl(text)
    for t in remove:
        g.remove(t)
    for t in add:
        g.add(t)
    return serialize_owl(g)


def test_no_change_is_none():
    assert semantic_diff(BASE_OWL, BASE_OWL)["impact"] == "none"


def test_annotation_change_is_patch():
    new = _edit(BASE_OWL, remove=[(URIRef(A + "Aluno"), RDFS.label, Literal("Aluno"))],
                add=[(URIRef(A + "Aluno"), RDFS.label, Literal("Estudante"))])
    diff = semantic_diff(BASE_OWL, new)
    assert diff["impact"] == "patch"
    assert diff["concepts"][0]["concept"] == A + "Aluno"
    assert diff["concepts"][0]["change_type"] == "modified"


def test_new_class_is_minor():
    new = _edit(BASE_OWL, add=[(URIRef(A + "Professor"), RDF.type, OWL.Class),
                               (URIRef(A + "Professor"), RDFS.subClassOf, URIRef(A + "Pessoa"))])
    diff = semantic_diff(BASE_OWL, new)
    assert diff["impact"] == "minor"
    assert diff["counts"]["concepts_added"] == 1


def test_removed_class_is_major():
    g = parse_owl(BASE_OWL)
    for t in list(g.triples((URIRef(A + "Aluno"), None, None))):
        g.remove(t)
    diff = semantic_diff(BASE_OWL, serialize_owl(g))
    assert diff["impact"] == "major"
    assert any(c["change_type"] == "removed" for c in diff["concepts"])


def test_new_range_on_existing_property_is_major():
    new = _edit(BASE_OWL, remove=[(URIRef(A + "matriculadoEm"), RDFS.range, URIRef(A + "Curso"))],
                add=[(URIRef(A + "matriculadoEm"), RDFS.range, URIRef(A + "Pessoa"))])
    assert semantic_diff(BASE_OWL, new)["impact"] == "major"


def test_new_superclass_on_existing_class_is_minor():
    new = _edit(BASE_OWL, add=[(URIRef(A + "Curso"), RDFS.subClassOf, URIRef(A + "Coisa")),
                               (URIRef(A + "Coisa"), RDF.type, OWL.Class)])
    assert semantic_diff(BASE_OWL, new)["impact"] == "minor"


def test_header_changes_are_ignored():
    new = apply_version_header(BASE_OWL, "http://example.org/aula", "2.0.0", "1.0.0", "CC-BY-4.0")
    assert semantic_diff(BASE_OWL, new)["impact"] == "none"


@pytest.mark.parametrize("version,impact,expected", [
    ("1.2.3", "major", "2.0.0"), ("1.2.3", "minor", "1.3.0"), ("1.2.3", "patch", "1.2.4"),
])
def test_bump(version, impact, expected):
    assert bump_version(version, impact) == expected


def test_bump_without_changes_fails():
    with pytest.raises(SemanticError):
        bump_version("1.0.0", "none")


def test_version_header_has_required_metadata():
    out = apply_version_header(BASE_OWL, "http://example.org/aula", "1.1.0", "1.0.0", "CC-BY-4.0")
    check = ontology_header_check(out, "http://example.org/aula")
    assert check["ok"] and check["has_prior_version"]
    g = parse_owl(out)
    onto = URIRef("http://example.org/aula")
    assert (onto, OWL.versionIRI, URIRef("http://example.org/aula/1.1.0")) in g
    assert (onto, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")) in g


def _editor_export(triples):
    """Simula o export do editor: só triplas nomeadas que ele entende."""
    from rdflib import Graph
    g = Graph()
    g.add((URIRef("http://example.org/aula"), RDF.type, OWL.Ontology))
    for t in triples:
        g.add(t)
    return serialize_owl(g)


def test_editor_delta_keeps_what_editor_cannot_see():
    seen = [(URIRef(A + "Pessoa"), RDF.type, OWL.Class),
            (URIRef(A + "Pessoa"), RDFS.label, Literal("Pessoa")),
            (URIRef(A + "Aluno"), RDF.type, OWL.Class),
            (URIRef(A + "Aluno"), RDFS.subClassOf, URIRef(A + "Pessoa"))]
    base_export = _editor_export(seen)
    new_export = _editor_export(seen + [(URIRef(A + "Aluno"), RDFS.comment, Literal("Pessoa matriculada."))])
    out, stats = apply_editor_delta(BASE_OWL, base_export, new_export)
    g = parse_owl(out)
    assert stats["added"] == 1 and stats["removed"] == 0
    assert (URIRef(A + "Aluno"), RDFS.comment, Literal("Pessoa matriculada.")) in g
    # O que o editor não representa continua lá: anotação vs:term_status e o domínio unionOf
    assert any(True for _ in g.objects(URIRef(A + "Pessoa"), URIRef("http://www.w3.org/2003/06/sw-vocab-status/ns#term_status")))
    assert any(True for _ in g.objects(URIRef(A + "matriculadoEm"), RDFS.domain))
    assert semantic_diff(BASE_OWL, out)["impact"] == "patch"


def test_editor_delta_removes_typed_literal_matching_plain_literal():
    seen = [(URIRef(A + "Aluno"), RDF.type, OWL.Class),
            (URIRef(A + "Aluno"), RDFS.label, Literal("Aluno", datatype="http://www.w3.org/2001/XMLSchema#string"))]
    out, _ = apply_editor_delta(BASE_OWL, _editor_export(seen), _editor_export(seen[:1]))
    assert not any(True for _ in parse_owl(out).objects(URIRef(A + "Aluno"), RDFS.label))


def test_editor_delta_purges_deleted_entity():
    seen = [(URIRef(A + "Pessoa"), RDF.type, OWL.Class), (URIRef(A + "Aluno"), RDF.type, OWL.Class),
            (URIRef(A + "Aluno"), RDFS.subClassOf, URIRef(A + "Pessoa"))]
    out, stats = apply_editor_delta(BASE_OWL, _editor_export(seen), _editor_export(seen[:1]))
    g = parse_owl(out)
    assert (URIRef(A + "Aluno"), None, None) not in g
    assert stats["entities_removed"] == 1


def test_concept_triples_follow_blank_nodes():
    rows = concept_triples(BASE_OWL, A + "matriculadoEm")
    assert any("unionOf" in r[1] for r in rows)
