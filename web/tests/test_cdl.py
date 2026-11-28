import pytest

from conftest import BASE_OWL
from services import cdl

LOG = [
    {"version": "1.0.0", "concept_iri": "http://example.org/aula#Pessoa", "change_type": "added",
     "kind": "asserted", "impact": "initial", "author": "Eng", "approver": None, "proposal_id": None,
     "created_at": "2026-11-01T10:00:00", "triples_added": [], "triples_removed": []},
    {"version": "1.1.0", "concept_iri": "http://example.org/aula#Professor", "change_type": "added",
     "kind": "asserted", "impact": "minor", "author": "Eng", "approver": "Esp", "proposal_id": 1,
     "created_at": "2026-11-10T10:00:00", "triples_added": [], "triples_removed": []},
    {"version": "2.0.0", "concept_iri": "http://example.org/aula#Pessoa", "change_type": "modified",
     "kind": "asserted", "impact": "major", "author": "Eng", "approver": "Esp", "proposal_id": 2,
     "created_at": "2026-11-20T10:00:00", "triples_added": [], "triples_removed": []},
    {"version": "2.0.0", "concept_iri": "http://example.org/aula#Professor", "change_type": "added",
     "kind": "inferred", "impact": None, "author": "Eng", "approver": "Esp", "proposal_id": 2,
     "created_at": "2026-11-20T10:00:00", "triples_added": [], "triples_removed": []},
]
VERSIONS = [{"version": "1.0.0", "prior_version": None, "impact": "initial", "published_at": "x",
             "publisher": "Eng", "content": BASE_OWL}]


def run(q):
    return cdl.execute(cdl.parse(q), LOG, VERSIONS)


def test_history_by_local_name():
    rows = run("HISTORY Pessoa")["rows"]
    assert [r["version"] for r in rows] == ["1.0.0", "2.0.0"]


def test_history_by_iri():
    assert len(run("history <http://example.org/aula#Professor>")["rows"]) == 2


def test_changes_range_is_exclusive_from_inclusive_to():
    rows = run("CHANGES FROM 1.0.0 TO 1.1.0")["rows"]
    assert [r["version"] for r in rows] == ["1.1.0"]


def test_changes_where_filters():
    assert len(run("CHANGES WHERE impact=major")["rows"]) == 1
    rows = run("CHANGES WHERE kind=inferred AND type=added")["rows"]
    assert len(rows) == 1 and rows[0]["kind"] == "inferred"


def test_changes_since():
    assert {r["version"] for r in run("CHANGES SINCE 2026-11-15")["rows"]} == {"2.0.0"}


def test_who_changed():
    rows = run("WHO CHANGED Pessoa")["rows"]
    assert rows[-1]["approver"] == "Esp"


def test_state_at_version():
    res = run("STATE Pessoa AT 1.0.0")
    assert any(r["predicate"].endswith("#label>") for r in res["rows"])


def test_versions():
    assert run("VERSIONS")["rows"][0]["version"] == "1.0.0"


@pytest.mark.parametrize("q", ["", "DELETE ALL", "CHANGES WHERE impact=huge", "STATE Pessoa AT x", "CHANGES SINCE ontem"])
def test_invalid_queries(q):
    with pytest.raises(cdl.CDLError):
        cdl.parse(q)
