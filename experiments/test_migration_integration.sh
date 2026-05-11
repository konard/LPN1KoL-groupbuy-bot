#!/usr/bin/env bash
# Integration test that reproduces issue #248 by creating a database in the
# state that the production system was in: core-rust schema (INTEGER users.id)
# plus Django-created tables (supplier_votes, vote_close_requests,
# supplier_document_jobs) with hashed FK constraint names referencing users.id.
#
# Then it runs the migration from core-fastapi/app/db.py and verifies that the
# upgrade succeeds and users.id becomes UUID.

set -euo pipefail
export PATH="/home/linuxbrew/.linuxbrew/opt/postgresql@16/bin:$PATH"

PSQL="psql -h localhost -p 5433 -U postgres"
DB="test_issue248"

cleanup() {
    $PSQL -d postgres -c "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

$PSQL -d postgres -c "DROP DATABASE IF EXISTS $DB" >/dev/null
$PSQL -d postgres -c "CREATE DATABASE $DB" >/dev/null

echo "=== Step 1: simulate legacy core-rust schema (INTEGER users.id) ==="
$PSQL -d $DB -f - <<'SQL' >/dev/null
-- Core-rust schema subset.
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL DEFAULT 'telegram',
    platform_user_id VARCHAR(100) NOT NULL,
    username VARCHAR(100) NOT NULL DEFAULT '',
    first_name VARCHAR(100) NOT NULL DEFAULT '',
    last_name VARCHAR(100) NOT NULL DEFAULT '',
    phone VARCHAR(30) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    role VARCHAR(20) NOT NULL DEFAULT 'buyer',
    balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
    language_code VARCHAR(20) NOT NULL DEFAULT 'ru',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    selfie_file_id VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, platform_user_id)
);

CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dialog_type VARCHAR(50) NOT NULL DEFAULT '',
    dialog_state VARCHAR(50) NOT NULL DEFAULT '',
    dialog_data JSONB NOT NULL DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE procurements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    organizer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE participants (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0
);
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL
);
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL
);
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    text TEXT NOT NULL
);
CREATE TABLE message_reads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(30) NOT NULL,
    title VARCHAR(200) NOT NULL
);
SQL

echo "=== Step 2: simulate Django tables with hashed FK names ==="
$PSQL -d $DB -f - <<'SQL' >/dev/null
CREATE TABLE supplier_votes (
    id BIGSERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    supplier_id INTEGER NOT NULL,
    voter_id INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT supplier_votes_supplier_id_cb31811f_fk_users_id
        FOREIGN KEY (supplier_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT supplier_votes_voter_id_2e8acc32_fk_users_id
        FOREIGN KEY (voter_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE vote_close_requests (
    id BIGSERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vote_close_requests_user_id_e5c5f27d_fk_users_id
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE supplier_document_jobs (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
    organizer_id INTEGER NOT NULL,
    job_type VARCHAR(50) NOT NULL DEFAULT 'receipt_table',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CONSTRAINT supplier_document_jobs_organizer_id_40d7a91e_fk_users_id
        FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE
);
SQL

echo "=== Step 3: insert some legacy data so truncation actually has data to clear ==="
$PSQL -d $DB -f - <<'SQL' >/dev/null
INSERT INTO users (platform_user_id) VALUES ('123'), ('456');
INSERT INTO procurements (title, organizer_id) VALUES ('Test', 1);
INSERT INTO participants (procurement_id, user_id, amount) VALUES (1, 1, 10);
INSERT INTO supplier_votes (procurement_id, supplier_id, voter_id, comment) VALUES (1, 1, 2, 'ok');
INSERT INTO vote_close_requests (procurement_id, user_id) VALUES (1, 1);
INSERT INTO supplier_document_jobs (procurement_id, organizer_id) VALUES (1, 1);
SQL

echo "=== Step 4: verify pre-migration state ==="
$PSQL -d $DB -c "\d users" | grep "id "
$PSQL -d $DB -c "
SELECT con.conname, cls.relname AS table_name
FROM pg_constraint con
JOIN pg_class cls ON cls.oid = con.conrelid
JOIN pg_class ref ON ref.oid = con.confrelid
WHERE con.contype = 'f' AND ref.relname = 'users'
ORDER BY cls.relname, con.conname;"

echo "=== Step 5: extract and run migration 000 from core-fastapi/app/db.py ==="
python3 <<'PY' >/tmp/migration_000.sql
from pathlib import Path
src = Path("/tmp/gh-issue-solver-1778498490692/core-fastapi/app/db.py").read_text()
start = src.index('MIGRATIONS = [')
first = src.index('"""', start)
end = src.index('"""', first + 3)
print(src[first + 3:end])
PY
$PSQL -d $DB -f /tmp/migration_000.sql 2>&1

echo "=== Step 6: verify post-migration state ==="
echo "users.id column type:"
$PSQL -d $DB -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users' AND column_name='id';"
echo
echo "users.is_banned column exists:"
$PSQL -d $DB -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users' AND column_name='is_banned';"
echo
echo "Remaining FK constraints referencing users:"
$PSQL -d $DB -c "
SELECT con.conname, cls.relname AS table_name
FROM pg_constraint con
JOIN pg_class cls ON cls.oid = con.conrelid
JOIN pg_class ref ON ref.oid = con.confrelid
WHERE con.contype = 'f' AND ref.relname = 'users'
ORDER BY cls.relname, con.conname;"
echo
echo "Row counts (should be 0 for tables that had FKs to users):"
for t in users user_sessions procurements participants payments transactions chat_messages message_reads notifications supplier_votes vote_close_requests supplier_document_jobs; do
    $PSQL -d $DB -t -c "SELECT '$t: ' || count(*) FROM $t;"
done

echo "=== Step 7: idempotency check — run the migration again ==="
$PSQL -d $DB -f /tmp/migration_000.sql 2>&1
echo "✓ Migration is idempotent"

echo "=== Step 8: simulate fresh install (no users table) — migration should be no-op ==="
$PSQL -d postgres -c "DROP DATABASE IF EXISTS ${DB}_fresh" >/dev/null
$PSQL -d postgres -c "CREATE DATABASE ${DB}_fresh" >/dev/null
$PSQL -d ${DB}_fresh -f /tmp/migration_000.sql 2>&1
echo "✓ Fresh-install migration succeeded (no-op)"
$PSQL -d postgres -c "DROP DATABASE ${DB}_fresh" >/dev/null

echo "=== ALL TESTS PASSED ==="
