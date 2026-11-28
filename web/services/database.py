"""Projeções derivadas da versão oficial (a fonte da verdade é Postgres + Git).

- MongoDB: snapshot de cada versão publicada (XML bruto + estrutura) e execuções do Agente LLM.
- Neo4j: grafo da ontologia publicada.
"""
from datetime import datetime, timezone

import extensions


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
def save_version_snapshot(mongo_db_name, ontology, version, raw_content, parsed, reasoner):
    coll = extensions.mongo_client[mongo_db_name]["ontology_snapshots"]
    result = coll.insert_one({
        "ontology_id": ontology["id"],
        "ontology_iri": ontology["iri"],
        "version": version,
        "published_at": datetime.now(timezone.utc),
        "raw_owl": raw_content,
        "parsed": parsed,
        "reasoner": reasoner,
    })
    return str(result.inserted_id)


def save_agent_run(mongo_db_name, document):
    coll = extensions.mongo_client[mongo_db_name]["agent_runs"]
    result = coll.insert_one({**document, "created_at": datetime.now(timezone.utc)})
    return str(result.inserted_id)


# ---------------------------------------------------------------------------
# Neo4j
# ---------------------------------------------------------------------------
# Um mesmo nó (ex.: foaf:Person) pode pertencer a várias ontologias carregadas,
# por isso guardamos uma lista em vez de sobrescrever uma propriedade única.
_ADD_ONTOLOGY = (
    "SET {v}.ontologies = CASE WHEN $iri IN coalesce({v}.ontologies, []) "
    "THEN {v}.ontologies ELSE coalesce({v}.ontologies, []) + $iri END"
)


def _local_name(uri):
    return uri.rstrip("/#").replace("#", "/").split("/")[-1]


def _write_graph(tx, parsed, iri):
    tx.run(
        "UNWIND $rows AS row "
        "MERGE (c:Class {uri: row.uri}) "
        "SET c.label = row.label, c.comment = row.comment "
        + _ADD_ONTOLOGY.format(v="c"),
        rows=parsed["classes"], iri=iri,
    )

    subclass_rows = [{"child": c["uri"], "parent": p} for c in parsed["classes"] for p in c["parents"]]
    tx.run(
        "UNWIND $rows AS row "
        "MATCH (child:Class {uri: row.child}) "
        "MERGE (parent:Class {uri: row.parent}) "
        + _ADD_ONTOLOGY.format(v="parent") + " "
        "MERGE (child)-[:SUBCLASS_OF]->(parent)",
        rows=subclass_rows, iri=iri,
    )

    rel_rows = [
        {"uri": op["uri"], "name": _local_name(op["uri"]), "label": op["label"],
         "domain": op["domain"], "range": op["range"]}
        for op in parsed["obj_props"] if op["domain"] and op["range"]
    ]
    tx.run(
        "UNWIND $rows AS row "
        "MATCH (d:Class {uri: row.domain}) "
        "MATCH (r:Class {uri: row.range}) "
        "MERGE (d)-[rel:RELATION {name: row.name}]->(r) "
        "SET rel.label = row.label, rel.uri = row.uri",
        rows=rel_rows,
    )

    tx.run(
        "UNWIND $rows AS row "
        "MERGE (i:Individual {uri: row.uri}) "
        "SET i.label = row.label "
        + _ADD_ONTOLOGY.format(v="i"),
        rows=parsed["individuals"], iri=iri,
    )

    type_rows = [{"ind": ind["uri"], "type": t} for ind in parsed["individuals"] for t in ind["types"]]
    tx.run(
        "UNWIND $rows AS row "
        "MATCH (i:Individual {uri: row.ind}) "
        "MERGE (t:Class {uri: row.type}) "
        + _ADD_ONTOLOGY.format(v="t") + " "
        "MERGE (i)-[:TYPE_OF]->(t)",
        rows=type_rows, iri=iri,
    )


def _replace_graph(tx, parsed, iri):
    # Desmarca a ontologia dos nós da versão anterior e remove os que eram só dela
    tx.run("MATCH (n) WHERE $iri IN coalesce(n.ontologies, []) "
           "SET n.ontologies = [x IN n.ontologies WHERE x <> $iri]", iri=iri)
    tx.run("MATCH (n) WHERE n.ontologies = [] DETACH DELETE n")
    _write_graph(tx, parsed, iri)


def save_to_neo4j(parsed, base_iri, replace=False):
    """Grava todo o grafo em UMA transação: ou entra tudo, ou nada.

    replace=True: o grafo da ontologia passa a refletir exatamente esta versão.
    """
    with extensions.neo4j_driver.session() as session:
        session.execute_write(_replace_graph if replace else _write_graph, parsed, base_iri)
