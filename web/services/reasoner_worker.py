"""Processo isolado que roda o HermiT (OWL 2 DL, cobre SHOIN(D)) via owlready2.

Uso: python -m services.reasoner_worker <arquivo.owl>
Imprime uma linha `RESULT:<json>` com consistência, classes insatisfatíveis e inferências.
Roda em processo separado para ter timeout e não acumular estado global do owlready2.
"""
import json
import os
import sys
import time

OWL_THING = "http://www.w3.org/2002/07/owl#Thing"
OWL_NOTHING = "http://www.w3.org/2002/07/owl#Nothing"
SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
EQUIVALENT = "http://www.w3.org/2002/07/owl#equivalentClass"
TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _emit(payload):
    print("RESULT:" + json.dumps(payload), flush=True)


def _snapshot(world, owlready2):
    sub, eq, types = set(), set(), set()
    for cls in world.classes():
        for parent in cls.is_a:
            if isinstance(parent, owlready2.ThingClass):
                sub.add((cls.iri, parent.iri))
        for other in cls.equivalent_to:
            if isinstance(other, owlready2.ThingClass):
                eq.add((cls.iri, other.iri))
    for ind in world.individuals():
        for t in ind.is_a:
            if isinstance(t, owlready2.ThingClass):
                types.add((ind.iri, t.iri))
    return sub, eq, types


def main(path):
    started = time.time()
    import owlready2
    from rdflib import Graph
    from rdflib.namespace import OWL

    owlready2.reasoning.JAVA_MEMORY = int(os.getenv("REASONER_JAVA_MEMORY", "768"))

    # owl:imports faria o owlready2 buscar ontologias na rede: removemos antes de raciocinar
    g = Graph()
    g.parse(path, format="xml")
    g.remove((None, OWL.imports, None))
    clean = path + ".clean.owl"
    g.serialize(clean, format="xml")

    world = owlready2.World()
    world.get_ontology("file://" + os.path.abspath(clean)).load()
    before = _snapshot(world, owlready2)

    base = {"reasoner": "HermiT (OWL 2 DL / SROIQ(D) ⊇ SHOIN(D))"}
    try:
        owlready2.sync_reasoner_hermit(world, infer_property_values=False, debug=0)
    except owlready2.OwlReadyInconsistentOntologyError:
        _emit({**base, "status": "inconsistent", "consistent": False, "unsatisfiable": [],
               "inferred": [], "message": "A ontologia é logicamente inconsistente.",
               "duration_s": round(time.time() - started, 2)})
        return
    except Exception as exc:  # erro do Java/HermiT (ex.: construção fora do OWL 2 DL)
        msg = str(exc).strip().splitlines()
        _emit({**base, "status": "error", "consistent": False, "unsatisfiable": [], "inferred": [],
               "message": "Falha ao executar o raciocinador: " + (msg[-1] if msg else type(exc).__name__),
               "duration_s": round(time.time() - started, 2)})
        return

    unsat = sorted({c.iri for c in world.inconsistent_classes()} - {OWL_NOTHING})
    after = _snapshot(world, owlready2)
    inferred = (
        [[s, SUBCLASS, o] for s, o in sorted(after[0] - before[0]) if o not in (OWL_THING, OWL_NOTHING)]
        + [[s, EQUIVALENT, o] for s, o in sorted(after[1] - before[1]) if s != o]
        + [[s, TYPE, o] for s, o in sorted(after[2] - before[2]) if o != OWL_THING]
    )
    _emit({**base, "status": "consistent", "consistent": True, "unsatisfiable": unsat,
           "inferred": inferred,
           "message": "Consistente." if not unsat else f"Consistente, mas com {len(unsat)} classe(s) insatisfatível(is).",
           "duration_s": round(time.time() - started, 2)})


if __name__ == "__main__":
    main(sys.argv[1])
