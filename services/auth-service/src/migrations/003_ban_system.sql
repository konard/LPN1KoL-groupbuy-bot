-- Migration: 003_ban_system
-- Adds ban tracking to users and creates audit_bans table.

-- Add ban-related columns to users
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS ban_reason TEXT;

-- Separate audit table for ban history (append-only log)
CREATE TABLE IF NOT EXISTS audit_bans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    admin_id        UUID NOT NULL,
    action          VARCHAR(20) NOT NULL CHECK (action IN ('ban', 'unban')),
    reason          TEXT NOT NULL DEFAULT '',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_bans_target ON audit_bans (target_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_bans_admin  ON audit_bans (admin_id);
CREATE INDEX IF NOT EXISTS idx_audit_bans_created ON audit_bans (created_at DESC);

-- Index for fast is_banned lookups (most users are NOT banned)
CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users (is_banned) WHERE is_banned = TRUE;
