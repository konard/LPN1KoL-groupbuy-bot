"""
Tests for issue #190 fixes:

Two errors were observed in the production logs for the Rust core API:

  1. "value too long for type character varying(20)"
     – Caused by the phone column (VARCHAR 20) being too narrow for some
       international phone numbers, and by language_code (VARCHAR 10) being
       too narrow for some BCP-47 locale tags sent by Telegram.
     – Fixed by:
         a. Widening phone to VARCHAR(30) and language_code to VARCHAR(20)
            in 001_initial.sql (fresh installs).
         b. Adding 003_widen_phone_and_language_code.sql (existing databases).
         c. Running migration 003 from db/mod.rs.
         d. Adding truncate_str() helper in the Rust handler as a safety net.

  2. "null value in column 'selfie_file_id' of relation 'users' violates
     not-null constraint"
     – The CREATE USER handler did not include selfie_file_id in the INSERT,
       and some existing databases lacked the column (fixed earlier in #188).
     – Fixed by adding selfie_file_id to the CreateUser struct and including
       it in the INSERT statement.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath):
    """Read a file relative to the repo root."""
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Fix 1a — 001_initial.sql uses wider column types
# ===========================================================================


class TestInitialMigrationWiderColumns:
    """
    The initial migration must use VARCHAR(30) for phone and VARCHAR(20) for
    language_code so that fresh installs are not vulnerable to the too-long
    error from the start.
    """

    def test_phone_column_is_varchar30_or_wider(self):
        sql = read_file("core-rust/migrations/001_initial.sql")
        # Extract the phone column definition
        match = re.search(r"phone\s+VARCHAR\((\d+)\)", sql, re.IGNORECASE)
        assert match is not None, "phone column must be VARCHAR(...) in 001_initial.sql"
        size = int(match.group(1))
        assert size >= 30, (
            f"phone column size {size} must be at least 30 to accommodate "
            "international phone numbers longer than 20 characters"
        )

    def test_language_code_column_is_varchar20_or_wider(self):
        sql = read_file("core-rust/migrations/001_initial.sql")
        match = re.search(r"language_code\s+VARCHAR\((\d+)\)", sql, re.IGNORECASE)
        assert match is not None, "language_code column must be VARCHAR(...) in 001_initial.sql"
        size = int(match.group(1))
        assert size >= 20, (
            f"language_code column size {size} must be at least 20 to accommodate "
            "long BCP-47 locale tags (e.g. zh-hans-cn)"
        )


# ===========================================================================
# Fix 1b — migration 003 widens phone and language_code on existing databases
# ===========================================================================


class TestMigration003Exists:
    """
    A migration file must exist that widens phone and language_code for
    databases that were created before this fix.
    """

    def test_migration_003_file_exists(self):
        path = os.path.join(ROOT, "core-rust/migrations/003_widen_phone_and_language_code.sql")
        assert os.path.isfile(path), (
            "core-rust/migrations/003_widen_phone_and_language_code.sql must exist"
        )

    def test_migration_003_widens_phone(self):
        sql = read_file("core-rust/migrations/003_widen_phone_and_language_code.sql")
        assert "phone" in sql, "migration 003 must ALTER the phone column"
        assert "VARCHAR" in sql.upper(), "migration 003 must use VARCHAR for phone"

    def test_migration_003_widens_language_code(self):
        sql = read_file("core-rust/migrations/003_widen_phone_and_language_code.sql")
        assert "language_code" in sql, "migration 003 must ALTER the language_code column"

    def test_migration_003_is_idempotent(self):
        """Migration must use conditional logic so it is safe to run multiple times."""
        sql = read_file("core-rust/migrations/003_widen_phone_and_language_code.sql")
        # Either IF NOT EXISTS or a DO $$ BEGIN / IF EXISTS pattern is acceptable
        has_conditional = (
            "IF NOT EXISTS" in sql.upper()
            or "IF EXISTS" in sql.upper()
            or ("DO" in sql.upper() and "IF" in sql.upper())
        )
        assert has_conditional, (
            "migration 003 must be idempotent (use conditional DDL so it can be "
            "applied to databases that are already on the new schema)"
        )


# ===========================================================================
# Fix 1c — db/mod.rs runs migration 003
# ===========================================================================


class TestMigrationRunnerIncludes003:
    """
    The migration runner must execute 003_widen_phone_and_language_code.sql
    so existing production databases get the columns widened on next startup.
    """

    def test_migration_runner_includes_003(self):
        src = read_file("core-rust/src/db/mod.rs")
        assert "003_widen_phone_and_language_code" in src, (
            "db/mod.rs must include and run 003_widen_phone_and_language_code.sql"
        )


# ===========================================================================
# Fix 1d — Rust handler has truncate_str safety net
# ===========================================================================


class TestTruncateStrHelper:
    """
    The Rust create_user handler must truncate field values before binding
    them so that even if the column sizes are not yet updated the handler
    will not panic or return a 500 error.
    """

    def test_truncate_str_helper_defined(self):
        src = read_file("core-rust/src/handlers/users.rs")
        assert "truncate_str" in src, (
            "handlers/users.rs must define a truncate_str helper to guard "
            "against 'value too long' database errors"
        )

    def test_truncate_applied_to_phone(self):
        src = read_file("core-rust/src/handlers/users.rs")
        # truncate_str should be called with phone
        assert re.search(r'truncate_str\s*\(\s*&phone', src), (
            "truncate_str must be applied to the phone field in create_user"
        )

    def test_truncate_applied_to_language_code(self):
        src = read_file("core-rust/src/handlers/users.rs")
        assert re.search(r'truncate_str\s*\(\s*&language_code', src), (
            "truncate_str must be applied to language_code in create_user"
        )


# ===========================================================================
# Fix 2 — selfie_file_id included in CREATE USER INSERT
# ===========================================================================


class TestSelfieFileIdInCreateUser:
    """
    The create_user handler must include selfie_file_id in its INSERT
    statement so that:
      - Callers can supply a selfie at registration time.
      - The column's NOT NULL constraint is always satisfied (defaults to '').
    """

    def test_create_user_inserts_selfie_file_id(self):
        src = read_file("core-rust/src/handlers/users.rs")
        # The INSERT column list must name selfie_file_id
        insert_block = re.search(
            r'INSERT INTO users\s*\(([^)]+)\)',
            src,
            re.DOTALL,
        )
        assert insert_block is not None, "create_user must contain an INSERT INTO users (...) statement"
        columns = insert_block.group(1)
        assert "selfie_file_id" in columns, (
            "The INSERT column list must include selfie_file_id so the NOT NULL "
            "constraint is always satisfied"
        )

    def test_create_user_struct_has_selfie_file_id(self):
        src = read_file("core-rust/src/models/user.rs")
        # CreateUser struct must have the field
        create_user_block = re.search(
            r'pub struct CreateUser\s*\{(.+?)\}',
            src,
            re.DOTALL,
        )
        assert create_user_block is not None, "CreateUser struct must exist in models/user.rs"
        assert "selfie_file_id" in create_user_block.group(1), (
            "CreateUser struct must have a selfie_file_id field"
        )

    def test_create_user_first_name_is_optional(self):
        """first_name should be optional so users without a Telegram name can register."""
        src = read_file("core-rust/src/models/user.rs")
        create_user_block = re.search(
            r'pub struct CreateUser\s*\{(.+?)\}',
            src,
            re.DOTALL,
        )
        assert create_user_block is not None
        block = create_user_block.group(1)
        # first_name must be Option<String>, not plain String
        match = re.search(r'pub first_name\s*:\s*(\S+)', block)
        assert match is not None, "CreateUser must have a first_name field"
        assert "Option" in match.group(1), (
            "first_name in CreateUser must be Option<String> so it is not required"
        )
