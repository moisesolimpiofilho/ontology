import re

from flask import Blueprint, jsonify, request

from services import auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")


def _me_payload():
    user = auth.current_user()
    return {
        "user": auth.public_user(user),
        "permissions": auth.permissions_of(user),
        "roles": auth.ROLES,
    }


@auth_bp.get("/me")
def me():
    return jsonify(_me_payload())


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = auth.authenticate((data.get("username") or "").strip().lower(), data.get("password") or "")
    if not user:
        return jsonify({"error": "Usuário ou senha inválidos."}), 401
    auth.login_user(user)
    return jsonify(_me_payload())


@auth_bp.post("/logout")
def logout():
    auth.logout_user()
    return jsonify({"ok": True})


@auth_bp.post("/register")
def register():
    """Autocadastro: sempre como Stakeholder (papéis com escrita são atribuídos via CLI)."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip() or username
    password = data.get("password") or ""
    if not USERNAME_RE.match(username):
        return jsonify({"error": "Usuário deve ter 3-40 caracteres: letras minúsculas, números, '.', '_' ou '-'."}), 400
    if len(password) < 8:
        return jsonify({"error": "A senha deve ter pelo menos 8 caracteres."}), 400
    user = auth.create_user(username, display_name, password, "stakeholder")
    if not user:
        return jsonify({"error": "Este usuário já existe."}), 409
    auth.login_user(user)
    return jsonify(_me_payload()), 201
