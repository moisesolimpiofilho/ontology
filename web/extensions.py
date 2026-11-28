import os
from contextlib import closing

import psycopg2
from neo4j import GraphDatabase
from pymongo import MongoClient

# Variáveis globais que serão inicializadas no app.py
neo4j_driver = None
mongo_client = None


def init_db_clients(app):
    global neo4j_driver, mongo_client

    # Neo4j
    # Timeouts curtos: com o Neo4j fora do ar o upload falha rápido (padrão do driver passa de 1 min)
    neo4j_driver = GraphDatabase.driver(
        app.config['NEO4J_URI'],
        auth=(app.config['NEO4J_USER'], app.config['NEO4J_PASSWORD']),
        connection_timeout=5,
        connection_acquisition_timeout=10,
        max_transaction_retry_time=5,
    )
    # Constraints de unicidade (também criam índice, evitando full scan nos MERGE)
    try:
        with neo4j_driver.session() as session:
            session.run("CREATE CONSTRAINT class_uri IF NOT EXISTS FOR (c:Class) REQUIRE c.uri IS UNIQUE")
            session.run("CREATE CONSTRAINT individual_uri IF NOT EXISTS FOR (i:Individual) REQUIRE i.uri IS UNIQUE")
        print("[DB] Neo4j conectado e constraints verificadas.")
    except Exception as e:
        print(f"[DB] Aviso: Neo4j indisponível no boot: {e}")

    # MongoDB
    mongo_client = MongoClient(app.config['MONGO_URI'])

    # Postgres (psycopg2 direto, sem pool). Aplica o schema da governança e cria as contas iniciais.
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    try:
        with closing(psycopg2.connect(app.config['PG_DSN'])) as conn:
            with conn.cursor() as cur, open(schema_path, encoding="utf-8") as f:
                cur.execute(f.read())
            conn.commit()
        with app.app_context():
            from services.auth import seed_users
            seed_users(app.config['SEED_PASSWORD'])
        print("[DB] Postgres conectado e schema de governança verificado.")
    except Exception as e:
        print(f"[DB] Aviso: Postgres indisponível no boot: {e}")
