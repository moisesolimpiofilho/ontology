"""Teste ponta a ponta do fluxo de governança contra a API em execução.

Uso (dentro do container):  python tests/e2e_governance.py [http://localhost:5000]
Cria dados reais (ontologia de teste com IRI único, propostas, versões).
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
PWD = os.environ.get("SEED_PASSWORD", "ontocube123")
STAMP = str(int(time.time()))
IRI = f"http://example.org/e2e{STAMP}"
NS = IRI + "#"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, csrf=True, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if csrf:
            req.add_header("X-OntoCube", "1")
        try:
            with self.opener.open(req) as resp:
                text = resp.read().decode()
                return resp.status, (text if raw else json.loads(text or "null"))
        except urllib.error.HTTPError as e:
            text = e.read().decode()
            try:
                return e.code, json.loads(text)
            except json.JSONDecodeError:
                return e.code, text

    def login(self, user):
        status, body = self.call("POST", "/api/auth/login", {"username": user, "password": PWD})
        assert status == 200, body
        return body


def owl(body):
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns="{NS}" xmlns:owl="http://www.w3.org/2002/07/owl#"
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:dcterms="http://purl.org/dc/terms/">
  <owl:Ontology rdf:about="{IRI}"/>
{body}
</rdf:RDF>"""


PESSOA = f"""  <owl:Class rdf:about="{NS}Pessoa"><rdfs:label>Pessoa</rdfs:label>
    <rdfs:comment>Ser humano.</rdfs:comment><dcterms:source>Dicionário</dcterms:source>
    <dcterms:creator>Engenheiro</dcterms:creator></owl:Class>
  <owl:Class rdf:about="{NS}Curso"><owl:disjointWith rdf:resource="{NS}Pessoa"/></owl:Class>"""
PROFESSOR_SEM_FAIR = f"""  <owl:Class rdf:about="{NS}Professor"><rdfs:subClassOf rdf:resource="{NS}Pessoa"/></owl:Class>"""
PROFESSOR_FAIR = f"""  <owl:Class rdf:about="{NS}Professor"><rdfs:subClassOf rdf:resource="{NS}Pessoa"/>
    <rdfs:label>Professor</rdfs:label><rdfs:comment>Pessoa que leciona.</rdfs:comment>
    <dcterms:source>Regimento</dcterms:source><dcterms:creator>Engenheiro</dcterms:creator></owl:Class>"""

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("OK   " if cond else "FAIL ") + name + (f"  -> {detail}" if not cond and detail else ""))


anon, eng, esp, stk = Client(), Client(), Client(), Client()

# --- login opcional / proteção --------------------------------------------
s, me = anon.call("GET", "/api/auth/me")
check("visitante: /me sem usuário", s == 200 and me["user"] is None)
s, _ = anon.call("GET", "/api/ontologies")
check("visitante: consulta exige login (401)", s == 401)
s, _ = eng.call("POST", "/api/auth/login", {"username": "engenheiro", "password": PWD}, csrf=False)
check("POST sem cabeçalho CSRF é recusado (403)", s == 403)
s, _ = anon.call("POST", "/api/auth/login", {"username": "engenheiro", "password": "errada"})
check("senha errada (401)", s == 401)
check("login engenheiro", "publicar_versao" in eng.login("engenheiro")["permissions"])
esp.login("especialista")
stk_me = stk.login("stakeholder")
check("stakeholder sem permissão de edição", "editar_ontologia" not in stk_me["permissions"])

# --- cadastro ---------------------------------------------------------------
s, _ = stk.call("POST", "/api/ontologies", {"name": "x", "iri": IRI})
check("stakeholder não cadastra ontologia (403)", s == 403)
s, onto = eng.call("POST", "/api/ontologies", {"name": f"E2E {STAMP}", "iri": IRI, "license": "CC-BY-4.0",
                                                "content": owl(PESSOA)})
check("engenheiro cadastra ontologia v1.0.0", s == 201 and onto["current_version"] == "1.0.0", onto)
oid = onto["id"]
s, v1 = eng.call("GET", f"/api/ontologies/{oid}/versions/1.0.0?format=raw", raw=True)
check("v1.0.0 tem owl:versionInfo e licença", "versionInfo" in v1 and "creativecommons.org/licenses/by/4.0" in v1)

# --- solicitação e análise -------------------------------------------------
s, p = stk.call("POST", "/api/proposals", {"ontology_id": oid, "title": "Incluir Professor",
                                           "description": "Precisamos representar professores.",
                                           "justification": "Projeto RADIAR usa o conceito.",
                                           "affected_elements": "Professor", "source": "Regimento"})
check("stakeholder abre solicitação (Pendente)", s == 201 and p["status"] == "pendente" and p["origin"] == "humana", p)
pid = p["id"]
s, _ = stk.call("POST", f"/api/proposals/{pid}/comments", {"body": "Importante para o semestre."})
check("stakeholder comenta (deliberação)", s == 201)
s, _ = esp.call("POST", f"/api/proposals/{pid}/actions/iniciar_analise")
check("especialista não inicia análise (403)", s == 403)
s, p = eng.call("POST", f"/api/proposals/{pid}/actions/iniciar_analise")
check("engenheiro inicia análise", s == 200 and p["status"] == "em_analise" and p["base_version"] == "1.0.0", p)

base_export = owl(PESSOA)
s, p = eng.call("POST", f"/api/proposals/{pid}/working-copy",
                {"base_export": base_export, "new_export": owl(PESSOA + PROFESSOR_SEM_FAIR), "submit": True})
check("submissão sem metadados FAIR -> Inconsistente", s == 200 and p["status"] == "inconsistente", p.get("status"))
check("relatório aponta FAIR", p.get("check_report") and not p["check_report"]["fair"]["ok"])

s, p = eng.call("POST", f"/api/proposals/{pid}/working-copy",
                {"base_export": owl(PESSOA + PROFESSOR_SEM_FAIR), "new_export": owl(PESSOA + PROFESSOR_FAIR)})
check("correção salva volta para Em análise", s == 200 and p["status"] == "em_analise", p.get("status"))
s, p = eng.call("POST", f"/api/proposals/{pid}/actions/submeter")
check("submissão com FAIR -> Em validação", s == 200 and p["status"] == "em_validacao", p)
check("raciocinador: consistente", p["check_report"]["reasoner"]["status"] == "consistent", p["check_report"]["reasoner"])
check("impacto calculado: minor", p["impact"] == "minor")

s, _ = eng.call("POST", f"/api/proposals/{pid}/actions/aprovar")
check("engenheiro não aprova (403)", s == 403)
s, _ = esp.call("POST", f"/api/proposals/{pid}/actions/rejeitar", {"reason": ""})
check("rejeição exige justificativa (400)", s == 400)
s, p = esp.call("POST", f"/api/proposals/{pid}/actions/aprovar")
check("especialista aprova", s == 200 and p["status"] == "aprovada", p)
s, _ = stk.call("POST", f"/api/proposals/{pid}/actions/publicar")
check("stakeholder não publica (403)", s == 403)
s, pub = eng.call("POST", f"/api/proposals/{pid}/actions/publicar")
check("publicação gera v1.1.0", s == 200 and pub["version"] == "1.1.0" and pub["tag"] == "v1.1.0", pub)
s, v = eng.call("GET", f"/api/ontologies/{oid}/versions/1.1.0?format=raw", raw=True)
check("v1.1.0 tem priorVersion 1.0.0", f"{IRI}/1.0.0" in v and "Professor" in v)

# --- proposta inconsistente (disjunção) e rejeição ---------------------------
s, p2 = esp.call("POST", "/api/proposals", {"ontology_id": oid, "title": "Curso é pessoa?",
                                            "description": "Tornar Curso subclasse de Pessoa.",
                                            "justification": "Teste de inconsistência."})
pid2 = p2["id"]
eng.call("POST", f"/api/proposals/{pid2}/actions/iniciar_analise")
_, cur = eng.call("GET", f"/api/proposals/{pid2}/working-copy", raw=True)
check("cópia de trabalho parte da v1.1.0", "Professor" in cur)
bad = PESSOA.replace('<owl:disjointWith', f'<rdfs:subClassOf rdf:resource="{NS}Pessoa"/><owl:disjointWith')
ind = f'  <owl:NamedIndividual rdf:about="{NS}c1"><rdf:type rdf:resource="{NS}Curso"/></owl:NamedIndividual>'
s, p2 = eng.call("POST", f"/api/proposals/{pid2}/working-copy",
                 {"base_export": owl(PESSOA), "new_export": owl(bad + ind), "submit": True})
rep = (p2.get("check_report") or {}).get("reasoner", {})
check("raciocinador barra proposta inconsistente", p2.get("status") == "inconsistente"
      and (rep.get("status") == "inconsistent" or rep.get("unsatisfiable")), rep)
s, p2 = esp.call("POST", f"/api/proposals/{pid2}/actions/rejeitar", {"reason": "Curso não é pessoa."})
check("rejeição registrada com justificativa", s == 200 and p2["status"] == "rejeitada" and p2["decision_reason"])
check("requisitante não aprova a própria proposta", not p2["actions"]["aprovar"]["allowed"])

# --- Version Log, CDL e Git ---------------------------------------------------
s, res = stk.call("POST", f"/api/ontologies/{oid}/cdl", {"query": "HISTORY Professor"})
check("CDL HISTORY Professor", s == 200 and [r["version"] for r in res["rows"]] == ["1.1.0"], res)
s, res = stk.call("POST", f"/api/ontologies/{oid}/cdl", {"query": "STATE Pessoa AT 1.0.0"})
check("CDL STATE AT", s == 200 and len(res["rows"]) >= 4, res)
s, res = stk.call("POST", f"/api/ontologies/{oid}/cdl", {"query": "CHANGES WHERE impact=minor"})
check("CDL CHANGES WHERE", s == 200 and res["rows"], res)
s, res = stk.call("POST", f"/api/ontologies/{oid}/cdl", {"query": "APAGAR TUDO"})
check("CDL inválida -> 400", s == 400)
s, git = eng.call("GET", f"/api/ontologies/{oid}/git-log")
check("Git: tags v1.0.0 e v1.1.0", s == 200 and {"v1.0.0", "v1.1.0"} <= set(git["tags"]), git.get("tags"))
check("Git: branches das propostas", any(f"proposta/{pid}" in e["refs"] or f"proposta/{pid2}" in e["refs"]
                                         for e in git["log"]))
s, onto2 = stk.call("GET", f"/api/ontologies/{oid}")
check("versões preservadas", [v["version"] for v in onto2["versions"]] == ["1.1.0", "1.0.0"])
s, doc = stk.call("GET", f"/api/ontologies/{oid}/versions/1.1.0")
check("documentação gerada", s == 200 and "Professor" in (doc.get("documentation") or ""))

# --- concorrência: duas propostas sobre a mesma base ---------------------------
def prepare(title, cls_xml):
    _, pr = stk.call("POST", "/api/proposals", {"ontology_id": oid, "title": title, "description": "x",
                                               "justification": "y"})
    eng.call("POST", f"/api/proposals/{pr['id']}/actions/iniciar_analise")
    s, pr = eng.call("POST", f"/api/proposals/{pr['id']}/working-copy",
                     {"base_export": owl(PESSOA), "new_export": owl(PESSOA + cls_xml), "submit": True})
    return pr


def fair_class(name):
    return (f'  <owl:Class rdf:about="{NS}{name}"><rdfs:label>{name}</rdfs:label><rdfs:comment>Def.</rdfs:comment>'
            f'<dcterms:source>Fonte</dcterms:source><dcterms:creator>Eng</dcterms:creator></owl:Class>')


pa, pb = prepare("Incluir Monitor", fair_class("Monitor")), prepare("Incluir Tutor", fair_class("Tutor"))
check("duas propostas em validação sobre a v1.1.0", pa["status"] == pb["status"] == "em_validacao", (pa["status"], pb["status"]))
esp.call("POST", f"/api/proposals/{pa['id']}/actions/aprovar")
esp.call("POST", f"/api/proposals/{pb['id']}/actions/aprovar")
s, pub_a = eng.call("POST", f"/api/proposals/{pa['id']}/actions/publicar")
check("primeira publicada como v1.2.0", s == 200 and pub_a["version"] == "1.2.0", pub_a)
s, err = eng.call("POST", f"/api/proposals/{pb['id']}/actions/publicar")
check("segunda bloqueada: base desatualizada (409)", s == 409, err)
s, pb = eng.call("POST", f"/api/proposals/{pb['id']}/actions/reabrir_base_atual")
check("reaberta sobre a v1.2.0", s == 200 and pb["status"] == "em_analise" and pb["base_version"] == "1.2.0", pb)
_, cur = eng.call("GET", f"/api/proposals/{pb['id']}/working-copy", raw=True)
check("nova cópia parte da v1.2.0 (contém Monitor)", "Monitor" in cur and "Tutor" not in cur)
s, pb = eng.call("POST", f"/api/proposals/{pb['id']}/working-copy",
                 {"base_export": owl(PESSOA), "new_export": owl(PESSOA + fair_class("Tutor")), "submit": True})
esp.call("POST", f"/api/proposals/{pb['id']}/actions/aprovar")
s, pub_b = eng.call("POST", f"/api/proposals/{pb['id']}/actions/publicar")
check("segunda publicada como v1.3.0 sem perder a primeira", s == 200 and pub_b["version"] == "1.3.0", pub_b)
_, v13 = eng.call("GET", f"/api/ontologies/{oid}/versions/1.3.0?format=raw", raw=True)
check("v1.3.0 tem Monitor e Tutor", "Monitor" in v13 and "Tutor" in v13)
s, git = eng.call("GET", f"/api/ontologies/{oid}/git-log")
check("cópia antiga preservada em branch", any(f"proposta/{pb['id']}-base-1.1.0" in e["refs"] for e in git["log"]), [e["refs"] for e in git["log"]])

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} verificações passaram.")
sys.exit(1 if failed else 0)
