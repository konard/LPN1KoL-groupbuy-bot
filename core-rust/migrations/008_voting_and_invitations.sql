-- Supplier votes for procurement voting system
CREATE TABLE IF NOT EXISTS procurement_votes (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    voter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (procurement_id, voter_id)
);

CREATE INDEX IF NOT EXISTS idx_procurement_votes_procurement ON procurement_votes(procurement_id);
CREATE INDEX IF NOT EXISTS idx_procurement_votes_voter ON procurement_votes(voter_id);

-- Vote close confirmations (consensus to end voting round)
CREATE TABLE IF NOT EXISTS vote_close_confirmations (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (procurement_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_vote_close_procurement ON vote_close_confirmations(procurement_id);

-- Procurement invitations by organizer via email
CREATE TABLE IF NOT EXISTS procurement_invitations (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    organizer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(254) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (procurement_id, email)
);

CREATE INDEX IF NOT EXISTS idx_procurement_invitations_procurement ON procurement_invitations(procurement_id);
