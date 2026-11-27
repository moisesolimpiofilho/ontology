import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-mude-em-producao")
    
    # Caminhos
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "ontology"))
    
    # Bancos de Dados
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "senha_forte_neo4j")
    
    PG_DSN = os.getenv("PG_DSN", "host=postgres dbname=meubanco user=admin password=senha_forte_postgres")
    
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:senha_forte_mongo@mongo:27017/ontocube?authSource=admin")
    MONGO_DB = os.getenv("MONGO_DB", "ontocube")