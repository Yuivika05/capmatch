"""LangChain tools the agent can call.

These are the 'AI-powered tool calling' capabilities from the brief. The LLM
decides WHEN to call each one; the functions themselves do the real work
(retrieving data, scoring fit, checking ESG). Each tool returns JSON-friendly
data so it can be fed back into the model's reasoning.
"""
from __future__ import annotations

import json
from langchain_core.tools import tool

from matching import score_pair          # reuse our transparent scorer
from data_access import (load_issuers, load_investors,
                         get_issuer, semantic_search_investors)


@tool
def get_issuer_profile(issuer_id: str) -> str:
    """Fetch a single issuer's full profile (its need/mandate) by id."""
    iss = get_issuer(issuer_id)
    if not iss:
        return json.dumps({"error": f"issuer '{issuer_id}' not found"})
    return json.dumps(iss)


@tool
def search_investors(query: str, k: int = 8) -> str:
    """Retrieve the k investors most relevant to a free-text need or thesis.
    Use this to autonomously gather candidate investors before scoring."""
    hits = semantic_search_investors(query, k=k)
    slim = [{"id": h["id"], "name": h["name"], "sectors": h["sectors"],
             "stages": h["stages"], "thesis": h["thesis"]} for h in hits]
    return json.dumps(slim)


@tool
def score_investor_fit(issuer_id: str, investor_id: str) -> str:
    """Compute an explainable fit score (0-1) for one issuer/investor pair,
    with a per-factor breakdown (sector, stage, ticket, geography, esg, thesis)."""
    iss = get_issuer(issuer_id)
    from data_access import all_investors
    inv = next((x for x in all_investors() if x["id"] == investor_id), None)
    if not iss or not inv:
        return json.dumps({"error": "issuer or investor not found"})
    return json.dumps(score_pair(iss, inv))


# The list the LLM is bound to.
TOOLS = [get_issuer_profile, search_investors, score_investor_fit]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
