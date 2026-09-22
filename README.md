CapMatch — Agentic AI for Issuer ↔ Investor Matching
CapMatch connects companies seeking capital with the right investors using
an agentic AI pipeline. Instead of keyword filtering, an autonomous agent reads
each company's profile, understands its meaning with NLP embeddings, scores
investors with a hybrid formula, and returns an explainable, ranked recommendation
in plain English.

Features
🧠 Semantic matching — Sentence-Transformers + FAISS vector search
⚖️ Hybrid scoring — 40% semantic, 20% sector, 15% investment range, 10% geography, 10% stage, 5% other
🤖 Agentic AI (LangGraph) — the agent autonomously searches, scores, reflects, and explains
📊 Explainable AI — per-factor breakdown plus an LLM-written justification
🔀 Event pipeline — new investors flow through a Kafka-style topic → embedding service → vector DB
🔐 JWT auth + role-based access — issuer, investor, admin get different permissions
🗄️ PostgreSQL (Supabase) — normalized schema for issuers, investors, matches, transactions
Tech Stack
Python · LangChain · LangGraph · Sentence-Transformers · FAISS · Groq LLM ·
FastAPI · JWT · Supabase (PostgreSQL)

Run it
Bash

pip install fastapi "uvicorn[standard]" langgraph langchain-core langchain-groq \
            sentence-transformers faiss-cpu supabase bcrypt "python-jose[cryptography]" python-multipart
python -m uvicorn main:app --reload
Then open http://127.0.0.1:8000/ (dashboard) or /docs (API).

Built by Yuvika.
