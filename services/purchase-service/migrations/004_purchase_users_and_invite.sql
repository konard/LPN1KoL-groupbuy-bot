-- Migration: 004_purchase_users_and_invite
-- Creates the purchase_users table (was missing from previous migrations) and adds
-- the 'participant' role so that regular users can be invited to join a purchase.

-- ── Create role enum (idempotent via DO block) ────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchase_user_role') THEN
        CREATE TYPE purchase_user_role AS ENUM ('owner', 'editor', 'participant');
    ELSE
        -- Add 'participant' if it doesn't exist yet (safe to run multiple times)
        BEGIN
            ALTER TYPE purchase_user_role ADD VALUE IF NOT EXISTS 'participant';
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END
$$;

-- ── Purchases status: add 'active' if not already present ────────────────────
-- (The TypeORM entity uses PurchaseStatus.ACTIVE but migration 001 may have omitted it)
DO $$
BEGIN
    BEGIN
        ALTER TYPE purchase_status ADD VALUE IF NOT EXISTS 'active';
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;
END
$$;

-- ── purchase_users table ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchase_users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_id UUID NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL,
    role        purchase_user_role NOT NULL DEFAULT 'editor',
    invited_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT purchase_users_purchase_user_unique UNIQUE (purchase_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_purchase_users_purchase ON purchase_users (purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_users_user ON purchase_users (user_id);
