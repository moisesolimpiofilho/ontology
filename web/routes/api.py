import os
from flask import Blueprint, request, jsonify, current_app
import psycopg2
from services.parser import extract_ontology_data
from services.database import save_to_postgres, save_to_mongo, save_to_neo4j

import extensions

api_bp = Blueprint('api', __name__)

@api_bp.route('/upload-owl', methods=['POST'])
def upload_owl():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if file.filename == "" or not file.filename.lower().endswith(('.owl', '.rdf', '.xml', '.rdfs')):
        return jsonify({"error": "Arquivo inválido ou formato não suportado"}), 400

    try:
        raw = file.read().decode("utf-8", errors="replace")
        
        # 1. Parse
        base_iri, parsed = extract_ontology_data(raw)

        # 2. Salvar nos Bancos
        pg_id = save_to_postgres(current_app.config['PG_DSN'], file.filename, base_iri, parsed)
        mongo_id = save_to_mongo(current_app.config['MONGO_DB'], file.filename, raw, parsed)
        save_to_neo4j(parsed, base_iri)

        # 3. Salvar arquivo físico (opcional)
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(raw)

        return jsonify({
            "message": "Ontologia processada e salva nos 3 bancos",
            "postgres_id": pg_id,
            "mongo_id": mongo_id,
            "classes": len(parsed["classes"]),
            "individuals": len(parsed["individuals"]),
            "path": save_path,
        }), 200

    except Exception as e:
        current_app.logger.exception("Erro ao processar ontologia")
        return jsonify({"error": f"Falha ao processar: {str(e)}"}), 500


@api_bp.route('/ontologies')
def list_ontologies():
    with psycopg2.connect(current_app.config['PG_DSN']) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, base_iri, class_count, ind_count, prop_count, uploaded_at FROM ontology_uploads ORDER BY uploaded_at DESC LIMIT 50;")
            rows = cur.fetchall()
    return jsonify([
        {"id": r[0], "filename": r[1], "base_iri": r[2], "classes": r[3], "individuals": r[4], "properties": r[5], "uploaded_at": r[6].isoformat() if r[6] else None}
        for r in rows
    ])

@api_bp.route('/ontologies/<int:pg_id>/graph')
def get_ontology_graph(pg_id):
    with psycopg2.connect(current_app.config['PG_DSN']) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT base_iri FROM ontology_uploads WHERE id = %s", (pg_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Ontologia não encontrada"}), 404

    base_iri = row[0]
    with extensions.neo4j_driver.session() as session:
        edges = [dict(rec) for rec in session.run("MATCH (c:Class {ontology: $iri})-[r]->(m) RETURN c.uri AS src, type(r) AS rel, m.uri AS dst LIMIT 500", iri=base_iri)]
        nodes = [dict(rec) for rec in session.run("MATCH (c:Class {ontology: $iri}) RETURN c.uri AS uri, c.label AS label", iri=base_iri)]

    return jsonify({"nodes": nodes, "edges": edges})