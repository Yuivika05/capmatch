"""Data access + retrieval (the 'autonomously gather data' step).
Tries real embeddings (sentence-transformers), falls back to a lightweight
vector so it runs anywhere. Swap for Supabase pgvector in production."""
from __future__ import annotations
import json, math, os, re
from collections import Counter
from functools import lru_cache
from typing import List, Dict

_DIR = os.path.dirname(__file__)

def load_issuers() -> List[Dict]:
    with open(os.path.join(_DIR, "issuers.json")) as f:
        return json.load(f)

def load_investors() -> List[Dict]:
    with open(os.path.join(_DIR, "investors.json")) as f:
        return json.load(f)

def get_issuer(issuer_id: str):
    return next((i for i in load_issuers() if i["id"] == issuer_id), None)

_STOP = {"the","a","an","and","or","of","to","for","in","on","with","we","our",
         "is","are","by","from","that","this","their","at"}

def _bow(text: str) -> Counter:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return Counter(w for w in words if w not in _STOP and len(w) > 2)

def _cosine_bow(a: str, b: str) -> float:
    va, vb = _bow(a), _bow(b)
    if not va or not vb: return 0.0
    common = set(va) & set(vb)
    dot = sum(va[t]*vb[t] for t in common)
    na = math.sqrt(sum(v*v for v in va.values()))
    nb = math.sqrt(sum(v*v for v in vb.values()))
    return dot/(na*nb) if na and nb else 0.0

@lru_cache(maxsize=1)
def _st_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None

def _investor_doc(inv: Dict) -> str:
    return " ".join([inv.get("thesis",""), " ".join(inv.get("sectors",[])),
        " ".join(inv.get("stages",[])), " ".join(inv.get("instruments",[])),
        " ".join(inv.get("geographies",[]))])

def semantic_search_investors(query: str, k: int = 8) -> List[Dict]:
    investors = load_investors()
    model = _st_model()
    if model is not None:
        docs = [_investor_doc(i) for i in investors]
        emb = model.encode([query] + docs, normalize_embeddings=True)
        q, mat = emb[0], emb[1:]
        scores = (mat @ q).tolist()
    else:
        scores = [_cosine_bow(query, _investor_doc(i)) for i in investors]
    ranked = sorted(zip(investors, scores), key=lambda x: x[1], reverse=True)
    out = []
    for inv, sc in ranked[:k]:
        item = dict(inv); item["_retrieval_score"] = round(float(sc), 4); out.append(item)
    return out