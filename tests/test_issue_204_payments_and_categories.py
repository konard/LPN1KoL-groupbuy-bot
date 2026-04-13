"""
Tests for issue #204 fixes.

Three related problems were reported:

  Problem 1 — Django admin (superuser) not created automatically:
    Root cause (chain from Problem 2):
    - Migration failure causes `manage.py migrate` to exit with a non-zero code
    - entrypoint.sh uses `set -e` → container stops before the superuser creation
      step is reached
    Fix:
    Fixing Problem 2 (migration) unblocks entrypoint.sh so superuser creation runs.
    The superuser creation logic in entrypoint.sh is already correct — it uses
    django.contrib.auth.models.User with an idempotent check.

  Problem 2 — Migration error: relation "payments_user_id_a1b2c3_idx" does not exist:
    Failing migration:
    payments.0003_rename_payments_user_id_a1b2c3_idx_payments_user_id_1b771c_idx_and_more

    Root cause (same pattern as issue #202 for the chat app):
    - core/entrypoint.sh runs `manage.py makemigrations` before `manage.py migrate`
    - payments/migrations/0001_initial.py creates indexes with CUSTOM hand-crafted names
      (e.g., 'payments_user_id_a1b2c3_idx') but payments/models.py declares those same
      indexes WITHOUT explicit names
    - Django auto-generates names from field names, producing DIFFERENT names
    - makemigrations detects this discrepancy and auto-generates a 0003 rename migration
    - When migrate runs 0003, it tries to rename the old custom-named index but on
      databases where the schema was created with old auto-generated names → ProgrammingError

    Fix:
    Add explicit `name=` arguments to Meta.indexes in payments/models.py (and
    transactions/Meta.indexes) that MATCH the names already used in 0001_initial.py.
    With model state and migration state now consistent, `makemigrations` produces no
    rename migration.

  Problem 3 — API /api/procurements/categories/ does not return all categories:
    Root cause:
    - The global DRF setting DEFAULT_PAGINATION_CLASS='PageNumberPagination' with
      PAGE_SIZE=20 applies to all ViewSets, including CategoryViewSet
    - When more than 20 categories exist in the database, the response is paginated
      and the frontend receives only the first page (20 items), not all categories
    Fix:
    Set pagination_class = None on CategoryViewSet to bypass global pagination and
    always return the full list.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath):
    """Read a file relative to the repo root."""
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Problem 2 — payments/models.py index names must match 0001_initial.py
# ===========================================================================


class TestPaymentsModelIndexNames:
    """
    payments/models.py Meta.indexes must declare explicit names matching the names
    already used in payments/migrations/0001_initial.py.  Without this, Django's
    makemigrations (run in entrypoint.sh) detects a discrepancy between the
    migration state (custom names) and the model state (auto-generated names)
    and generates a 0003 rename migration that fails on many database states.
    """

    MODELS_PATH = "core/payments/models.py"
    MIGRATION_PATH = "core/payments/migrations/0001_initial.py"

    # The five index names that 0001_initial.py creates; models.py must use the same.
    EXPECTED_PAYMENT_INDEX_NAMES = [
        "payments_user_id_a1b2c3_idx",
        "payments_externa_d4e5f6_idx",
        "payments_created_g7h8i9_idx",
    ]

    EXPECTED_TRANSACTION_INDEX_NAMES = [
        "transactio_user_id_j0k1l2_idx",
        "transactio_transac_m3n4o5_idx",
    ]

    def test_payment_user_status_index_name(self):
        """
        Payment.Meta.indexes on ['user', 'status'] must use explicit name
        'payments_user_id_a1b2c3_idx' matching 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "payments_user_id_a1b2c3_idx" in src, (
            "core/payments/models.py Payment.Meta.indexes must declare "
            "name='payments_user_id_a1b2c3_idx' for the ['user', 'status'] index.  "
            "Without this explicit name, makemigrations generates a 0003 rename "
            "migration that fails with ProgrammingError (issue #204)."
        )

    def test_payment_external_id_index_name(self):
        """
        Payment.Meta.indexes on ['external_id'] must use explicit name
        'payments_externa_d4e5f6_idx' matching 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "payments_externa_d4e5f6_idx" in src, (
            "core/payments/models.py Payment.Meta.indexes must declare "
            "name='payments_externa_d4e5f6_idx' for the ['external_id'] index.  "
            "See issue #204."
        )

    def test_payment_created_at_index_name(self):
        """
        Payment.Meta.indexes on ['created_at'] must use explicit name
        'payments_created_g7h8i9_idx' matching 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "payments_created_g7h8i9_idx" in src, (
            "core/payments/models.py Payment.Meta.indexes must declare "
            "name='payments_created_g7h8i9_idx' for the ['created_at'] index.  "
            "See issue #204."
        )

    def test_transaction_user_created_at_index_name(self):
        """
        Transaction.Meta.indexes on ['user', 'created_at'] must use explicit name
        'transactio_user_id_j0k1l2_idx' matching 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "transactio_user_id_j0k1l2_idx" in src, (
            "core/payments/models.py Transaction.Meta.indexes must declare "
            "name='transactio_user_id_j0k1l2_idx' for the ['user', 'created_at'] index.  "
            "See issue #204."
        )

    def test_transaction_type_index_name(self):
        """
        Transaction.Meta.indexes on ['transaction_type'] must use explicit name
        'transactio_transac_m3n4o5_idx' matching 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "transactio_transac_m3n4o5_idx" in src, (
            "core/payments/models.py Transaction.Meta.indexes must declare "
            "name='transactio_transac_m3n4o5_idx' for the ['transaction_type'] index.  "
            "See issue #204."
        )

    def test_all_payment_index_names_in_models(self):
        """All Payment index names from 0001_initial.py must appear in models.py."""
        src = read_file(self.MODELS_PATH)
        missing = [n for n in self.EXPECTED_PAYMENT_INDEX_NAMES if n not in src]
        assert not missing, (
            f"core/payments/models.py is missing these Payment index names: {missing}.  "
            "This mismatch causes makemigrations to generate a broken 0003 rename "
            "migration (issue #204)."
        )

    def test_all_transaction_index_names_in_models(self):
        """All Transaction index names from 0001_initial.py must appear in models.py."""
        src = read_file(self.MODELS_PATH)
        missing = [n for n in self.EXPECTED_TRANSACTION_INDEX_NAMES if n not in src]
        assert not missing, (
            f"core/payments/models.py is missing these Transaction index names: {missing}.  "
            "This mismatch causes makemigrations to generate a broken 0003 rename "
            "migration (issue #204)."
        )

    def test_index_names_consistent_between_model_and_migration(self):
        """
        Every index name in 0001_initial.py via AddIndex must also appear in
        models.py, and vice versa.  Guards against future drift.
        """
        migration_src = read_file(self.MIGRATION_PATH)
        models_src = read_file(self.MODELS_PATH)

        add_index_names = set(re.findall(
            r'migrations\.AddIndex\([^)]*name=[\'"]([^\'"]+)[\'"]',
            migration_src,
            re.DOTALL,
        ))
        model_index_names = set(re.findall(
            r'models\.Index\([^)]*name=[\'"]([^\'"]+)[\'"]',
            models_src,
            re.DOTALL,
        ))

        assert add_index_names, (
            "No migrations.AddIndex(name=...) entries found in 0001_initial.py"
        )
        assert model_index_names, (
            "No models.Index(name=...) entries found in payments/models.py — "
            "explicit names are required to prevent makemigrations from "
            "generating a rename migration (issue #204)"
        )
        assert add_index_names == model_index_names, (
            f"Index names in 0001_initial.py and payments/models.py must match exactly.\n"
            f"  Only in migration: {add_index_names - model_index_names}\n"
            f"  Only in models:    {model_index_names - add_index_names}"
        )


# ===========================================================================
# Problem 2 — no stray 0003 rename migration
# ===========================================================================


class TestNoPaymentsRenameIndexMigration:
    """
    Ensure no auto-generated rename migration exists for the payments app.
    If present, any database where indexes use different names would crash
    during `manage.py migrate`.
    """

    MIGRATIONS_DIR = "core/payments/migrations"

    def test_no_rename_migration_file(self):
        """
        There must be NO rename migration file for the payments app.  Such a
        file is auto-generated by makemigrations when models.py lacks explicit
        index names matching 0001_initial.py — the root cause of issue #204.
        """
        migrations_dir = os.path.join(ROOT, self.MIGRATIONS_DIR)
        migration_files = [
            f for f in os.listdir(migrations_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]
        rename_migrations = [f for f in migration_files if "rename" in f.lower()]
        assert not rename_migrations, (
            f"Stray rename migration(s) found in {self.MIGRATIONS_DIR}: "
            f"{rename_migrations}.  These are auto-generated by makemigrations "
            f"when models.py index names do not match 0001_initial.py.  "
            f"Remove them and add explicit name= to Meta.indexes in models.py "
            f"(see issue #204)."
        )


# ===========================================================================
# Problem 3 — CategoryViewSet must not paginate
# ===========================================================================


class TestCategoryViewSetNoPagination:
    """
    CategoryViewSet must set pagination_class = None so that all categories
    are returned in a single response regardless of how many exist in the DB.

    The global DRF setting PAGE_SIZE=20 would otherwise truncate the list when
    there are more than 20 categories, causing the frontend dropdown to appear
    incomplete.
    """

    VIEWS_PATH = "core/procurements/views.py"

    def test_category_viewset_disables_pagination(self):
        """CategoryViewSet must set pagination_class = None."""
        src = read_file(self.VIEWS_PATH)
        assert "pagination_class = None" in src, (
            f"{self.VIEWS_PATH}: CategoryViewSet must set "
            "`pagination_class = None` to override the global PAGE_SIZE=20 "
            "setting and return all categories in a single response (issue #204)."
        )

    def test_pagination_none_in_category_viewset_class(self):
        """
        pagination_class = None must appear inside CategoryViewSet, not in
        another viewset.
        """
        src = read_file(self.VIEWS_PATH)
        # Find the CategoryViewSet class body up to the next class definition
        match = re.search(
            r'class CategoryViewSet\b.*?(?=\nclass |\Z)',
            src,
            re.DOTALL,
        )
        assert match, "CategoryViewSet class not found in views.py"
        class_body = match.group(0)
        assert "pagination_class = None" in class_body, (
            "pagination_class = None must be declared inside CategoryViewSet, "
            "not in another viewset (issue #204)."
        )


# ===========================================================================
# Problem 1 — entrypoint.sh superuser creation is in place
# ===========================================================================


class TestEntrypointSuperuserCreation:
    """
    entrypoint.sh must contain superuser creation logic so that the admin panel
    is accessible after a fresh deployment.

    The superuser is not created when the migration fails (Problem 2) because
    entrypoint.sh uses `set -e`.  Fixing the migration (Problem 2) allows
    entrypoint.sh to reach the superuser step.
    """

    ENTRYPOINT_PATH = "core/entrypoint.sh"

    def test_entrypoint_has_superuser_creation(self):
        """entrypoint.sh must contain superuser creation logic."""
        src = read_file(self.ENTRYPOINT_PATH)
        assert "create_superuser" in src or "createsuperuser" in src, (
            f"{self.ENTRYPOINT_PATH} must contain superuser creation logic.  "
            "Without it the admin panel is inaccessible after a fresh deployment "
            "(issue #204)."
        )

    def test_entrypoint_superuser_uses_env_vars(self):
        """
        Superuser creation must respect DJANGO_SUPERUSER_USERNAME /
        DJANGO_SUPERUSER_PASSWORD / DJANGO_SUPERUSER_EMAIL env vars.
        """
        src = read_file(self.ENTRYPOINT_PATH)
        assert "DJANGO_SUPERUSER_PASSWORD" in src, (
            f"{self.ENTRYPOINT_PATH}: superuser creation must be conditioned on "
            "DJANGO_SUPERUSER_PASSWORD being set (issue #204)."
        )

    def test_entrypoint_superuser_after_migrate(self):
        """
        Superuser creation block must appear AFTER the migrate command so the
        auth tables exist before inserting the superuser row.
        """
        src = read_file(self.ENTRYPOINT_PATH)
        migrate_pos = src.find("manage.py migrate")
        # Look for the conditional block that checks the password at runtime
        # (not the comment header at the top of the file)
        superuser_pos = src.find("if [ -n \"${DJANGO_SUPERUSER_PASSWORD")
        if superuser_pos == -1:
            superuser_pos = src.find("create_superuser")
        assert migrate_pos != -1, "manage.py migrate not found in entrypoint.sh"
        assert superuser_pos != -1, (
            "Superuser creation block not found in entrypoint.sh"
        )
        assert migrate_pos < superuser_pos, (
            f"{self.ENTRYPOINT_PATH}: superuser creation must come AFTER "
            "manage.py migrate so the auth_user table exists first (issue #204)."
        )

    def test_entrypoint_superuser_is_idempotent(self):
        """
        Superuser creation must be idempotent — it must check whether the user
        already exists before trying to create it to avoid errors on container
        restart.
        """
        src = read_file(self.ENTRYPOINT_PATH)
        assert "exists()" in src or "get_or_create" in src, (
            f"{self.ENTRYPOINT_PATH}: superuser creation must check for existing "
            "users (e.g., User.objects.filter(...).exists()) to be idempotent "
            "across container restarts (issue #204)."
        )


# ===========================================================================
# Regression guards — previous fixes must still be in place
# ===========================================================================


class TestRegressionGuards:
    """Ensure fixes from earlier issues are not accidentally reverted."""

    def test_entrypoint_still_has_fake_initial(self):
        """The --fake-initial flag from issue #182 must still be present."""
        src = read_file("core/entrypoint.sh")
        assert "--fake-initial" in src, (
            "core/entrypoint.sh must still pass --fake-initial to manage.py migrate "
            "(regression guard for issue #182 fix)"
        )

    def test_chat_model_index_names_still_present(self):
        """The chat model index names from issue #202 must still be present."""
        src = read_file("core/chat/models.py")
        for name in [
            "chat_messa_procure_a1b2c3_idx",
            "chat_messa_user_id_d4e5f6_idx",
            "notificati_user_id_g7h8i9_idx",
            "notificati_created_j0k1l2_idx",
        ]:
            assert name in src, (
                f"core/chat/models.py is missing index name '{name}' "
                f"(regression guard for issue #202 fix)"
            )
