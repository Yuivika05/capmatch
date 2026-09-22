-- ============================================================================
--  CapMatch — PostgreSQL schema (run once in Supabase → SQL Editor → New query)
-- ============================================================================
--  A normalized schema for the issuer <-> investor matching platform.
--  5 tables: issuers, investors, investment_preferences, matches, transactions.
--  Uses foreign keys (relationships) + indexes (fast lookups).
--  The existing `users` table (auth) stays as-is; these are the domain tables.
-- ============================================================================

-- ---------- ISSUERS: companies seeking capital -------------------------------
create table if not exists issuers (
    id              text primary key,
    name            text not null,
    sector          text,
    stage           text,
    instrument      text default 'equity',
    ask_amount_usd  bigint,
    geography       text,
    esg_focus       boolean default false,
    summary         text,
    owner_username  text references users(username),   -- which user owns this issuer
    created_at      timestamptz default now()
);

-- ---------- INVESTORS: parties providing capital -----------------------------
create table if not exists investors (
    id              text primary key,
    name            text not null,
    instruments     text[] default '{equity}',
    ticket_min_usd  bigint,
    ticket_max_usd  bigint,
    esg_required    boolean default false,
    thesis          text,
    owner_username  text references users(username),   -- which user owns this investor
    created_at      timestamptz default now()
);

-- ---------- INVESTMENT_PREFERENCES: sectors/stages/geos an investor wants -----
--  A separate table (one investor -> many preference rows) = "normalized".
create table if not exists investment_preferences (
    id              bigserial primary key,
    investor_id     text references investors(id) on delete cascade,
    pref_type       text not null,      -- 'sector' | 'stage' | 'geography'
    pref_value      text not null
);

-- ---------- MATCHES: a scored issuer<->investor pairing ----------------------
create table if not exists matches (
    id              bigserial primary key,
    issuer_id       text references issuers(id) on delete cascade,
    investor_id     text references investors(id) on delete cascade,
    score           numeric(5,4),       -- 0.0000 .. 1.0000
    explanation     text,               -- LLM natural-language justification
    factors         jsonb,              -- per-factor breakdown (explainable AI)
    created_at      timestamptz default now()
);

-- ---------- TRANSACTIONS: a funding event between the two parties -------------
create table if not exists transactions (
    id              bigserial primary key,
    match_id        bigint references matches(id) on delete set null,
    issuer_id       text references issuers(id),
    investor_id     text references investors(id),
    amount_usd      bigint,
    status          text default 'proposed',  -- proposed | committed | closed
    created_at      timestamptz default now()
);

-- ---------- INDEXES: make the common lookups fast ----------------------------
create index if not exists idx_issuers_sector    on issuers(sector);
create index if not exists idx_investors_thesis  on investors using gin (to_tsvector('english', coalesce(thesis,'')));
create index if not exists idx_prefs_investor    on investment_preferences(investor_id);
create index if not exists idx_matches_issuer    on matches(issuer_id);
create index if not exists idx_matches_investor  on matches(investor_id);
create index if not exists idx_tx_status         on transactions(status);
