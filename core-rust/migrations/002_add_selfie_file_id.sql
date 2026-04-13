-- Add selfie_file_id column to users table if it does not already exist.
-- This matches the Django migration 0003_user_selfie_file_id and ensures
-- the Rust core can read/write the column without NOT NULL violations.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'selfie_file_id'
    ) THEN
        ALTER TABLE users ADD COLUMN selfie_file_id VARCHAR(255) NOT NULL DEFAULT '';
    END IF;
END
$$;
