-- Migration: 004_add_phone_column
-- Adds phone number field to users table for phone-based authentication.
-- Login is now done by phone number; registration requires phone + email.
-- The verification code (OTP) is sent to the user's email address.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone VARCHAR(20);

-- Backfill existing rows with a placeholder to satisfy NOT NULL later.
-- In production, existing users should update their phone via profile settings.
UPDATE users SET phone = CONCAT('+00000000000', SUBSTRING(id::text, 1, 9)) WHERE phone IS NULL;

ALTER TABLE users ALTER COLUMN phone SET NOT NULL;

ALTER TABLE users
    ADD CONSTRAINT users_phone_unique UNIQUE (phone);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users (phone);

-- password_hash is no longer required since login is OTP-based.
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
