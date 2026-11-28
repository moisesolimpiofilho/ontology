import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-mude-em-producao")

    # Sessão de login (cookie assinado)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 horas

    # Caminhos
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "ontology"))
    REPOS_DIR = os.getenv("REPOS_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "repos"))

    # Limite de upload (o Mongo guarda o XML bruto num único documento, limitado a 16 MB)
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024

    # Contas de demonstração criadas no primeiro boot (só se não houver usuários)
    SEED_PASSWORD = os.getenv("SEED_PASSWORD", "ontocube123")

    # Raciocinador
    REASONER_TIMEOUT = int(os.getenv("REASONER_TIMEOUT", "120"))

    # Agente LLM
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-5-5")
    LLM_EFFORT = os.getenv("LLM_EFFORT", "high")
    LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "60000"))
    LLM_SIMILARITY_THRESHOLD = float(os.getenv("LLM_SIMILARITY_THRESHOLD", "0.82"))

    # Bancos de Dados
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "senha_forte_neo4j")

    PG_DSN = os.getenv("PG_DSN", "host=postgres dbname=meubanco user=admin password=senha_forte_postgres")

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:senha_forte_mongo@mongo:27017/ontocube?authSource=admin")
    MONGO_DB = os.getenv("MONGO_DB", "ontocube")
