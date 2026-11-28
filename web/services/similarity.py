"""Filtragem de candidatos por similaridade vetorial (PocGov seção 1.4).

Vetores esparsos de n-gramas de caracteres + palavras (hashing trick), comparados por cosseno.
Leve e determinístico: não exige serviço de embeddings. Serve para descartar candidatos que
duplicam entidades existentes (ou outros candidatos) antes de abrir a proposta.
"""
import math
import re
import unicodedata
import zlib

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def normalize(text):
    text = _CAMEL_RE.sub(" ", str(text or ""))
    text = text.replace("_", " ").replace("-", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def vectorize(text, dim=4096):
    norm = normalize(text)
    vec = {}
    feats = norm.split()
    padded = f" {norm} "
    feats += [padded[i:i + 3] for i in range(len(padded) - 2)]
    for f in feats:
        idx = zlib.crc32(f.encode()) % dim
        vec[idx] = vec.get(idx, 0.0) + 1.0
    length = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / length for k, v in vec.items()}


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _key_text(item):
    return f"{item.get('name', '')} {item.get('label', '')}"


def filter_candidates(candidates, existing, threshold=0.82):
    """Separa candidatos novos dos que duplicam entidades existentes ou outros candidatos.

    candidates: [{name, label, ...}]; existing: [{iri, name, label}].
    """
    existing_vecs = [(e, vectorize(_key_text(e))) for e in existing]
    kept, rejected, kept_vecs = [], [], []
    for cand in candidates:
        v = vectorize(_key_text(cand))
        best, best_score = None, 0.0
        for e, ev in existing_vecs:
            s = cosine(v, ev)
            if s > best_score:
                best, best_score = e, s
        if best is not None and best_score >= threshold:
            rejected.append({**cand, "similarity": round(best_score, 3),
                             "reason": f"Semelhante a entidade existente: {best.get('label') or best.get('name')}",
                             "nearest": best.get("iri") or best.get("name")})
            continue
        dup = next((k for k, kv in zip(kept, kept_vecs) if cosine(v, kv) >= threshold), None)
        if dup is not None:
            rejected.append({**cand, "similarity": round(cosine(v, vectorize(_key_text(dup))), 3),
                             "reason": f"Duplica outro candidato: {dup['name']}", "nearest": dup["name"]})
            continue
        cand = {**cand, "similarity": round(best_score, 3),
                "nearest": (best.get("iri") or best.get("name")) if best else None}
        kept.append(cand)
        kept_vecs.append(v)
    return kept, rejected
