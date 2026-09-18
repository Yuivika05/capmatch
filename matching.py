# matching.py — the "AI agent" brain that scores and ranks investors

# How important each factor is. All add up to 1.0 (100%).
WEIGHTS = {
    "sector": 0.25,      # does the industry match?
    "ticket": 0.20,      # is the money amount in their range?
    "stage": 0.15,       # seed / series A / growth?
    "instrument": 0.15,  # equity / debt / convertible?
    "geography": 0.10,   # same region?
    "thesis": 0.10,      # text similarity of goals
    "esg": 0.05,         # green/ESG rule
}


def score_pair(issuer, inv):
    """Give one investor a score (0 to 1) for one issuer, with reasons."""
    factors = []

    # 1) Sector match
    hit = issuer["sector"] in inv["sectors"]
    factors.append(("sector", 1.0 if hit else 0.0,
                    f"Sector '{issuer['sector']}' {'is' if hit else 'not'} in {inv['sectors']}"))

    # 2) Stage match
    hit = issuer["stage"] in inv["stages"]
    factors.append(("stage", 1.0 if hit else 0.0,
                    f"Stage '{issuer['stage']}' {'matches' if hit else 'outside'} {inv['stages']}"))

    # 3) Instrument match (equity/debt/etc.)
    hit = issuer["instrument"] in inv["instruments"]
    factors.append(("instrument", 1.0 if hit else 0.0,
                    f"Instrument '{issuer['instrument']}' {'accepted' if hit else 'not offered'}"))

    # 4) Ticket (money amount) inside their range?
    ask = issuer["ask_amount_usd"]
    inside = inv["ticket_min_usd"] <= ask <= inv["ticket_max_usd"]
    factors.append(("ticket", 1.0 if inside else 0.0,
                    f"Ask ${ask:,.0f} {'within' if inside else 'outside'} "
                    f"${inv['ticket_min_usd']:,.0f}-${inv['ticket_max_usd']:,.0f}"))

    # 5) Geography
    hit = issuer["geography"] in inv["geographies"]
    factors.append(("geography", 1.0 if hit else 0.0,
                    f"Geography '{issuer['geography']}' {'covered' if hit else 'not covered'}"))

    # 6) ESG rule
    if not inv["esg_required"]:
        esg_score, esg_note = 1.0, "No ESG requirement"
    elif issuer["esg_focus"]:
        esg_score, esg_note = 1.0, "ESG required and issuer is ESG-focused"
    else:
        esg_score, esg_note = 0.0, "ESG required but issuer is NOT ESG-focused"
    factors.append(("esg", esg_score, esg_note))

    # 7) Thesis text similarity (simple word overlap)
    sim = text_similarity(issuer["summary"], inv["thesis"])
    factors.append(("thesis", sim, f"Text overlap of goals = {sim:.2f}"))

    # Add up: each factor score x its weight
    overall = sum(WEIGHTS[name] * score for name, score, _ in factors)

    return {
        "investor_id": inv["id"],
        "investor_name": inv["name"],
        "score": round(overall, 3),
        "factors": [{"name": n, "score": round(s, 2), "detail": d} for n, s, d in factors],
    }


def text_similarity(a, b):
    """Very simple similarity: how many words two texts share."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    common = wa & wb
    return round(len(common) / max(len(wa), len(wb)), 3)


def rank_matches(issuer, investors, top_k=5):
    """Score ALL investors for one issuer, then sort best-first."""
    scored = [score_pair(issuer, inv) for inv in investors]
    scored.sort(key=lambda x: x["score"], reverse=True)  # highest first
    return scored[:top_k]