"""Papéis, matriz de permissões (PocGov seção 2) e sessão de login."""
from functools import wraps

from flask import current_app, g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from services import db

ROLES = {
    "engenheiro": "Engenheiro de Conhecimento",
    "especialista": "Especialista de Domínio",
    "stakeholder": "Stakeholder",
    "agente": "Agente LLM",
}
HUMAN_ROLES = ("engenheiro", "especialista", "stakeholder")
ALL_ROLES = frozenset(ROLES)

# Matriz de permissões. Cada ação -> papéis que podem executá-la.
PERMISSIONS = {
    "consultar_ontologia": ALL_ROLES,
    "consultar_historico": ALL_ROLES,                       # Version Log, versões, CDL
    "solicitar_alteracao": ALL_ROLES,                       # abrir issue
    "comentar": frozenset({"engenheiro", "especialista", "stakeholder"}),
    "gerar_candidatos": frozenset({"agente"}),
    # O Agente gera os candidatos; quem dispara a ingestão do corpus é o Engenheiro.
    "executar_agente": frozenset({"engenheiro"}),
    "cadastrar_ontologia": frozenset({"engenheiro"}),
    "analisar_proposta": frozenset({"engenheiro"}),         # assumir a solicitação (Em análise)
    "editar_ontologia": frozenset({"engenheiro"}),          # criar/alterar classes, relações e triplas
    "corrigir_triplas": frozenset({"engenheiro", "especialista"}),
    "submeter_verificacao": frozenset({"engenheiro"}),
    "validar_alteracao": frozenset({"especialista"}),       # aprovar, rejeitar, solicitar ajustes
    "publicar_versao": frozenset({"engenheiro"}),
}

AGENT_USERNAME = "agente-llm"


def has_permission(user, action):
    return bool(user) and user["role"] in PERMISSIONS.get(action, frozenset())


def permissions_of(user):
    return sorted(a for a in PERMISSIONS if has_permission(user, a))


def public_user(user):
    if not user:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "role_label": ROLES[user["role"]],
    }


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------
def get_user(user_id):
    return db.fetch_one("SELECT * FROM users WHERE id = %s AND active", (user_id,))


def get_user_by_username(username):
    return db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))


def agent_user():
    return get_user_by_username(AGENT_USERNAME)


def create_user(username, display_name, password, role):
    if role not in ROLES:
        raise ValueError(f"Papel inválido: {role}")
    pwd_hash = generate_password_hash(password) if password else None
    return db.execute(
        "INSERT INTO users (username, display_name, password_hash, role) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (username) DO NOTHING RETURNING *",
        (username, display_name, pwd_hash, role),
    )


def authenticate(username, password):
    user = get_user_by_username(username)
    if not user or not user["active"] or not user["password_hash"]:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def seed_users(seed_password):
    """Garante o ator automatizado e, num banco vazio, contas de demonstração para cada papel."""
    create_user(AGENT_USERNAME, "Agente LLM (Ontology Learning)", None, "agente")
    humans = db.fetch_one("SELECT count(*) AS n FROM users WHERE role <> 'agente'")["n"]
    if humans == 0:
        create_user("engenheiro", "Engenheiro de Conhecimento (demo)", seed_password, "engenheiro")
        create_user("especialista", "Especialista de Domínio (demo)", seed_password, "especialista")
        create_user("stakeholder", "Stakeholder (demo)", seed_password, "stakeholder")
        print("[AUTH] Contas de demonstração criadas (senha em SEED_PASSWORD).")


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------
def login_user(user):
    session.clear()
    session["uid"] = user["id"]
    session.permanent = True


def logout_user():
    session.clear()


def current_user():
    if "current_user" not in g:
        uid = session.get("uid")
        g.current_user = get_user(uid) if uid else None
    return g.current_user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Faça login para realizar esta ação."}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_permission(action):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Faça login para realizar esta ação."}), 401
            if not has_permission(user, action):
                current_app.logger.info("Permissão negada: %s -> %s", user["username"], action)
                return jsonify({"error": f"Seu papel ({ROLES[user['role']]}) não permite esta ação."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
