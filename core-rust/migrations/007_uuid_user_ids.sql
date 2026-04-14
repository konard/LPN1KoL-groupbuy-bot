-- Migration 007: Change user IDs from integer (SERIAL) to UUID
--
-- Root cause: The API routes expected i32 integer IDs for users, but the
-- frontend sends UUID strings (e.g. "25afb8e3-9e8d-4467-ae76-62507610c6f6"),
-- causing "can not parse UUID to i32" errors on all user-related endpoints.
--
-- This migration:
--   1. Drops all FK constraints that reference users(id)
--   2. Drops and re-creates the users.id column as UUID DEFAULT gen_random_uuid()
--   3. Drops and re-creates all FK columns referencing users to UUID
--   4. Restores all FK constraints
--
-- IMPORTANT: This migration cannot preserve existing integer user IDs.
-- All existing user rows will receive new random UUIDs. Related FK rows
-- (sessions, procurements, participants, payments, transactions,
-- chat_messages, message_reads, notifications, supplier_document_jobs)
-- will be truncated first to satisfy the FK constraint change.

-- Requires pgcrypto for gen_random_uuid() on older PostgreSQL.
-- On PostgreSQL 13+ gen_random_uuid() is built-in (no extension needed).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------
-- Step 1: Truncate all child tables (FK deps on users) to allow column type change.
-- This avoids needing to convert existing integer FK values to UUIDs.
-- -----------------------------------------------------------------------
TRUNCATE TABLE supplier_document_jobs CASCADE;
TRUNCATE TABLE notifications CASCADE;
TRUNCATE TABLE message_reads CASCADE;
TRUNCATE TABLE transactions CASCADE;
TRUNCATE TABLE payments CASCADE;
TRUNCATE TABLE participants CASCADE;
TRUNCATE TABLE procurements CASCADE;
TRUNCATE TABLE user_sessions CASCADE;
TRUNCATE TABLE users CASCADE;

-- -----------------------------------------------------------------------
-- Step 2: Drop FK constraints referencing users(id)
-- -----------------------------------------------------------------------
ALTER TABLE user_sessions        DROP CONSTRAINT IF EXISTS user_sessions_user_id_fkey;
ALTER TABLE procurements         DROP CONSTRAINT IF EXISTS procurements_organizer_id_fkey;
ALTER TABLE procurements         DROP CONSTRAINT IF EXISTS procurements_supplier_id_fkey;
ALTER TABLE participants         DROP CONSTRAINT IF EXISTS participants_user_id_fkey;
ALTER TABLE payments             DROP CONSTRAINT IF EXISTS payments_user_id_fkey;
ALTER TABLE transactions         DROP CONSTRAINT IF EXISTS transactions_user_id_fkey;
ALTER TABLE chat_messages        DROP CONSTRAINT IF EXISTS chat_messages_user_id_fkey;
ALTER TABLE message_reads        DROP CONSTRAINT IF EXISTS message_reads_user_id_fkey;
ALTER TABLE notifications        DROP CONSTRAINT IF EXISTS notifications_user_id_fkey;
ALTER TABLE supplier_document_jobs DROP CONSTRAINT IF EXISTS supplier_document_jobs_organizer_id_fkey;

-- -----------------------------------------------------------------------
-- Step 3: Change users.id to UUID
-- -----------------------------------------------------------------------
ALTER TABLE users DROP COLUMN id;
ALTER TABLE users ADD COLUMN id UUID PRIMARY KEY DEFAULT gen_random_uuid();

-- -----------------------------------------------------------------------
-- Step 4: Change all child FK columns from INTEGER to UUID
-- -----------------------------------------------------------------------
ALTER TABLE user_sessions   ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE procurements    ALTER COLUMN organizer_id TYPE UUID USING NULL;
ALTER TABLE procurements    ALTER COLUMN supplier_id  TYPE UUID USING NULL;
ALTER TABLE participants    ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE payments        ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE transactions    ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE chat_messages   ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE message_reads   ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE notifications   ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE supplier_document_jobs ALTER COLUMN organizer_id TYPE UUID USING NULL;

-- -----------------------------------------------------------------------
-- Step 5: Restore NOT NULL constraints where they existed originally
-- -----------------------------------------------------------------------
ALTER TABLE user_sessions   ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE procurements    ALTER COLUMN organizer_id SET NOT NULL;
ALTER TABLE participants    ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE payments        ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE transactions    ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE message_reads   ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE notifications   ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE supplier_document_jobs ALTER COLUMN organizer_id SET NOT NULL;

-- -----------------------------------------------------------------------
-- Step 6: Restore FK constraints
-- -----------------------------------------------------------------------
ALTER TABLE user_sessions   ADD CONSTRAINT user_sessions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE procurements    ADD CONSTRAINT procurements_organizer_id_fkey
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE procurements    ADD CONSTRAINT procurements_supplier_id_fkey
    FOREIGN KEY (supplier_id)  REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE participants    ADD CONSTRAINT participants_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE payments        ADD CONSTRAINT payments_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE transactions    ADD CONSTRAINT transactions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE chat_messages   ADD CONSTRAINT chat_messages_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE message_reads   ADD CONSTRAINT message_reads_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE notifications   ADD CONSTRAINT notifications_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE supplier_document_jobs ADD CONSTRAINT supplier_document_jobs_organizer_id_fkey
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE;
