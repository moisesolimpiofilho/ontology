from neo4j import GraphDatabase
from pymongo import MongoClient
import psycopg2

# Variáveis globais que serão inicializadas no app.py
neo4j_driver = None
mongo_client = None

def init_db_clients(app):
    global neo4j_driver, mongo_client
    
    # Neo4j
    neo4j_driver = GraphDatabase.driver(
        app.config['NEO4J_URI'], 
        auth=(app.config['NEO4J_USER'], app.config['NEO4J_PASSWORD'])
    )
    
    # MongoDB
    mongo_client = MongoClient(app.config['MONGO_URI'])
    
    # Postgres (usamos psycopg2 direto, sem pool por enquanto para simplificar)
    # Testa a conexão inicial e cria a tabela
    try:
        with psycopg2.connect(app.config['PG_DSN']) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ontology_uploads (
                        id            SERIAL PRIMARY KEY,
                        filename      TEXT NOT NULL,
                        base_iri      TEXT,
                        class_count   INTEGER DEFAULT 0,
                        ind_count     INTEGER DEFAULT 0,
                        prop_count    INTEGER DEFAULT 0,
                        uploaded_at   TIMESTAMPTZ DEFAULT NOW(),
                        extras        JSONB
                    );
                """)
            conn.commit()
        print("[DB] Postgres conectado e tabela verificada.")
    except Exception as e:
        print(f"[DB] Aviso: Postgres indisponível no boot: {e}")