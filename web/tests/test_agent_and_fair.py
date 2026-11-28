import json
from types import SimpleNamespace

import pytest

from conftest import BASE_OWL
from services import llm_agent
from services.fair import fair_check
from services.reasoner import run_reasoner
from services.similarity import filter_candidates

A = "http://example.org/aula#"


# ---------------------------------------------------------------------------
# FAIR
# ---------------------------------------------------------------------------
def test_fair_blocks_changed_elements_without_metadata():
    report = fair_check(BASE_OWL, [A + "Aluno"])
    assert not report["ok"]
    assert report["errors"][0]["concept"] == A + "Aluno"
    assert set(report["errors"][0]["missing"]) == {"rdfs:comment", "dcterms:source", "dcterms:creator"}


def test_fair_complete_element_passes_and_legacy_is_warning():
    report = fair_check(BASE_OWL, [A + "Pessoa"])
    assert report["ok"]
    assert report["legacy_missing_count"] >= 2  # Aluno, Curso, matriculadoEm sem metadados


# ---------------------------------------------------------------------------
# Similaridade vetorial
# ---------------------------------------------------------------------------
def test_similarity_filters_existing_and_duplicates():
    existing = [{"iri": A + "Pessoa", "name": "Pessoa", "label": "Pessoa"}]
    cands = [{"name": "Pessoa", "label": "Pessoa"},
             {"name": "Professor", "label": "Professor"},
             {"name": "Professora", "label": "Professor"},
             {"name": "Disciplina", "label": "Disciplina"}]
    kept, rejected = filter_candidates(cands, existing, 0.82)
    assert [k["name"] for k in kept] == ["Professor", "Disciplina"]
    assert {r["name"] for r in rejected} == {"Pessoa", "Professora"}


# ---------------------------------------------------------------------------
# Agente LLM (cliente simulado: nenhum custo de API)
# ---------------------------------------------------------------------------
class FakeClient:
    def __init__(self, payload, stop_reason="end_turn"):
        self.calls = []
        self.payload, self.stop_reason = payload, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason, model=kwargs["model"],
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(input_tokens=100, output_tokens=50))


CONFIG = {"ANTHROPIC_API_KEY": "", "LLM_MODEL": "claude-opus-5-5", "LLM_EFFORT": "high",
          "LLM_MAX_INPUT_CHARS": 1000, "LLM_SIMILARITY_THRESHOLD": 0.82}
ONTO = {"name": "Aula", "iri": "http://example.org/aula"}
PAYLOAD = {
    "classes": [
        {"name": "Professor", "label": "Professor", "definition": "Pessoa que leciona.", "parent": "Pessoa",
         "evidence": "o professor leciona"},
        {"name": "Pessoa", "label": "Pessoa", "definition": "Ser humano.", "parent": "", "evidence": "pessoas"},
    ],
    "object_properties": [
        {"name": "leciona em", "label": "leciona em", "definition": "Curso em que leciona.",
         "domain": "Professor", "range": "Curso", "evidence": "leciona no curso"},
    ],
    "datatype_properties": [
        {"name": "matricula", "label": "matrícula", "definition": "Número de matrícula.",
         "domain": "Aluno", "datatype": "string", "evidence": "número de matrícula"},
    ],
}


def test_agent_generates_filtered_candidates_with_fair_annotations():
    client = FakeClient(PAYLOAD)
    out = llm_agent.generate_candidates(CONFIG, ONTO, BASE_OWL, "texto do domínio", "Regimento", client=client)
    names = [c["name"] for c in out["candidates"]]
    assert names == ["Professor", "lecionaEm", "matricula"]
    assert [r["name"] for r in out["filtered_out"]] == ["Pessoa"]
    prof = out["candidates"][0]
    assert prof["triple"] == ["Professor", "subClassOf", "Pessoa"]
    assert prof["fair"]["dcterms:source"] == "Regimento"
    assert prof["fair"]["dcterms:creator"] == llm_agent.AGENT_CREATOR
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"
    assert "Pessoa" in call["messages"][0]["content"]  # contexto com entidades existentes


def test_agent_refusal_and_size_limit():
    with pytest.raises(llm_agent.AgentError):
        llm_agent.generate_candidates(CONFIG, ONTO, BASE_OWL, "x", "s", client=FakeClient(PAYLOAD, "refusal"))
    with pytest.raises(llm_agent.AgentError):
        llm_agent.generate_candidates(CONFIG, ONTO, BASE_OWL, "x" * 2000, "s", client=FakeClient(PAYLOAD))


def test_agent_requires_key():
    with pytest.raises(llm_agent.AgentNotConfigured):
        llm_agent.generate_candidates(CONFIG, ONTO, BASE_OWL, "x", "s")


def test_strict_schema_is_closed():
    def walk(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        if node.get("type") == "array":
            walk(node["items"])
    walk(llm_agent.CANDIDATES_SCHEMA)


# ---------------------------------------------------------------------------
# Raciocinador real (HermiT via Java) — roda dentro do container
# ---------------------------------------------------------------------------
INCONSISTENT = BASE_OWL.replace("</rdf:RDF>", """
  <owl:NamedIndividual rdf:about="#x"><rdf:type rdf:resource="#Pessoa"/><rdf:type rdf:resource="#Curso"/></owl:NamedIndividual>
</rdf:RDF>""")
UNSAT = BASE_OWL.replace("</rdf:RDF>", """
  <owl:Class rdf:about="#Monitor"><rdfs:subClassOf rdf:resource="#Pessoa"/><rdfs:subClassOf rdf:resource="#Curso"/></owl:Class>
</rdf:RDF>""")
INFERRED = BASE_OWL.replace("</rdf:RDF>", """
  <owl:Class rdf:about="#Matriculado">
    <owl:equivalentClass><owl:Restriction>
      <owl:onProperty rdf:resource="#matriculadoEm"/><owl:someValuesFrom rdf:resource="#Curso"/>
    </owl:Restriction></owl:equivalentClass>
  </owl:Class>
  <owl:Class rdf:about="#Veterano">
    <rdfs:subClassOf rdf:resource="#Aluno"/>
    <rdfs:subClassOf><owl:Restriction>
      <owl:onProperty rdf:resource="#matriculadoEm"/><owl:someValuesFrom rdf:resource="#Curso"/>
    </owl:Restriction></rdfs:subClassOf>
  </owl:Class>
  <owl:NamedIndividual rdf:about="#curso1"><rdf:type rdf:resource="#Curso"/></owl:NamedIndividual>
  <owl:NamedIndividual rdf:about="#joao">
    <rdf:type rdf:resource="#Aluno"/><matriculadoEm rdf:resource="#curso1"/>
  </owl:NamedIndividual>
</rdf:RDF>""")


def test_reasoner_consistent_with_inferences():
    r = run_reasoner(INFERRED, timeout=120)
    assert r["status"] == "consistent", r
    assert r["unsatisfiable"] == []
    # Classe definida: Veterano ⊑ ∃matriculadoEm.Curso ≡ Matriculado; joao ganha o tipo Matriculado
    assert [A + "Veterano", "http://www.w3.org/2000/01/rdf-schema#subClassOf", A + "Matriculado"] in r["inferred"]
    assert [A + "joao", "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", A + "Matriculado"] in r["inferred"]


def test_reasoner_detects_inconsistency():
    assert run_reasoner(INCONSISTENT, timeout=120)["status"] == "inconsistent"


def test_reasoner_detects_unsatisfiable_class():
    r = run_reasoner(UNSAT, timeout=120)
    assert r["status"] == "consistent"
    assert r["unsatisfiable"] == [A + "Monitor"]
