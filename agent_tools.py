"""LangChain tools the agent calls (the 'AI-powered tool calling')."""
from __future__ import annotations
import json
from langchain_core.tools import tool
from matching import score_pair
from data_access import load_investors, get_issuer, semantic_search_investors

@tool
def get_issuer_profile(issuer_id: str) -> str:
    """Fetch a single issuer's full profile (its need/mandate) by id."""
    iss = get_issuer(issuer_id)
    return json.dumps(iss) if iss else json.dumps({"error": "not found"})

@tool
def search_investors(query: str, k: int = 8) -> str:
    """Retrieve the k investors most relevant to a free-text need or thesis."""
    hits = semantic_search_investors(query, k=k)
    slim = [{"id": h["id"], "name": h["name"], "sectors": h["sectors"],
             "stages": h["stages"], "thesis": h["thesis"]} for h in hits]
    return json.dumps(slim)

@tool
def score_investor_fit(issuer_id: str, investor_id: str) -> str:
    """Compute an explainable fit score (0-1) with a per-factor breakdown."""
    iss = get_issuer(issuer_id)
    inv = next((x for x in load_investors() if x["id"] == investor_id), None)
    if not iss or not inv:
        return json.dumps({"error": "not found"})
    return json.dumps(score_pair(iss, inv))

TOOLS = [get_issuer_profile, search_investors, score_investor_fit]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}