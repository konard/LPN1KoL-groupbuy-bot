-- Migration: 002_add_2fa_and_missing_columns
-- Adds missing 2FA columns and extends the user_role enum to match the entity

-- Extend user_role enum with values missing from 001_create_users.sql
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'organizer';
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'supplier';
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'buyer';

-- Add 2FA columns absent from 001_create_users.sql but present in users.entity.ts
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS two_factor_secret    VARCHAR(255),
    ADD COLUMN IF NOT EXISTS two_factor_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS backup_codes         TEXT,
    ADD COLUMN IF NOT EXISTS two_factor_required  BOOLEAN NOT NULL DEFAULT FALSE;
