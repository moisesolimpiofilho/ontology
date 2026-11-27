from datetime import datetime
from psycopg2.extras import Json
import psycopg2

import extensions 

def save_to_postgres(pg_dsn, filename, base_iri, parsed):
    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ontology_uploads
                    (filename, base_iri, class_count, ind_count, prop_count, extras)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    filename, base_iri,
                    len(parsed["classes"]), len(parsed["individuals"]),
                    len(parsed["obj_props"]) + len(parsed["data_props"]),
                    Json({"obj_props": len(parsed["obj_props"]), "data_props": len(parsed["data_props"])}),
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id

def save_to_mongo(mongo_db_name, filename, raw_content, parsed):
    db = extensions.mongo_client[mongo_db_name]
    coll = db["ontology_snapshots"]
    result = coll.insert_one({
        "filename": filename,
        "uploaded_at": datetime.utcnow(),
        "raw_owl": raw_content,
        "parsed": parsed,
    })
    return str(result.inserted_id)

def save_to_neo4j(parsed, base_iri):
    with extensions.neo4j_driver.session() as session:
        # Classes
        session.run(
            "UNWIND $rows AS row MERGE (c:Class {uri: row.uri}) SET c.label = row.label, c.comment = row.comment, c.ontology = $iri",
            rows=parsed["classes"], iri=base_iri
        )
        # Subclasses
        subclass_rows = [{"child": c["uri"], "parent": p} for c in parsed["classes"] for p in c["parents"]]
        session.run(
            "UNWIND $rows AS row MATCH (child:Class {uri: row.child}) MERGE (parent:Class {uri: row.parent}) MERGE (child)-[:SUBCLASS_OF]->(parent)",
            rows=subclass_rows
        )
        # Object Properties
        for op in parsed["obj_props"]:
            if op["domain"] and op["range"]:
                session.run(
                    "MATCH (d:Class {uri: $domain}) MATCH (r:Class {uri: $range}) MERGE (d)-[rel:RELATION {name: $name}]->(r) SET rel.label = $label",
                    domain=op["domain"], range=op["range"],
                    name=op["uri"].split("#")[-1].split("/")[-1], label=op["label"]
                )
        # Indivíduos
        session.run(
            "UNWIND $rows AS row MERGE (i:Individual {uri: row.uri}) SET i.label = row.label, i.ontology = $iri",
            rows=parsed["individuals"], iri=base_iri
        )
        # Tipos
        type_rows = [{"ind": ind["uri"], "type": t} for ind in parsed["individuals"] for t in ind["types"] if t != str(OWL.NamedIndividual)]
        if type_rows:
            session.run(
                "UNWIND $rows AS row MATCH (i:Individual {uri: row.ind}) MERGE (t:Class {uri: row.type}) MERGE (i)-[:TYPE_OF]->(t)",
                rows=type_rows
            )