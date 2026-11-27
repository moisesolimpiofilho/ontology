import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify

from rdflib import Graph, RDF, RDFS, OWL, URIRef
import psycopg2
from psycopg2.extras import Json
from neo4j import GraphDatabase
from pymongo import MongoClient

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "ontology")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------- CONEXÕES ----------------
# Usa os nomes dos serviços do docker-compose como host
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "senha_forte_neo4j")

PG_DSN = os.getenv(
    "PG_DSN",
    "host=postgres dbname=meubanco user=admin password=senha_forte_postgres"
)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:senha_forte_mongo@mongo:27017/ontocube?authSource=admin")
MONGO_DB = os.getenv("MONGO_DB", "ontocube")

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
mongo_client = MongoClient(MONGO_URI)


# ---------------- HELPERS DE PERSISTÊNCIA ----------------
def init_postgres():
    """Cria a tabela de metadados, se não existir."""
    with psycopg2.connect(PG_DSN) as conn:
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


def extract_ontology_data(g: Graph):
    """Extrai classes, propriedades e indivíduos de um rdflib Graph."""
    classes = []
    for cls in g.subjects(RDF.type, OWL.Class):
        classes.append({
            "uri": str(cls),
            "label": str(g.value(cls, RDFS.label) or ""),
            "comment": str(g.value(cls, RDFS.comment) or ""),
            "parents": [str(p) for p in g.objects(cls, RDFS.subClassOf)],
        })

    obj_props = []
    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        obj_props.append({
            "uri": str(p),
            "label": str(g.value(p, RDFS.label) or ""),
            "domain": str(g.value(p, RDFS.domain) or ""),
            "range": str(g.value(p, RDFS.range) or ""),
        })

    data_props = []
    for p in g.subjects(RDF.type, OWL.DatatypeProperty):
        data_props.append({
            "uri": str(p),
            "label": str(g.value(p, RDFS.label) or ""),
            "domain": str(g.value(p, RDFS.domain) or ""),
            "range": str(g.value(p, RDFS.range) or ""),
        })

    individuals = []
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        individuals.append({
            "uri": str(ind),
            "label": str(g.value(ind, RDFS.label) or ""),
            "types": [str(t) for t in g.objects(ind, RDF.type)],
        })

    return {
        "classes": classes,
        "obj_props": obj_props,
        "data_props": data_props,
        "individuals": individuals,
    }


def save_to_neo4j(parsed, base_iri):
    """Salva classes, propriedades e indivíduos como grafo no Neo4j."""
    with neo4j_driver.session() as session:
        # Classes
        session.run(
            """
            UNWIND $rows AS row
            MERGE (c:Class {uri: row.uri})
            SET c.label = row.label,
                c.comment = row.comment,
                c.ontology = $iri
            """,
            rows=parsed["classes"],
            iri=base_iri,
        )
        # Relações de subClassOf
        subclass_rows = [
            {"child": c["uri"], "parent": p}
            for c in parsed["classes"]
            for p in c["parents"]
        ]
        session.run(
            """
            UNWIND $rows AS row
            MATCH (child:Class {uri: row.child})
            MERGE (parent:Class {uri: row.parent})
            MERGE (child)-[:SUBCLASS_OF]->(parent)
            """,
            rows=subclass_rows,
        )

        # Object Properties como tipo de relacionamento
        for op in parsed["obj_props"]:
            if op["domain"] and op["range"]:
                session.run(
                    """
                    MATCH (d:Class {uri: $domain})
                    MATCH (r:Class {uri: $range})
                    MERGE (d)-[rel:RELATION {name: $name}]->(r)
                    SET rel.label = $label
                    """,
                    domain=op["domain"],
                    range=op["range"],
                    name=op["uri"].split("#")[-1].split("/")[-1],
                    label=op["label"],
                )

        # Indivíduos
        session.run(
            """
            UNWIND $rows AS row
            MERGE (i:Individual {uri: row.uri})
            SET i.label = row.label, i.ontology = $iri
            """,
            rows=parsed["individuals"],
            iri=base_iri,
        )
        # Tipos dos indivíduos
        type_rows = [
            {"ind": ind["uri"], "type": t}
            for ind in parsed["individuals"]
            for t in ind["types"]
            if t != str(OWL.NamedIndividual)
        ]
        session.run(
            """
            UNWIND $rows AS row
            MATCH (i:Individual {uri: row.ind})
            MERGE (t:Class {uri: row.type})
            MERGE (i)-[:TYPE_OF]->(t)
            """,
            rows=type_rows,
        )


def save_to_postgres(filename, base_iri, parsed):
    """Grava metadados da ontologia no Postgres."""
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ontology_uploads
                    (filename, base_iri, class_count, ind_count, prop_count, extras)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    filename,
                    base_iri,
                    len(parsed["classes"]),
                    len(parsed["individuals"]),
                    len(parsed["obj_props"]) + len(parsed["data_props"]),
                    Json({"obj_props": len(parsed["obj_props"]),
                          "data_props": len(parsed["data_props"])}),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def save_to_mongo(filename, raw_content, parsed):
    """Guarda o XML bruto + o parse em JSON como um documento."""
    coll = mongo_client[MONGO_DB]["ontology_snapshots"]
    result = coll.insert_one({
        "filename": filename,
        "uploaded_at": datetime.utcnow(),
        "raw_owl": raw_content,
        "parsed": parsed,
    })
    return str(result.inserted_id)


# ---------------- ROTAS ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload-owl", methods=["POST"])
def upload_owl():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nome de arquivo vazio"}), 400
    if not file.filename.lower().endswith((".owl", ".rdf", ".xml", ".rdfs")):
        return jsonify({"error": "Formato inválido"}), 400

    try:
        raw = file.read().decode("utf-8", errors="replace")
        # 1. Parse com rdflib
        g = Graph()
        g.parse(data=raw, format="xml")

        # 2. Extrai dados estruturados
        parsed = extract_ontology_data(g)
        base_iri = str(g.identifier) or "http://example.org/ontocube#"

        # 3. Salva no Postgres (metadados)
        pg_id = save_to_postgres(file.filename, base_iri, parsed)

        # 4. Salva no MongoDB (XML bruto + snapshot JSON)
        mongo_id = save_to_mongo(file.filename, raw, parsed)

        # 5. Salva no Neo4j (grafo)
        save_to_neo4j(parsed, base_iri)

        # 6. Salva o arquivo em disco também (opcional, para uso futuro)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(raw)

        return jsonify({
            "message": "Ontologia processada e salva nos 3 bancos",
            "postgres_id": pg_id,
            "mongo_id": mongo_id,
            "classes": len(parsed["classes"]),
            "obj_props": len(parsed["obj_props"]),
            "data_props": len(parsed["data_props"]),
            "individuals": len(parsed["individuals"]),
            "path": save_path,
        }), 200

    except Exception as e:
        app.logger.exception("Erro ao processar ontologia")
        return jsonify({"error": f"Falha ao processar: {str(e)}"}), 500


@app.route("/ontologies")
def list_ontologies():
    """Lista o histórico de uploads salvos no Postgres."""
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, filename, base_iri, class_count,
                       ind_count, prop_count, uploaded_at
                FROM ontology_uploads
                ORDER BY uploaded_at DESC
                LIMIT 50;
            """)
            rows = cur.fetchall()
    return jsonify([
        {
            "id": r[0], "filename": r[1], "base_iri": r[2],
            "classes": r[3], "individuals": r[4],
            "properties": r[5],
            "uploaded_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ])


@app.route("/ontologies/<int:pg_id>/graph")
def get_ontology_graph(pg_id):
    """Retorna o grafo salvo no Neo4j para aquela ontologia."""
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT base_iri FROM ontology_uploads WHERE id = %s", (pg_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Ontologia não encontrada"}), 404

    base_iri = row[0]
    with neo4j_driver.session() as session:
        result = session.run(
            """
            MATCH (c:Class {ontology: $iri})-[r]->(m)
            RETURN c.uri AS src, type(r) AS rel, m.uri AS dst
            LIMIT 500
            """,
            iri=base_iri,
        )
        edges = [dict(rec) for rec in result]
        nodes = session.run(
            "MATCH (c:Class {ontology: $iri}) RETURN c.uri AS uri, c.label AS label",
            iri=base_iri,
        )
        nodes = [dict(rec) for rec in nodes]

    return jsonify({"nodes": nodes, "edges": edges})


if __name__ == "__main__":
    try:
        init_postgres()
    except Exception as e:
        print(f"[Aviso] Postgres indisponível no boot: {e}")

    app.run(host="0.0.0.0", port=5000, debug=True)