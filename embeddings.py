"""Real NLP embeddings + FAISS vector search (the ML component, Plan #2).

Pipeline:
    investor/issuer text  ->  Sentence-Transformer  ->  384-dim vector
    vectors  ->  FAISS index (cosine via inner product on normalized vectors)
    query need  ->  embed  ->  FAISS nearest-neighbour search  ->  candidates

Model: 'all-MiniLM-L6-v2' (small, fast, 384-dim). If the model or FAISS isn't
available yet (e.g. still downloading), we transparently fall back to a
bag-of-words cosine so the app never breaks.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import List, Dict

# ---------------- Fallback (dependency-free) ----------------
_STOP = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
         "we", "our", "is", "are", "by", "from", "that", "this", "their", "at"}


def _bow(text: str) -> Counter:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return Counter(w for w in words if w not in _STOP and len(w) > 2)


def _cosine_bow(a: str, b: str) -> float:
    va, vb = _bow(a), _bow(b)
    if not va or not vb:
        return 0.0
    common = set(va) & set(vb)
    dot = sum(va[t] * vb[t] for t in common)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    return dot / (na * nb) if na and nb else 0.0


# ---------------- Real embedding model ----------------
@lru_cache(maxsize=1)
def _model():
    """Load the Sentence-Transformer once. Returns None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


def embed(texts: List[str]):
    """Return normalized embeddings as a numpy array, or None if no model."""
    model = _model()
    if model is None:
        return None
    return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)


# ---------------- FAISS vector index ----------------
class VectorIndex:
    """Wraps a FAISS index over a set of documents. Falls back to BoW cosine."""

    def __init__(self, docs: List[str], ids: List[str]):
        self.docs = docs
        self.ids = ids
        self.index = None
        self.mode = "fallback"
        self._build()

    def _build(self):
        try:
            import faiss
            vecs = embed(self.docs)
            if vecs is None:
                return                      # keep fallback
            dim = vecs.shape[1]
            index = faiss.IndexFlatIP(dim)  # inner product = cosine (normalized)
            index.add(vecs)
            self.index = index
            self.mode = "faiss"
        except Exception:
            self.index = None               # keep fallback

    def add(self, doc: str, doc_id: str) -> None:
        """Add ONE new document to the index at runtime (Kafka pipeline uses this).

        Works in both modes: if FAISS is active we embed the new doc and push its
        vector into the index; otherwise we just append to the fallback lists.
        """
        self.docs.append(doc)
        self.ids.append(doc_id)
        if self.index is not None:
            vec = embed([doc])
            if vec is not None:
                self.index.add(vec)

    def search(self, query: str, k: int = 8) -> List[Dict]:
        if self.index is not None:
            import faiss  # noqa
            qv = embed([query])
            scores, idxs = self.index.search(qv, min(k, len(self.ids)))
            return [{"id": self.ids[i], "score": round(float(s), 4)}
                    for s, i in zip(scores[0], idxs[0]) if i != -1]
        # fallback: bag-of-words cosine over all docs
        scored = [(self.ids[i], _cosine_bow(query, d)) for i, d in enumerate(self.docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{"id": _id, "score": round(s, 4)} for _id, s in scored[:k]]
