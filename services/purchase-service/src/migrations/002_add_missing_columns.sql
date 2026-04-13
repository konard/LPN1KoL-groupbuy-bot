-- Migration: 002_add_missing_columns
-- Adds columns that exist in TypeORM entities but were missing from 001_create_purchases.sql

-- ── Purchases: commission & escrow columns ───────────────────────────────────
ALTER TABLE purchases
    ADD COLUMN IF NOT EXISTS commission_percent NUMERIC(4,1) NOT NULL DEFAULT 0
        CONSTRAINT chk_commission_range CHECK (commission_percent >= 0 AND commission_percent <= 10);

ALTER TABLE purchases
    ADD COLUMN IF NOT EXISTS escrow_required BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE purchases
    ADD COLUMN IF NOT EXISTS escrow_threshold BIGINT NOT NULL DEFAULT 1000000;

-- ── Voting Sessions: duration, ends_at, tie_breaker, candidate_deadline ──────
ALTER TABLE voting_sessions
    ADD COLUMN IF NOT EXISTS voting_duration INT NOT NULL DEFAULT 24;

ALTER TABLE voting_sessions
    ADD COLUMN IF NOT EXISTS voting_ends_at TIMESTAMPTZ;

ALTER TABLE voting_sessions
    ADD COLUMN IF NOT EXISTS tie_breaker UUID;

ALTER TABLE voting_sessions
    ADD COLUMN IF NOT EXISTS candidate_deadline TIMESTAMPTZ;

-- ── Indexes for new columns ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_purchases_commission
    ON purchases (commission_percent) WHERE commission_percent > 0;

CREATE INDEX IF NOT EXISTS idx_voting_sessions_ends_at
    ON voting_sessions (voting_ends_at) WHERE status = 'open';
