"""Verificação automática de consistência (PocGov seção 3.3)."""
import json
import os
import subprocess
import sys
import tempfile

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_reasoner(owl_text, timeout=120):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ontology.owl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(owl_text)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "services.reasoner_worker", path],
                cwd=APP_DIR, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return _error(f"O raciocinador excedeu o tempo limite de {timeout}s.")

    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("RESULT:"):
            return json.loads(line[len("RESULT:"):])
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
    return _error("Falha ao executar o raciocinador: " + " | ".join(tail))


def _error(message):
    return {"reasoner": "HermiT", "status": "error", "consistent": False,
            "unsatisfiable": [], "inferred": [], "message": message}
