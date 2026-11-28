"""Executa o pipeline do Agente LLM com um cliente Claude simulado (sem custo de API).

Uso (dentro do container): python tests/simulate_agent_run.py <ontology_id>
Abre uma solicitação real com origem automática, como o agente faria.
"""
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/tests")

from app import create_app  # noqa: E402
from services import auth, governance, llm_agent  # noqa: E402
from test_agent_and_fair import PAYLOAD, FakeClient  # noqa: E402

ontology_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
app = create_app()
real = llm_agent.generate_candidates


def simulated(config, *args, **kwargs):
    kwargs["client"] = FakeClient(PAYLOAD)
    return real({**config, "ANTHROPIC_API_KEY": "simulado"}, *args, **kwargs)


governance.llm_agent.generate_candidates = simulated

with app.app_context():
    engineer = auth.get_user_by_username("engenheiro")
    result = governance.run_agent(engineer, ontology_id,
                                  "O professor leciona no curso. Cada aluno tem número de matrícula.",
                                  "Regimento docente (simulação)")
    p = result["proposal"]
    print("proposta:", p and p["id"], "| origem:", p and p["origin"], "| solicitante:", p and p["requester_name"])
    print("candidatos:", [c["name"] for c in result["candidates"]])
    print("descartados:", [(c["name"], c["reason"]) for c in result["filtered_out"]])
