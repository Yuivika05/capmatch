"""kaggle_loader.py — the "refinery" that turns raw Kaggle data into clean records.

Real Kaggle data is messy (funding like "$1 million" / "$10M" / "150k", website
URLs instead of sectors, mixed stage names). This module reads the two raw files:

    investors_data.json  (253 real investors)  -> our INVESTOR schema
    founders_data.json   (500 real startups)   -> our ISSUER schema

...and cleans + maps every field onto the tidy shape the rest of the app expects.
Run it directly to WRITE the cleaned files:  python kaggle_loader.py
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

_DIR = os.path.dirname(__file__)

# ---------------------------------------------------------------- money parsing
def parse_amount(raw) -> Optional[int]:
    """Turn messy funding text into an integer USD, or None if unparseable.

    Handles: "$1 million", "$10M", "$150k", "$500,000", "20000000",
             "$1766148420.10" (junk -> capped), "", None, "string".
    """
    if raw is None:
        return None
    s = str(raw).strip().lower().replace(",", "").replace("$", "").strip()
    if not s or s in {"string", "n/a", "none"}:
        return None

    mult = 1
    if s.endswith("m") or "million" in s:
        mult = 1_000_000
        s = s.replace("million", "").replace("m", "").strip()
    elif s.endswith("b") or "billion" in s:
        mult = 1_000_000_000
        s = s.replace("billion", "").replace("b", "").strip()
    elif s.endswith("k") or "thousand" in s:
        mult = 1_000
        s = s.replace("thousand", "").replace("k", "").strip()

    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return None
    try:
        val = float(m.group()) * mult
    except ValueError:
        return None

    # sanity clamp: real rounds are ~$10k .. $10B. Junk like 1.7e9 "seed" -> clamp.
    if val < 1_000:
        return None
    if val > 10_000_000_000:
        val = 10_000_000_000
    return int(val)


# ---------------------------------------------------------------- stage mapping
_STAGE_MAP = {
    "pre-seed": "pre_seed", "preseed": "pre_seed",
    "seed": "seed", "seed funding": "seed", "seed round": "seed",
    "post-seed": "seed",
    "series a": "series_a", "round a": "series_a", "series a funding": "series_a",
    "series b": "series_b",
    "series c": "growth", "series d": "growth", "growth": "growth",
}


def norm_stage(raw: str) -> Optional[str]:
    if not raw:
        return None
    return _STAGE_MAP.get(str(raw).strip().lower())


def norm_stages(raw_list) -> List[str]:
    out = []
    for r in (raw_list or []):
        s = norm_stage(r)
        if s and s not in out:
            out.append(s)
    return out or ["seed"]


# ------------------------------------------------------------- geography mapping
def geo_from_location(loc: str) -> str:
    """Map a free-text location to a coarse region code used by the matcher."""
    l = (loc or "").lower()
    if any(x in l for x in ["india", "bangalore", "bengaluru", "mumbai", "delhi"]):
        return "IN"
    if any(x in l for x in ["singapore", "jakarta", "vietnam", "indonesia"]):
        return "SEA"
    if any(x in l for x in ["london", "uk", "berlin", "germany", "paris",
                            "france", "amsterdam", "europe", "stockholm"]):
        return "EU"
    if any(x in l for x in ["san francisco", "new york", "california", "boston",
                            "palo alto", "los angeles", "usa", "united states",
                            "seattle", "austin", "philadelphia"]):
        return "US"
    return "US"  # default bucket


# --------------------------------------------------------------- sector mapping
def norm_sector(raw: str) -> str:
    """Map a domain/tag to one of our simple sector buckets."""
    l = (raw or "").lower()
    table = [
        (["fintech", "payment", "pay", "finance", "financ", "bank", "capital",
          "invoice", "lending", "loan", "credit", "wallet", "insur"], "fintech"),
        (["health", "biotech", "medical", "medi", "pharma", "care", "clinic",
          "therap", "wellness", "fitbit", "watch", "dental", "bio"], "healthcare"),
        (["clean", "climate", "energy", "solar", "sustain", "power", "grid",
          "renewable", "carbon", "green"], "cleantech"),
        (["saas", "software", "enterprise", "smb software", "b2b", "cloud",
          "platform", "app", "data", "analytics", "dev", "api"], "saas"),
        (["ai", "ml", "machine learning", "robot", "agentic", "gpt", "llm",
          "neural", "intelligence"], "ai"),
        (["marketplace", "commerce", "retail", "ecommerce", "shop", "store",
          "social commerce", "buy", "sell", "market"], "marketplace"),
        (["ag", "agtech", "food", "farm", "crop", "grocery"], "agtech"),
        (["mobility", "auto", "transport", "logistics", "delivery", "fleet",
          "ride", "travel", "aalto"], "mobility"),
        (["game", "media", "content", "advertising", "social", "video",
          "music", "stream", "creator"], "media"),
        (["hardware", "material", "manufactur", "device", "chip", "sensor",
          "iot"], "hardware"),
    ]
    for keys, bucket in table:
        if any(k in l for k in keys):
            return bucket
    return "other"


# --------------------------------------------------------------- INVESTORS load
def load_raw_investors(limit: Optional[int] = None) -> List[Dict]:
    with open(os.path.join(_DIR, "investors_data.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return raw[:limit] if limit else raw


def clean_investor(r: Dict, idx: int) -> Dict:
    tags = r.get("tags") or []
    domains = [r.get("primary_domain", "")] + (r.get("secondary_domains") or [])
    sectors = []
    for d in domains + tags:
        s = norm_sector(d)
        if s != "other" and s not in sectors:
            sectors.append(s)
    if not sectors:
        sectors = ["other"]

    thesis = (r.get("investment_thesis") or "").strip()
    if not thesis:
        bio = (r.get("short_bio") or "").strip()
        thesis = bio or f"{r.get('firm_name') or r.get('name')} invests in " \
                        f"{', '.join(sectors)}."

    geo = geo_from_location(r.get("location", ""))
    stages = norm_stages(r.get("investment_stage_pref"))

    return {
        "id": f"inv-k{r.get('id', idx)}",
        "name": r.get("firm_name") or r.get("name") or f"Investor {idx}",
        "sectors": sectors,
        "stages": stages,
        "instruments": ["equity"],          # dataset has no instrument -> default
        "ticket_min_usd": 500_000,          # sensible defaults (dataset lacks these)
        "ticket_max_usd": 25_000_000,
        "geographies": [geo],
        "esg_required": any("impact" in str(t).lower() for t in tags),
        "thesis": thesis,
    }


# ----------------------------------------------------------------- ISSUERS load
def load_raw_founders(limit: Optional[int] = None) -> List[Dict]:
    with open(os.path.join(_DIR, "founders_data.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return raw[:limit] if limit else raw


def clean_issuer(r: Dict, idx: int) -> Optional[Dict]:
    pf = r.get("past_funding") or {}
    amount = parse_amount(pf.get("amount"))
    if amount is None:
        amount = 2_000_000                  # default ask if funding unparseable

    stage = norm_stage(pf.get("round")) or "seed"
    name = r.get("company") or r.get("name") or f"Startup {idx}"
    # Infer sector from ALL available clues: domain URL, company name,
    # competitors, and umbrella companies (more text = better classification).
    clues = " ".join([
        str(r.get("domain") or ""),
        str(name),
        " ".join(r.get("competitors") or []),
        " ".join(r.get("umbrella_companies") or []),
    ])
    sector = norm_sector(clues)

    competitors = r.get("competitors") or []
    comp_txt = f" Competes with {', '.join(competitors)}." if competitors else ""
    summary = (f"{name} operates in {sector}. Raised a {stage.replace('_',' ')} "
               f"round of about ${amount:,.0f}.{comp_txt}")

    return {
        "id": f"iss-k{r.get('id', idx)}",
        "name": name,
        "sector": sector,
        "stage": stage,
        "instrument": "equity",
        "ask_amount_usd": amount,
        "geography": "US",                  # founders file has no location -> default
        "esg_focus": sector == "cleantech",
        "summary": summary,
    }


# -------------------------------------------------------------------- build all
def build(limit_investors: int = 100, limit_issuers: int = 100):
    """Read raw files, clean, and WRITE investors.json + issuers.json."""
    raw_inv = load_raw_investors(limit_investors)
    investors = [clean_investor(r, i) for i, r in enumerate(raw_inv)]

    raw_fnd = load_raw_founders(limit_issuers)
    issuers = [c for i, r in enumerate(raw_fnd) if (c := clean_issuer(r, i))]

    with open(os.path.join(_DIR, "investors.json"), "w", encoding="utf-8") as f:
        json.dump(investors, f, indent=2)
    with open(os.path.join(_DIR, "issuers.json"), "w", encoding="utf-8") as f:
        json.dump(issuers, f, indent=2)

    return investors, issuers


if __name__ == "__main__":
    inv, iss = build(limit_investors=100, limit_issuers=100)
    print(f"Wrote {len(inv)} investors -> investors.json")
    print(f"Wrote {len(iss)} issuers   -> issuers.json")
    print()
    print("Sample investor:", json.dumps(inv[0], indent=2)[:600])
    print()
    print("Sample issuer:  ", json.dumps(iss[0], indent=2)[:600])
