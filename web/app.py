import getpass
import os
from datetime import date, datetime

import click
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider

from config import Config
from extensions import init_db_clients
from routes.auth import auth_bp
from routes.governance import gov_bp
from routes.main import main_bp

# Cabeçalho exigido em requisições que alteram estado (proteção simples contra CSRF:
# formulários de outros sites não conseguem enviar cabeçalhos customizados).
CSRF_HEADER = "X-OntoCube"


class IsoJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json = IsoJSONProvider(app)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPOS_DIR'], exist_ok=True)

    init_db_clients(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(gov_bp)

    @app.before_request
    def csrf_guard():
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get(CSRF_HEADER) != "1":
                return jsonify({"error": "Requisição recusada (cabeçalho de segurança ausente)."}), 403

    @app.errorhandler(413)
    def file_too_large(_err):
        limit_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        return jsonify({"error": f"Conteúdo maior que o limite de {limit_mb} MB"}), 413

    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("role", type=click.Choice(["engenheiro", "especialista", "stakeholder"]))
    @click.option("--name", "display_name", default=None, help="Nome exibido")
    def create_user_cmd(username, role, display_name):
        """Cria um usuário com papel (ex.: flask --app app create-user maria especialista)."""
        from services.auth import create_user
        password = getpass.getpass("Senha: ")
        if len(password) < 8:
            raise click.ClickException("A senha deve ter pelo menos 8 caracteres.")
        if not create_user(username.lower(), display_name or username, password, role):
            raise click.ClickException("Usuário já existe.")
        click.echo(f"Usuário {username} criado com papel {role}.")

    return app


if __name__ == "__main__":
    app = create_app()
    # Debug (reloader + debugger interativo) só quando pedido explicitamente
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
