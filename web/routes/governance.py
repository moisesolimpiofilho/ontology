import os

from flask import Blueprint, Response, current_app, jsonify, request

import extensions
from services import auth, cdl, governance, llm_agent, workflow
from services.auth import current_user, require_permission
from services.governance import GovernanceError
from services.llm_agent import AgentError, AgentNotConfigured

gov_bp = Blueprint("governance", __name__, url_prefix="/api")

SOP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "governanca")


@gov_bp.errorhandler(GovernanceError)
def _gov_error(err):
    return jsonify({"error": str(err)}), err.status


@gov_bp.errorhandler(cdl.CDLError)
def _cdl_error(err):
    return jsonify({"error": f"CDL: {err}"}), 400


def _json():
    return request.get_json(silent=True) or {}


def _public_proposal(p):
    out = dict(p)
    out.pop("working_copy", None)
    report = out.get("check_report")
    if report:
        out["check_report"] = {k: v for k, v in report.items() if k != "inferred_full"}
    return out


# ---------------------------------------------------------------------------
# Metadados do fluxo (status, ações, papéis)
# ---------------------------------------------------------------------------
@gov_bp.get("/governance/meta")
def meta():
    return jsonify({
        "statuses": workflow.STATUSES,
        "actions": workflow.ACTIONS,
        "roles": auth.ROLES,
        "permissions": {k: sorted(v) for k, v in auth.PERMISSIONS.items()},
        "licenses": {"CC-BY-4.0": "CC BY 4.0 (padrão)", "CC0-1.0": "CC0 1.0"},
        "agent_enabled": llm_agent.is_configured(current_app.config),
    })


@gov_bp.get("/governance/sops")
@require_permission("consultar_ontologia")
def list_sops():
    docs = []
    for name in sorted(os.listdir(SOP_DIR)) if os.path.isdir(SOP_DIR) else []:
        if name.endswith(".md"):
            with open(os.path.join(SOP_DIR, name), encoding="utf-8") as f:
                first = f.readline().lstrip("# ").strip()
            docs.append({"id": name[:-3], "title": first})
    return jsonify(docs)


@gov_bp.get("/governance/sops/<doc_id>")
@require_permission("consultar_ontologia")
def get_sop(doc_id):
    if not doc_id.replace("-", "").replace("_", "").isalnum():
        return jsonify({"error": "Documento inválido."}), 400
    path = os.path.join(SOP_DIR, doc_id + ".md")
    if not os.path.isfile(path):
        return jsonify({"error": "Documento não encontrado."}), 404
    with open(path, encoding="utf-8") as f:
        return jsonify({"id": doc_id, "content": f.read()})


# ---------------------------------------------------------------------------
# Ontologias e versões
# ---------------------------------------------------------------------------
@gov_bp.get("/ontologies")
@require_permission("consultar_ontologia")
def ontologies():
    return jsonify(governance.list_ontologies())


@gov_bp.post("/ontologies")
@require_permission("cadastrar_ontologia")
def register_ontology():
    d = _json()
    onto = governance.register_ontology(current_user(), d.get("name"), d.get("iri"), d.get("description"),
                                        d.get("license") or "CC-BY-4.0", d.get("content"))
    return jsonify(onto), 201


@gov_bp.get("/ontologies/<int:oid>")
@require_permission("consultar_ontologia")
def ontology(oid):
    onto = governance.get_ontology(oid)
    return jsonify({**onto, "versions": governance.list_versions(oid)})


@gov_bp.get("/ontologies/<int:oid>/versions/<version>")
@require_permission("consultar_historico")
def version(oid, version):
    v = governance.get_version(oid, version)
    fmt = request.args.get("format")
    if fmt == "owl":
        onto = governance.get_ontology(oid)
        return Response(v["content"], mimetype="application/rdf+xml",
                        headers={"Content-Disposition": f'attachment; filename="{onto["slug"]}-{version}.owl"'})
    if fmt == "raw":
        return Response(v["content"], mimetype="application/rdf+xml")
    v.pop("content", None)
    v["inferred_count"] = len(v.get("inferred") or [])
    v["inferred"] = (v.get("inferred") or [])[:300]
    return jsonify(v)


@gov_bp.get("/ontologies/<int:oid>/git-log")
@require_permission("consultar_historico")
def git_log(oid):
    onto = governance.get_ontology(oid)
    repo = governance._repo(onto)
    return jsonify({"log": repo.log("--all", 60), "tags": repo.tags()})


@gov_bp.get("/ontologies/<int:oid>/graph")
@require_permission("consultar_ontologia")
def ontology_graph(oid):
    onto = governance.get_ontology(oid)
    with extensions.neo4j_driver.session() as session:
        nodes = session.run(
            "MATCH (c:Class) WHERE $iri IN c.ontologies RETURN c.uri AS uri, c.label AS label",
            iri=onto["iri"]).data()
        edges = session.run(
            "MATCH (c:Class)-[r]->(m) WHERE $iri IN c.ontologies "
            "RETURN c.uri AS src, type(r) AS rel, coalesce(r.name, '') AS name, m.uri AS dst LIMIT 500",
            iri=onto["iri"]).data()
    return jsonify({"nodes": nodes, "edges": edges})


@gov_bp.get("/ontologies/<int:oid>/version-log")
@require_permission("consultar_historico")
def version_log(oid):
    governance.get_ontology(oid)
    return jsonify(governance.version_log(oid))


@gov_bp.post("/ontologies/<int:oid>/cdl")
@require_permission("consultar_historico")
def run_cdl(oid):
    governance.get_ontology(oid)
    query = cdl.parse(_json().get("query"))
    result = cdl.execute(query, governance.version_log(oid), governance.versions_with_content(oid))
    return jsonify({"query": query, **result})


# ---------------------------------------------------------------------------
# Propostas (issues)
# ---------------------------------------------------------------------------
@gov_bp.get("/proposals")
@require_permission("consultar_historico")
def proposals():
    status = request.args.get("status")
    return jsonify(governance.list_proposals(
        ontology_id=request.args.get("ontology_id", type=int),
        status=status.split(",") if status else None,
        mine_user=current_user() if request.args.get("mine") == "1" else None,
    ))


@gov_bp.post("/proposals")
@require_permission("solicitar_alteracao")
def create_proposal():
    d = _json()
    affected = d.get("affected_elements") or []
    if isinstance(affected, str):
        affected = [a for a in affected.replace("\n", ",").split(",")]
    p = governance.create_proposal(current_user(), d.get("ontology_id"), d.get("title"), d.get("description"),
                                   d.get("justification"), affected, d.get("source"), d.get("evidence"))
    return jsonify(_public_proposal(p)), 201


@gov_bp.get("/proposals/<int:pid>")
@require_permission("consultar_historico")
def proposal(pid):
    return jsonify(_public_proposal(governance.proposal_detail(pid, current_user())))


@gov_bp.get("/proposals/<int:pid>/working-copy")
@require_permission("consultar_historico")
def proposal_working_copy(pid):
    p = governance.get_proposal(pid)
    if not p.get("base_version"):
        raise GovernanceError("A proposta ainda não tem versão base (aguardando análise).")
    which = request.args.get("which", "working")
    content = governance.base_content(p) if which == "base" else governance.working_content(p)
    return Response(content, mimetype="application/rdf+xml")


@gov_bp.post("/proposals/<int:pid>/comments")
@require_permission("comentar")
def comment(pid):
    governance.add_comment(current_user(), pid, _json().get("body"))
    return jsonify(_public_proposal(governance.proposal_detail(pid, current_user()))), 201


@gov_bp.post("/proposals/<int:pid>/working-copy")
@require_permission("corrigir_triplas")
def save_working_copy(pid):
    d = _json()
    p = governance.save_working_copy(current_user(), pid, d.get("base_export"), d.get("new_export"),
                                     submit=bool(d.get("submit")))
    return jsonify(_public_proposal(governance.proposal_detail(p["id"], current_user())))


@gov_bp.post("/proposals/<int:pid>/actions/<action>")
@require_permission("consultar_historico")
def proposal_action(pid, action):
    user, d = current_user(), _json()
    if action == "iniciar_analise":
        governance.start_analysis(user, pid)
    elif action == "submeter":
        governance.submit_for_verification(user, pid)
    elif action in ("aprovar", "rejeitar", "solicitar_ajustes"):
        governance.decide(user, pid, action, d.get("reason"))
    elif action == "reabrir_base_atual":
        governance.reopen_on_current_base(user, pid)
    elif action == "publicar":
        result = governance.publish(user, pid)
        return jsonify({**result, "proposal": _public_proposal(governance.proposal_detail(pid, user))})
    else:
        return jsonify({"error": "Ação desconhecida."}), 400
    return jsonify(_public_proposal(governance.proposal_detail(pid, user)))


# ---------------------------------------------------------------------------
# Agente LLM
# ---------------------------------------------------------------------------
@gov_bp.post("/agent/run")
@require_permission("executar_agente")
def agent_run():
    d = _json()
    try:
        result = governance.run_agent(current_user(), d.get("ontology_id"), d.get("text"), d.get("source"),
                                      max(1, min(int(d.get("max_candidates") or 20), 60)))
    except AgentNotConfigured as e:
        return jsonify({"error": str(e)}), 503
    except AgentError as e:
        return jsonify({"error": str(e)}), 502
    if result.get("proposal"):
        result["proposal"] = _public_proposal(result["proposal"])
    return jsonify(result)
