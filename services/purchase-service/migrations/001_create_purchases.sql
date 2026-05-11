-- Migration: 001_create_purchases
-- Creates all tables for the purchase and voting domain

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Purchase status type
CREATE TYPE purchase_status AS ENUM (
    'draft',
    'voting',
    'approved',
    'payment_pending',
    'payment_complete',
    'cancelled',
    'completed'
);

-- Voting status type
CREATE TYPE voting_status AS ENUM ('open', 'closed', 'cancelled');

-- ─── Purchases ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    organizer_id        UUID NOT NULL,
    status              purchase_status NOT NULL DEFAULT 'draft',
    min_participants    INT NOT NULL DEFAULT 2,
    max_participants    INT,
    target_amount       NUMERIC(18, 2),
    currency            CHAR(3) NOT NULL DEFAULT 'RUB',
    category            VARCHAR(100),
    deadline_at         TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purchases_organizer ON purchases (organizer_id);
CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases (status);
CREATE INDEX IF NOT EXISTS idx_purchases_created ON purchases (created_at DESC);

-- ─── Voting Sessions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS voting_sessions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id             UUID NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    status                  voting_status NOT NULL DEFAULT 'open',
    closes_at               TIMESTAMPTZ NOT NULL,
    allow_add_candidates    BOOLEAN NOT NULL DEFAULT TRUE,
    allow_change_vote       BOOLEAN NOT NULL DEFAULT TRUE,
    min_votes_to_close      INT NOT NULL DEFAULT 1,
    winner_candidate_id     UUID,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT voting_sessions_purchase_unique UNIQUE (purchase_id)
);

CREATE INDEX IF NOT EXISTS idx_voting_sessions_status ON voting_sessions (status);
CREATE INDEX IF NOT EXISTS idx_voting_sessions_closes_at ON voting_sessions (closes_at)
    WHERE status = 'open';

-- ─── Candidates ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidates (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    voting_session_id   UUID NOT NULL REFERENCES voting_sessions(id) ON DELETE CASCADE,
    supplier_name       VARCHAR(500) NOT NULL,
    description         VARCHAR(1000),
    price_per_unit      NUMERIC(18, 2),
    unit                VARCHAR(50),
    supplier_url        VARCHAR(2048),
    proposed_by         UUID NOT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidates (voting_session_id);

-- ─── Votes ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS votes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    voting_session_id   UUID NOT NULL REFERENCES voting_sessions(id) ON DELETE CASCADE,
    candidate_id        UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL,
    comment             TEXT,
    changed_count       INT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT votes_user_session_unique UNIQUE (voting_session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_votes_session ON votes (voting_session_id);
CREATE INDEX IF NOT EXISTS idx_votes_candidate ON votes (candidate_id);
CREATE INDEX IF NOT EXISTS idx_votes_user ON votes (user_id);

-- Add FK from voting_sessions to candidates (winner)
ALTER TABLE voting_sessions
    ADD CONSTRAINT fk_winner_candidate
    FOREIGN KEY (winner_candidate_id) REFERENCES candidates(id)
    DEFERRABLE INITIALLY DEFERRED;

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER purchases_updated_at
    BEFORE UPDATE ON purchases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER voting_sessions_updated_at
    BEFORE UPDATE ON voting_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER votes_updated_at
    BEFORE UPDATE ON votes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
