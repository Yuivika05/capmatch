"""Agentic issuer->investor matching as a LangGraph state machine.
Graph: ingest -> retrieve -> score -> reflect --(need more?)--> retrieve
                                          \\--(enough)--> explain -> END
Set GROQ_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY to use a real LLM for
ingest+explain; with no key it runs a deterministic mock so the graph still runs."""
from __future__ import annotations
import os, json
from typing import List, Dict, TypedDict
from langgraph.graph import StateGraph, START, END
from data_access import get_issuer
from agent_tools import TOOLS_BY_NAME

class AgentState(TypedDict):
    issuer_id: str
    query: str
    candidates: List[Dict]
    scored: List[Dict]
    passes: int
    top_k: int
    answer: str
    trace: List[str]

def _get_llm():
    try:
        if os.getenv("GROQ_API_KEY"):
            from langchain_groq import ChatGroq
            return ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)
        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        if os.getenv("GOOGLE_API_KEY"):
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2)
    except Exception:
        return None
    return None

def ingest_node(state):
    iss = get_issuer(state["issuer_id"]) or {}
    query = " ".join([iss.get("sector",""), iss.get("stage",""), iss.get("instrument",""),
        iss.get("geography",""), iss.get("summary","")]).strip()
    llm = _get_llm()
    if llm is not None:
        try:
            query = llm.invoke("Rewrite this issuer's fundraising need into a concise "
                "keyword search query for finding investors:\n"+json.dumps(iss)).content.strip() or query
        except Exception:
            pass
    return {**state, "query": query, "passes": 0,
            "trace": state.get("trace", []) + [f"ingest: query='{query[:80]}'"]}

def retrieve_node(state):
    k = 6 + state.get("passes", 0) * 4
    cands = json.loads(TOOLS_BY_NAME["search_investors"].invoke({"query": state["query"], "k": k}))
    return {**state, "candidates": cands,
            "trace": state["trace"] + [f"retrieve: tool search_investors(k={k}) -> {len(cands)} candidates"]}

def score_node(state):
    scored = []
    for c in state["candidates"]:
        res = json.loads(TOOLS_BY_NAME["score_investor_fit"].invoke(
            {"issuer_id": state["issuer_id"], "investor_id": c["id"]}))
        if "error" not in res:
            scored.append(res)
    scored.sort(key=lambda r: r["score"], reverse=True)
    return {**state, "scored": scored,
            "trace": state["trace"] + [f"score: tool score_investor_fit x{len(scored)}"]}

def reflect_edge(state):
    best = state["scored"][0]["score"] if state["scored"] else 0.0
    if best < 0.6 and state.get("passes", 0) < 1:
        return "retry"
    return "done"

def widen_node(state):
    return {**state, "passes": state.get("passes", 0) + 1,
            "trace": state["trace"] + ["reflect: best<0.60 -> widening search and retrying"]}

def explain_node(state):
    iss = get_issuer(state["issuer_id"]) or {}
    top = state["scored"][: state.get("top_k", 4)]
    llm = _get_llm()
    if llm is not None and top:
        try:
            facts = json.dumps([{"investor": t["investor_name"], "score": t["score"],
                "factors": t["factors"]} for t in top])
            answer = llm.invoke("You are an investment analyst. Write a short explainable, "
                "ranked recommendation citing concrete factors. Do not invent facts.\n"
                f"ISSUER: {json.dumps(iss)}\nCANDIDATES: {facts}").content.strip()
        except Exception:
            answer = _mock(iss, top)
    else:
        answer = _mock(iss, top)
    return {**state, "answer": answer,
            "trace": state["trace"] + [f"explain: produced ranked recommendation for top {len(top)}"]}

def _mock(iss, top):
    lines = [f"Ranked investor matches for {iss.get('name','issuer')} "
             f"(need ${iss.get('ask_amount_usd',0):,.0f}, {iss.get('sector','')}):", ""]
    for i, t in enumerate(top, 1):
        strong = [f["name"] for f in t["factors"] if f["score"] >= 0.75]
        weak = [f["name"] for f in t["factors"] if f["score"] <= 0.25]
        lines.append(f"{i}. {t['investor_name']} — {t['score']*100:.0f}% match")
        if strong: lines.append(f"   strengths: {', '.join(strong)}")
        if weak: lines.append(f"   gaps: {', '.join(weak)}")
    return "\n".join(lines)

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("ingest", ingest_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("score", score_node)
    g.add_node("widen", widen_node)
    g.add_node("explain", explain_node)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "retrieve")
    g.add_edge("retrieve", "score")
    g.add_conditional_edges("score", reflect_edge, {"retry": "widen", "done": "explain"})
    g.add_edge("widen", "retrieve")
    g.add_edge("explain", END)
    return g.compile()

GRAPH = build_graph()

def run_agent(issuer_id: str, top_k: int = 4) -> Dict:
    init = {"issuer_id": issuer_id, "query": "", "candidates": [], "scored": [],
            "passes": 0, "top_k": top_k, "answer": "", "trace": []}
    final = GRAPH.invoke(init)
    return {"issuer_id": issuer_id, "answer": final["answer"], "trace": final["trace"],
            "matches": final["scored"][:top_k], "llm": bool(_get_llm())}