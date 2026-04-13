# Migration: add selfie_file_id field to User.
# The selfie (a Telegram file_id) is collected during registration for identity
# verification purposes.  It is accessible only to admins and is never returned
# in regular API responses.
#
# This migration is idempotent: it checks whether the column already exists
# before trying to add it.  The Rust core service creates the users table with
# selfie_file_id included in its initial SQL migration (001_initial.sql), so on
# deployments where the Rust container ran first the column will already be
# present.  Without the IF NOT EXISTS guard Django would raise:
#   psycopg2.errors.DuplicateColumn: column "selfie_file_id" of relation
#   "users" already exists
# which causes the django-admin container to crash-loop (issue #192).

from django.db import connection, migrations


def add_selfie_file_id_if_missing(apps, schema_editor):
    """Add selfie_file_id column only when it does not already exist.

    PostgreSQL supports the PL/pgSQL DO $$ … $$ block which lets us perform
    the existence check inside a single atomic statement.  SQLite (used by the
    test suite) does not support that syntax, so we fall back to checking the
    column list via the Python DB-API before issuing the ALTER TABLE.
    """
    if connection.vendor == 'postgresql':
        schema_editor.execute("""
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
""")
    else:
        # SQLite / other backends: check via cursor description
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
        if 'selfie_file_id' not in columns:
            schema_editor.execute(
                "ALTER TABLE users ADD COLUMN selfie_file_id VARCHAR(255) NOT NULL DEFAULT ''"
            )


def drop_selfie_file_id(apps, schema_editor):
    """Reverse: remove the selfie_file_id column."""
    if connection.vendor == 'postgresql':
        schema_editor.execute(
            "ALTER TABLE users DROP COLUMN IF EXISTS selfie_file_id;"
        )
    else:
        # SQLite does not support DROP COLUMN in older versions; skip silently.
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_first_name_optional'),
    ]

    operations = [
        migrations.RunPython(
            add_selfie_file_id_if_missing,
            reverse_code=drop_selfie_file_id,
        ),
    ]
