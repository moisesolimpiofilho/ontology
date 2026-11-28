"""Ciclo de vida das propostas de alteração (PocGov seções 3 e 4.4).

Funções puras: recebem o usuário (dict com id/role) e a proposta (dict) e dizem se a ação
é permitida e por quê. As rotas só executam o que `check` libera.
"""
from services.auth import has_permission

STATUSES = {
    "pendente": "Pendente",
    "em_analise": "Em análise",
    "inconsistente": "Inconsistente",
    "em_validacao": "Em validação",
    "aguardando_ajustes": "Aguardando ajustes",
    "aprovada": "Aprovada",
    "rejeitada": "Rejeitada",
    "publicada": "Publicada",
}
FINAL_STATUSES = {"rejeitada", "publicada"}
ENGINEER_EDIT_STATUSES = {"em_analise", "inconsistente", "aguardando_ajustes"}

ACTIONS = {
    "iniciar_analise": "Iniciar análise",
    "salvar_copia": "Salvar cópia de trabalho",
    "submeter": "Submeter à verificação automática",
    "solicitar_ajustes": "Solicitar ajustes",
    "aprovar": "Aprovar",
    "rejeitar": "Rejeitar",
    "publicar": "Publicar nova versão",
    "comentar": "Comentar",
}


def _is_assignee(user, p):
    return p.get("assignee_id") == user["id"]


def check(action, user, p):
    """Retorna (permitido: bool, motivo: str)."""
    if not user:
        return False, "Faça login."
    status = p["status"]
    role_ok = {
        "iniciar_analise": "analisar_proposta",
        "salvar_copia": "corrigir_triplas",
        "submeter": "submeter_verificacao",
        "solicitar_ajustes": "validar_alteracao",
        "aprovar": "validar_alteracao",
        "rejeitar": "validar_alteracao",
        "publicar": "publicar_versao",
        "comentar": "comentar",
    }.get(action)
    if role_ok is None:
        return False, "Ação desconhecida."
    if not has_permission(user, role_ok):
        return False, "Seu papel não permite esta ação."

    if action == "comentar":
        return True, ""

    if action == "iniciar_analise":
        if status != "pendente":
            return False, "Só solicitações pendentes podem entrar em análise."
        return True, ""

    if action == "salvar_copia":
        if user["role"] == "engenheiro":
            if not _is_assignee(user, p):
                return False, "Só o Engenheiro responsável pela análise edita a cópia de trabalho."
            if status not in ENGINEER_EDIT_STATUSES:
                return False, "A cópia de trabalho só pode ser editada em análise, inconsistente ou aguardando ajustes."
            return True, ""
        if user["role"] == "especialista":
            if status != "em_validacao":
                return False, "O Especialista corrige triplas apenas durante a validação."
            return True, ""
        return False, "Seu papel não permite editar a cópia de trabalho."

    if action == "submeter":
        if not _is_assignee(user, p):
            return False, "Só o Engenheiro responsável submete a proposta."
        if status not in ENGINEER_EDIT_STATUSES:
            return False, "A proposta não está em uma etapa de edição."
        if not p.get("working_copy"):
            return False, "Salve a cópia de trabalho antes de submeter."
        return True, ""

    if action == "solicitar_ajustes":
        if status != "em_validacao":
            return False, "Só propostas em validação podem ser devolvidas para ajustes."
        return True, ""

    if action == "aprovar":
        if status != "em_validacao":
            return False, "Só propostas em validação podem ser aprovadas."
        # Separação de responsabilidades: quem pediu ou construiu a alteração não aprova.
        if user["id"] in (p.get("requester_id"), p.get("assignee_id")):
            return False, "O responsável por uma alteração não aprova a própria proposta."
        report = p.get("check_report") or {}
        if not report.get("ok") or report.get("working_commit") != p.get("working_commit"):
            return False, "A versão atual da cópia de trabalho não passou pela verificação automática."
        return True, ""

    if action == "rejeitar":
        if status in FINAL_STATUSES or status == "aprovada":
            return False, "Esta proposta já foi decidida."
        return True, ""

    if action == "publicar":
        if status != "aprovada":
            return False, "A publicação só é permitida para alterações com status Aprovada."
        return True, ""

    return False, "Ação desconhecida."


def available_actions(user, p):
    return [a for a in ACTIONS if check(a, user, p)[0]]
