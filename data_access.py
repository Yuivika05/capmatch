"""Data access + semantic retrieval.

Loads issuers/investors and provides `semantic_search_investors`, now backed by
a real FAISS vector index over Sentence-Transformer embeddings (see embeddings.py).
The index is built once and cached. Swap the JSON loaders for Supabase later
without changing the agent.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import List, Dict

from embeddings import VectorIndex

_DIR = os.path.dirname(__file__)


def load_issuers() -> List[Dict]:
    with open(os.path.join(_DIR, "issuers.json")) as f:
        return json.load(f)


def load_investors() -> List[Dict]:
    with open(os.path.join(_DIR, "investors.json")) as f:
        return json.load(f)


def get_issuer(issuer_id: str):
    return next((i for i in load_issuers() if i["id"] == issuer_id), None)


def _investor_doc(inv: Dict) -> str:
    return " ".join([
        inv.get("thesis", ""),
        " ".join(inv.get("sectors", [])),
        " ".join(inv.get("stages", [])),
        " ".join(inv.get("instruments", [])),
        " ".join(inv.get("geographies", [])),
    ])


@lru_cache(maxsize=1)
def _investor_index() -> VectorIndex:
    investors = load_investors()
    docs = [_investor_doc(i) for i in investors]
    ids = [i["id"] for i in investors]
    return VectorIndex(docs, ids)


def all_investors() -> List[Dict]:
    """JSON investors PLUS any added live via the Kafka-style pipeline."""
    investors = load_investors()
    try:
        from embedding_service import runtime_investors
        investors = investors + runtime_investors()
    except Exception:
        pass
    return investors


def semantic_search_investors(query: str, k: int = 8) -> List[Dict]:
    """Return the k most semantically-similar investors to the query text."""
    index = _investor_index()
    hits = index.search(query, k=k)           # [{"id","score"}]
    by_id = {i["id"]: i for i in all_investors()}
    out = []
    for h in hits:
        inv = by_id.get(h["id"])
        if inv:
            item = dict(inv)
            item["_retrieval_score"] = h["score"]
            out.append(item)
    return out


def retrieval_mode() -> str:
    """'faiss' if real embeddings are active, else 'fallback' (bag-of-words)."""
    return _investor_index().mode
