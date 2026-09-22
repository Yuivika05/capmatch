# matching.py — the hybrid scoring "brain" that ranks investors for an issuer.
#
# HYBRID FORMULA (exactly as required by the project brief, part 2):
#   40%  semantic   -> AI meaning-match (embeddings) between issuer & investor
#   20%  sector     -> does the industry match?
#   15%  ticket     -> is the money amount in their range? (investment range)
#   10%  geography   -> same region?
#   10%  stage      -> seed / series A / growth? (funding stage)
#    5%  other      -> instrument + ESG rules
#  ----
#  100%
#
# The 40% "semantic" score is the real AI part: it compares MEANING, not words.
# It uses the embeddings module (Sentence-Transformer + FAISS). If that model
# isn't installed, it quietly falls back to a simple word-overlap score so the
# app still runs everywhere.

from embeddings import _cosine_bow

try:
    # Real meaning-based similarity (0..1) using the embedding model.
    from embeddings import embed
    import numpy as np
    _HAS_EMBED = True
except Exception:
    _HAS_EMBED = False


# How important each factor is. All add up to 1.0 (100%).
WEIGHTS = {
    "semantic": 0.40,    # AI meaning-match (embeddings)  <-- the star
    "sector": 0.20,      # does the industry match?
    "ticket": 0.15,      # is the money amount in their range?
    "geography": 0.10,   # same region?
    "stage": 0.10,       # seed / series A / growth?
    "other": 0.05,       # instrument + ESG rules bundled
}


def semantic_similarity(a: str, b: str) -> float:
    """Meaning-based similarity (0..1) between two texts.

    Uses real sentence embeddings when available (cosine of the two vectors),
    otherwise a simple bag-of-words cosine so the app never breaks.
    """
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    if _HAS_EMBED:
        try:
            vecs = embed([a, b])
            if vecs is not None:
                # embeddings are normalized -> dot product == cosine similarity
                sim = float(np.dot(vecs[0], vecs[1]))
                # cosine is -1..1; clamp to 0..1 for a clean score
                return round(max(0.0, min(1.0, sim)), 3)
        except Exception:
            pass
    # fallback: word-overlap cosine
    return round(_cosine_bow(a, b), 3)


def score_pair(issuer, inv):
    """Give one investor a hybrid score (0..1) for one issuer, with reasons."""
    factors = []

    # --- 40% SEMANTIC: AI meaning-match between issuer summary & investor thesis
    sem = semantic_similarity(issuer.get("summary", ""), inv.get("thesis", ""))
    factors.append(("semantic", sem,
                    f"AI meaning-match of issuer summary vs investor thesis = {sem:.2f}"))

    # --- 20% SECTOR
    hit = issuer["sector"] in inv["sectors"]
    factors.append(("sector", 1.0 if hit else 0.0,
                    f"Sector '{issuer['sector']}' {'is' if hit else 'not'} in {inv['sectors']}"))

    # --- 15% TICKET (investment range)
    ask = issuer["ask_amount_usd"]
    inside = inv["ticket_min_usd"] <= ask <= inv["ticket_max_usd"]
    factors.append(("ticket", 1.0 if inside else 0.0,
                    f"Ask ${ask:,.0f} {'within' if inside else 'outside'} "
                    f"${inv['ticket_min_usd']:,.0f}-${inv['ticket_max_usd']:,.0f}"))

    # --- 10% GEOGRAPHY
    hit = issuer["geography"] in inv["geographies"]
    factors.append(("geography", 1.0 if hit else 0.0,
                    f"Geography '{issuer['geography']}' {'covered' if hit else 'not covered'}"))

    # --- 10% STAGE (funding stage)
    hit = issuer["stage"] in inv["stages"]
    factors.append(("stage", 1.0 if hit else 0.0,
                    f"Stage '{issuer['stage']}' {'matches' if hit else 'outside'} {inv['stages']}"))

    # --- 5% OTHER: instrument fit + ESG rule, averaged into one small factor
    instrument_ok = 1.0 if issuer["instrument"] in inv["instruments"] else 0.0
    if not inv["esg_required"]:
        esg_ok, esg_note = 1.0, "no ESG requirement"
    elif issuer["esg_focus"]:
        esg_ok, esg_note = 1.0, "ESG required & issuer is ESG-focused"
    else:
        esg_ok, esg_note = 0.0, "ESG required but issuer is NOT ESG-focused"
    other = round((instrument_ok + esg_ok) / 2, 3)
    factors.append(("other", other,
                    f"Instrument '{issuer['instrument']}' "
                    f"{'accepted' if instrument_ok else 'not offered'}; {esg_note}"))

    overall = sum(WEIGHTS[name] * score for name, score, _ in factors)

    return {
        "investor_id": inv["id"],
        "investor_name": inv["name"],
        "score": round(overall, 3),
        "factors": [{"name": n, "score": round(s, 2), "detail": d} for n, s, d in factors],
    }


def rank_matches(issuer, investors, top_k=5):
    """Score ALL investors for one issuer, then sort best-first."""
    scored = [score_pair(issuer, inv) for inv in investors]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
