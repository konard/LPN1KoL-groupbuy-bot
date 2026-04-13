"""
Tests for issue #192 fixes.

Three related errors were reported:

  Error 1 — Django Admin crash-loop (DuplicateColumn):
    psycopg2.errors.DuplicateColumn: column "selfie_file_id" of relation
    "users" already exists
    django.db.utils.ProgrammingError: column "selfie_file_id" of relation
    "users" already exists

    Root cause: the Rust core service creates the users table with
    selfie_file_id already present (001_initial.sql).  When Django migration
    0003_user_selfie_file_id ran afterwards it issued an unconditional
    ALTER TABLE … ADD COLUMN which failed on the pre-existing column.

    Fix: replace migrations.AddField with migrations.RunSQL that wraps the
    ALTER TABLE in a DO $$ … IF NOT EXISTS … END $$ block so the migration
    is idempotent regardless of whether the column was added by the Rust
    service or a previous Django migration.

  Error 2 — Core NOT NULL violation:
    null value in column "selfie_file_id" of relation "users" violates
    not-null constraint

    Root cause: the column was created WITHOUT a DEFAULT (or without a NOT
    NULL default) by an earlier migration path.  The fix for Error 1 ensures
    the column is always created as VARCHAR(255) NOT NULL DEFAULT '' whether
    added by the Rust initial migration or the Django migration, so inserts
    from the Rust core (which default selfie_file_id to '') are always valid.

  Error 3 — Django Admin login fails:
    Caused by Error 1: the crash-loop prevented migrations from completing,
    so the superuser was never created.  Fixing Error 1 unblocks the
    entrypoint so it can reach the superuser-creation step.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath):
    """Read a file relative to the repo root."""
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Fix 1 — Django migration 0003 must be idempotent
# ===========================================================================


class TestDjangoMigration0003Idempotent:
    """
    Django migration 0003_user_selfie_file_id must not crash when the
    selfie_file_id column already exists (added by the Rust core's initial SQL
    migration).  The migration must use conditional DDL (IF NOT EXISTS) instead
    of a plain AddField operation.
    """

    MIGRATION_PATH = "core/users/migrations/0003_user_selfie_file_id.py"

    def test_migration_file_exists(self):
        path = os.path.join(ROOT, self.MIGRATION_PATH)
        assert os.path.isfile(path), (
            f"{self.MIGRATION_PATH} must exist"
        )

    def test_migration_does_not_use_bare_add_field(self):
        """
        migrations.AddField issues an unconditional ALTER TABLE ADD COLUMN
        which raises DuplicateColumn when the column already exists (issue #192,
        Error 1).  The migration must use RunSQL with an IF NOT EXISTS guard
        instead.
        """
        src = read_file(self.MIGRATION_PATH)
        assert "migrations.AddField" not in src, (
            f"{self.MIGRATION_PATH} must NOT use migrations.AddField for "
            "selfie_file_id.  AddField is not idempotent — it raises "
            "DuplicateColumn when the Rust core has already created the column. "
            "Use migrations.RunSQL with an IF NOT EXISTS check instead."
        )

    def test_migration_uses_run_python_or_run_sql(self):
        """Migration must use RunPython or RunSQL so it can embed conditional logic."""
        src = read_file(self.MIGRATION_PATH)
        assert "migrations.RunPython" in src or "migrations.RunSQL" in src, (
            f"{self.MIGRATION_PATH} must use migrations.RunPython or "
            "migrations.RunSQL to wrap the ALTER TABLE in conditional logic"
        )

    def test_migration_has_existence_check(self):
        """
        The migration must check whether selfie_file_id already exists before
        adding it, so the migration is safe to run on databases where the Rust
        core has already created the column.
        """
        src = read_file(self.MIGRATION_PATH)
        has_check = (
            "IF NOT EXISTS" in src.upper()
            or "selfie_file_id" in src and "not in" in src
            or "selfie_file_id" in src and "'selfie_file_id' not in" in src
        )
        assert has_check, (
            f"{self.MIGRATION_PATH} must guard against the column already existing "
            "(use IF NOT EXISTS in SQL or a Python existence check)"
        )

    def test_migration_adds_selfie_file_id(self):
        """The migration must reference the selfie_file_id column."""
        src = read_file(self.MIGRATION_PATH)
        assert "selfie_file_id" in src, (
            f"{self.MIGRATION_PATH} must add/guard the selfie_file_id column"
        )

    def test_migration_uses_varchar_255(self):
        """Column definition must be VARCHAR(255) matching the Django model."""
        src = read_file(self.MIGRATION_PATH)
        assert re.search(r"VARCHAR\s*\(\s*255\s*\)", src, re.IGNORECASE), (
            f"{self.MIGRATION_PATH} must define selfie_file_id as VARCHAR(255)"
        )

    def test_migration_has_not_null_default(self):
        """
        The column must be NOT NULL DEFAULT '' so that Rust core inserts
        (which default the field to an empty string) never violate the NOT NULL
        constraint (issue #192, Error 2).
        """
        src = read_file(self.MIGRATION_PATH)
        assert "NOT NULL" in src.upper(), (
            f"{self.MIGRATION_PATH} column definition must include NOT NULL"
        )
        assert "DEFAULT ''" in src, (
            f"{self.MIGRATION_PATH} column definition must include DEFAULT '' "
            "so rows inserted without an explicit selfie_file_id value are valid"
        )

    def test_migration_has_reverse_code(self):
        """RunPython/RunSQL must include reverse code so the migration can be rolled back."""
        src = read_file(self.MIGRATION_PATH)
        assert "reverse_code" in src or "reverse_sql" in src, (
            f"{self.MIGRATION_PATH} must supply reverse_code or reverse_sql so "
            "the migration can be rolled back with manage.py migrate users 0002"
        )

    def test_migration_depends_on_0002(self):
        """Migration must depend on 0002_user_first_name_optional."""
        src = read_file(self.MIGRATION_PATH)
        assert "0002_user_first_name_optional" in src, (
            f"{self.MIGRATION_PATH} must declare dependency on "
            "('users', '0002_user_first_name_optional')"
        )


# ===========================================================================
# Sanity-check: Django User model still declares selfie_file_id
# ===========================================================================


class TestDjangoUserModelHasSelfieField:
    """
    The User model must still declare selfie_file_id so Django's ORM knows
    about the column for admin display and serialization.
    """

    def test_user_model_has_selfie_file_id(self):
        src = read_file("core/users/models.py")
        assert "selfie_file_id" in src, (
            "core/users/models.py User model must declare selfie_file_id field"
        )

    def test_user_model_selfie_blank_true(self):
        """selfie_file_id must be blank=True (optional at the application layer)."""
        src = read_file("core/users/models.py")
        # Find the selfie_file_id field definition
        match = re.search(r"selfie_file_id\s*=\s*models\.CharField\(([^)]+)\)", src)
        assert match is not None, "selfie_file_id must be a CharField in User model"
        field_args = match.group(1)
        assert "blank=True" in field_args, (
            "selfie_file_id in User model must have blank=True so the field is "
            "not required in Django forms / admin"
        )


# ===========================================================================
# Entrypoint still uses --fake-initial (regression guard)
# ===========================================================================


class TestEntrypointFakeInitialNotRemoved:
    """
    The --fake-initial flag added in issue #182 must still be present.
    Fixing issue #192 must not regress the #182 fix.
    """

    def test_entrypoint_still_has_fake_initial(self):
        src = read_file("core/entrypoint.sh")
        assert "--fake-initial" in src, (
            "core/entrypoint.sh must still pass --fake-initial to manage.py "
            "migrate (regression guard for issue #182 fix)"
        )
