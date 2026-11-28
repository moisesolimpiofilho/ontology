import pytest

from services import workflow
from services.auth import PERMISSIONS, has_permission

ENG = {"id": 1, "role": "engenheiro"}
ENG2 = {"id": 5, "role": "engenheiro"}
ESP = {"id": 2, "role": "especialista"}
STK = {"id": 3, "role": "stakeholder"}
AGT = {"id": 4, "role": "agente"}


def proposal(**kw):
    base = {"id": 10, "status": "pendente", "requester_id": STK["id"], "assignee_id": None,
            "working_copy": None, "working_commit": None, "check_report": None}
    return {**base, **kw}


# Matriz de permissões (PocGov seção 2)
@pytest.mark.parametrize("action,allowed", [
    ("consultar_ontologia", {"engenheiro", "especialista", "stakeholder", "agente"}),
    ("gerar_candidatos", {"agente"}),
    ("editar_ontologia", {"engenheiro"}),
    ("corrigir_triplas", {"engenheiro", "especialista"}),
    ("validar_alteracao", {"especialista"}),
    ("publicar_versao", {"engenheiro"}),
    ("solicitar_alteracao", {"engenheiro", "especialista", "stakeholder", "agente"}),
    ("comentar", {"engenheiro", "especialista", "stakeholder"}),
    ("consultar_historico", {"engenheiro", "especialista", "stakeholder", "agente"}),
])
def test_permission_matrix(action, allowed):
    assert set(PERMISSIONS[action]) == allowed
    for user in (ENG, ESP, STK, AGT):
        assert has_permission(user, action) == (user["role"] in allowed)


def test_only_engineer_starts_analysis():
    p = proposal()
    assert workflow.check("iniciar_analise", ENG, p)[0]
    assert not workflow.check("iniciar_analise", ESP, p)[0]
    assert not workflow.check("iniciar_analise", STK, p)[0]


def test_only_assignee_edits_and_submits():
    p = proposal(status="em_analise", assignee_id=ENG["id"], working_copy="<x/>")
    assert workflow.check("salvar_copia", ENG, p)[0]
    assert not workflow.check("salvar_copia", ENG2, p)[0]
    assert workflow.check("submeter", ENG, p)[0]
    assert not workflow.check("submeter", ENG2, p)[0]


def test_submit_requires_working_copy():
    p = proposal(status="em_analise", assignee_id=ENG["id"])
    assert not workflow.check("submeter", ENG, p)[0]


def test_specialist_corrects_only_during_validation():
    assert workflow.check("salvar_copia", ESP, proposal(status="em_validacao", assignee_id=ENG["id"]))[0]
    assert not workflow.check("salvar_copia", ESP, proposal(status="em_analise", assignee_id=ENG["id"]))[0]


def test_stakeholder_cannot_modify_or_decide():
    p = proposal(status="em_validacao", assignee_id=ENG["id"])
    for action in ("salvar_copia", "submeter", "aprovar", "rejeitar", "solicitar_ajustes", "publicar"):
        assert not workflow.check(action, STK, p)[0]
    assert workflow.check("comentar", STK, p)[0]


def test_agent_cannot_comment_approve_or_publish():
    p = proposal(status="aprovada", assignee_id=ENG["id"])
    for action in ("comentar", "aprovar", "publicar", "salvar_copia"):
        assert not workflow.check(action, AGT, p)[0]


def _validated(**kw):
    return proposal(status="em_validacao", assignee_id=ENG["id"], working_commit="abc",
                    check_report={"ok": True, "working_commit": "abc"}, **kw)


def test_specialist_approves_verified_proposal():
    assert workflow.check("aprovar", ESP, _validated())[0]


def test_requester_cannot_approve_own_proposal():
    ok, reason = workflow.check("aprovar", ESP, _validated(requester_id=ESP["id"]))
    assert not ok and "própria" in reason


def test_cannot_approve_unverified_working_copy():
    p = _validated()
    p["working_commit"] = "def"  # correção salva depois da verificação
    assert not workflow.check("aprovar", ESP, p)[0]


def test_publish_only_when_approved():
    assert workflow.check("publicar", ENG, proposal(status="aprovada", assignee_id=ENG["id"]))[0]
    assert not workflow.check("publicar", ENG, proposal(status="em_validacao", assignee_id=ENG["id"]))[0]
    assert not workflow.check("publicar", ESP, proposal(status="aprovada", assignee_id=ENG["id"]))[0]


def test_reject_not_after_decision():
    assert workflow.check("rejeitar", ESP, proposal(status="pendente"))[0]
    for status in ("aprovada", "rejeitada", "publicada"):
        assert not workflow.check("rejeitar", ESP, proposal(status=status))[0]
