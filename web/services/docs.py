"""Documentação gerada a cada versão publicada (PocGov seção 3.5)."""
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from services.fair import missing_metadata
from services.semantics import DC, DCTERMS, license_iri, parse_owl

IMPACT_LABEL = {"major": "Major (breaking change)", "minor": "Minor (adição compatível)",
                "patch": "Patch (correção)", "initial": "Versão inicial"}


def _first(g, s, *preds):
    for p in preds:
        for o in g.objects(s, p):
            return str(o)
    return ""


def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _entities(g, rdf_type):
    rows = []
    for s in sorted({s for s in g.subjects(RDF.type, rdf_type) if isinstance(s, URIRef)}):
        rows.append({
            "iri": str(s),
            "label": _first(g, s, RDFS.label),
            "comment": _first(g, s, RDFS.comment),
            "source": _first(g, s, DCTERMS.source, DC.source),
            "creator": _first(g, s, DCTERMS.creator, DC.creator),
            "fair_missing": missing_metadata(g, s),
        })
    return rows


def generate_documentation(ontology, version, prior_version, impact, content, diff=None,
                           proposal=None, publisher=None, approver=None, published_at=None):
    g = parse_owl(content)
    lines = [
        f"# {ontology['name']} — versão {version}",
        "",
        f"- **IRI:** `{ontology['iri']}`",
        f"- **Versão:** {version}" + (f" (anterior: {prior_version})" if prior_version else ""),
        f"- **Tipo de mudança:** {IMPACT_LABEL.get(impact, impact)}",
        f"- **Licença:** {license_iri(ontology['license'])}",
    ]
    if published_at:
        lines.append(f"- **Publicada em:** {published_at}")
    if publisher:
        lines.append(f"- **Publicada por:** {publisher}")
    if approver:
        lines.append(f"- **Aprovada por:** {approver}")
    if proposal:
        lines.append(f"- **Proposta de origem:** #{proposal['id']} — {_md(proposal['title'])}")
    if ontology.get("description"):
        lines += ["", ontology["description"]]

    if diff and diff.get("concepts"):
        lines += ["", "## Alterações desta versão", "",
                  "| Conceito | Mudança | Impacto | Motivos |", "|---|---|---|---|"]
        for c in diff["concepts"]:
            lines.append(f"| `{_md(c['concept'])}` | {c['change_type']} | {c['impact']} | {_md('; '.join(c['reasons']))} |")

    for title, rdf_type in (("Classes", OWL.Class), ("Relações (ObjectProperty)", OWL.ObjectProperty),
                            ("Atributos (DatatypeProperty)", OWL.DatatypeProperty),
                            ("Indivíduos", OWL.NamedIndividual)):
        rows = _entities(g, rdf_type)
        lines += ["", f"## {title} ({len(rows)})", ""]
        if not rows:
            lines.append("_Nenhum._")
            continue
        lines += ["| IRI | Rótulo | Definição | Fonte | Criador | FAIR |", "|---|---|---|---|---|---|"]
        for r in rows:
            fair = "ok" if not r["fair_missing"] else "falta " + ", ".join(r["fair_missing"])
            lines.append(f"| `{_md(r['iri'])}` | {_md(r['label'])} | {_md(r['comment'])} | "
                         f"{_md(r['source'])} | {_md(r['creator'])} | {fair} |")
    return "\n".join(lines) + "\n"
