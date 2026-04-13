"""
Tests for issue #202 fixes.

Two related problems were reported:

  Problem 1 — Django migration failure on container restart:
    django.db.utils.ProgrammingError: relation "chat_messa_procure_a1b2c3_idx"
    does not exist

    Failing migration:
    chat.0002_rename_chat_messa_procure_a1b2c3_idx_chat_messag_procure_43963d_idx_and_more

    Root cause:
    - core/entrypoint.sh runs `manage.py makemigrations` before `manage.py migrate`
    - chat/migrations/0001_initial.py creates indexes with CUSTOM hand-crafted names
      (e.g., 'chat_messa_procure_a1b2c3_idx') but chat/models.py declares those same
      indexes WITHOUT explicit names
    - Django auto-generates names from field names, producing DIFFERENT names than
      what 0001_initial.py used
    - makemigrations detects this discrepancy (migration state vs model state) and
      auto-generates a 0002 rename migration
    - When migrate then runs 0002, it tries to rename chat_messa_procure_a1b2c3_idx
      but on databases where the schema was created via an older code path that used
      auto-generated names, the old custom name does not exist → ProgrammingError

    Fix:
    Add explicit `name=` arguments to the Meta.indexes in chat/models.py that
    MATCH the names already used in 0001_initial.py.  With model state and
    migration state now consistent, `makemigrations` produces no rename migration,
    and the container starts cleanly on both fresh and existing databases.

  Problem 2 — Organizer cannot create a procurement; category dropdown is empty:

    Root cause (chain from Problem 1):
    - Migration failure causes `manage.py migrate` to exit with a non-zero code
    - entrypoint.sh uses `set -e` → container stops immediately
    - The fixture loading step (`loaddata initial_categories`) never executes
    - The `categories` table is empty in the database
    - CategoryViewSet.get_queryset() returns an empty queryset
    - The React frontend receives [] from GET /api/procurements/categories/
    - The <select> dropdown for category in CreateProcurementModal renders no options

    Fix:
    Fixing Problem 1 (migration) unblocks entrypoint.sh so the fixture is loaded,
    categories appear in the database, and the dropdown renders correctly.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath):
    """Read a file relative to the repo root."""
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Problem 1 — chat/models.py index names must match 0001_initial.py
# ===========================================================================


class TestChatModelIndexNames:
    """
    chat/models.py Meta.indexes must declare explicit names matching the names
    already used in chat/migrations/0001_initial.py.  Without this, Django's
    makemigrations (run in entrypoint.sh) detects a discrepancy between the
    migration state (custom names) and the model state (auto-generated names)
    and generates a 0002 rename migration that fails on many database states.
    """

    MODELS_PATH = "core/chat/models.py"
    MIGRATION_PATH = "core/chat/migrations/0001_initial.py"

    # The four index names that 0001_initial.py creates; models.py must use the same.
    EXPECTED_INDEX_NAMES = [
        "chat_messa_procure_a1b2c3_idx",
        "chat_messa_user_id_d4e5f6_idx",
        "notificati_user_id_g7h8i9_idx",
        "notificati_created_j0k1l2_idx",
    ]

    def test_message_procurement_created_at_index_name(self):
        """
        Message.Meta.indexes[0] on ['procurement', 'created_at'] must use the same
        explicit name as 0001_initial.py to prevent a makemigrations rename cycle.
        """
        src = read_file(self.MODELS_PATH)
        assert "chat_messa_procure_a1b2c3_idx" in src, (
            "core/chat/models.py Message.Meta.indexes must declare "
            "name='chat_messa_procure_a1b2c3_idx' for the "
            "['procurement', 'created_at'] index.  Without this explicit name, "
            "makemigrations generates a 0002 rename migration that fails with "
            "ProgrammingError when the index does not exist under the old name."
        )

    def test_message_user_index_name(self):
        """
        Message.Meta.indexes[1] on ['user'] must use the same explicit name as
        0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "chat_messa_user_id_d4e5f6_idx" in src, (
            "core/chat/models.py Message.Meta.indexes must declare "
            "name='chat_messa_user_id_d4e5f6_idx' for the ['user'] index.  "
            "See issue #202 for the ProgrammingError this mismatch causes."
        )

    def test_notification_user_is_read_index_name(self):
        """
        Notification.Meta.indexes[0] on ['user', 'is_read'] must use the same
        explicit name as 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "notificati_user_id_g7h8i9_idx" in src, (
            "core/chat/models.py Notification.Meta.indexes must declare "
            "name='notificati_user_id_g7h8i9_idx' for the ['user', 'is_read'] "
            "index.  See issue #202."
        )

    def test_notification_created_at_index_name(self):
        """
        Notification.Meta.indexes[1] on ['created_at'] must use the same explicit
        name as 0001_initial.py.
        """
        src = read_file(self.MODELS_PATH)
        assert "notificati_created_j0k1l2_idx" in src, (
            "core/chat/models.py Notification.Meta.indexes must declare "
            "name='notificati_created_j0k1l2_idx' for the ['created_at'] index.  "
            "See issue #202."
        )

    def test_all_index_names_present_in_models(self):
        """All four index names from 0001_initial.py must also appear in models.py."""
        src = read_file(self.MODELS_PATH)
        missing = [name for name in self.EXPECTED_INDEX_NAMES if name not in src]
        assert not missing, (
            f"core/chat/models.py is missing these index names from 0001_initial.py: "
            f"{missing}.  This mismatch causes makemigrations to generate a broken "
            f"0002 rename migration (issue #202)."
        )

    def test_all_index_names_present_in_initial_migration(self):
        """Regression guard: all four names must still be in 0001_initial.py."""
        src = read_file(self.MIGRATION_PATH)
        missing = [name for name in self.EXPECTED_INDEX_NAMES if name not in src]
        assert not missing, (
            f"core/chat/migrations/0001_initial.py is missing these index names: "
            f"{missing}.  This file should not be changed without also updating "
            f"models.py to keep both in sync."
        )

    def test_index_names_consistent_between_model_and_migration(self):
        """
        Every index name that appears in 0001_initial.py via AddIndex must also
        appear in models.py, and vice versa.  This guards against future drift.
        """
        migration_src = read_file(self.MIGRATION_PATH)
        models_src = read_file(self.MODELS_PATH)

        # Extract names from AddIndex operations
        add_index_names = set(re.findall(
            r'migrations\.AddIndex\([^)]*name=[\'"]([^\'"]+)[\'"]',
            migration_src,
            re.DOTALL,
        ))

        # Extract names from models.py Index() calls
        model_index_names = set(re.findall(
            r'models\.Index\([^)]*name=[\'"]([^\'"]+)[\'"]',
            models_src,
            re.DOTALL,
        ))

        assert add_index_names, (
            "No migrations.AddIndex(name=...) entries found in 0001_initial.py"
        )
        assert model_index_names, (
            "No models.Index(name=...) entries found in models.py — "
            "explicit names are required to prevent makemigrations from "
            "generating a rename migration (issue #202)"
        )
        assert add_index_names == model_index_names, (
            f"Index names in 0001_initial.py and models.py must match exactly.\n"
            f"  Only in migration: {add_index_names - model_index_names}\n"
            f"  Only in models:    {model_index_names - add_index_names}"
        )


# ===========================================================================
# Problem 1 — no stray 0002 rename migration
# ===========================================================================


class TestNoChatRenameIndexMigration:
    """
    Ensure the broken 0002 rename migration does not exist in the repository.
    If it were present, any environment where the indexes do not carry the
    custom names from 0001_initial.py would crash during `manage.py migrate`.
    """

    MIGRATIONS_DIR = "core/chat/migrations"

    def test_no_0002_rename_migration_file(self):
        """
        There must be NO 0002 migration file for the chat app.  The only allowed
        migrations are 0001_initial.py (and __init__.py).  A 0002 rename migration
        would be auto-generated by makemigrations when models.py lacks explicit
        index names — the root cause of issue #202.
        """
        migrations_dir = os.path.join(ROOT, self.MIGRATIONS_DIR)
        migration_files = [
            f for f in os.listdir(migrations_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]
        rename_migrations = [
            f for f in migration_files
            if f.startswith("0002") and "rename" in f.lower()
        ]
        assert not rename_migrations, (
            f"Stray rename migration(s) found in {self.MIGRATIONS_DIR}: "
            f"{rename_migrations}.  These are auto-generated by makemigrations "
            f"when models.py index names do not match 0001_initial.py names.  "
            f"Remove them and add explicit name= to Meta.indexes in models.py "
            f"(see issue #202)."
        )

    def test_only_initial_migration_exists(self):
        """Only 0001_initial.py should exist in the chat migrations folder."""
        migrations_dir = os.path.join(ROOT, self.MIGRATIONS_DIR)
        migration_files = sorted([
            f for f in os.listdir(migrations_dir)
            if f.endswith(".py") and f != "__init__.py"
        ])
        assert migration_files == ["0001_initial.py"], (
            f"Expected only ['0001_initial.py'] in {self.MIGRATIONS_DIR}, "
            f"found: {migration_files}.  Extra migrations (especially rename "
            f"migrations) indicate a models.py / migration name mismatch."
        )


# ===========================================================================
# Problem 2 — categories fixture and API
# ===========================================================================


class TestCategoriesFixtureExists:
    """
    The initial categories fixture must exist so that after a successful
    migration run the `loaddata initial_categories` command in entrypoint.sh
    can populate the categories table.  Without this data the frontend
    category dropdown is empty and organizers cannot create procurements.
    """

    FIXTURE_PATH = "core/procurements/fixtures/initial_categories.json"

    def test_fixture_file_exists(self):
        path = os.path.join(ROOT, self.FIXTURE_PATH)
        assert os.path.isfile(path), (
            f"{self.FIXTURE_PATH} must exist so that the container entrypoint "
            "can load initial category data after running migrations"
        )

    def test_fixture_contains_categories(self):
        """Fixture must contain at least one category entry."""
        import json
        path = os.path.join(ROOT, self.FIXTURE_PATH)
        with open(path) as f:
            data = json.load(f)
        categories = [
            obj for obj in data
            if obj.get("model") == "procurements.category"
        ]
        assert len(categories) >= 1, (
            f"{self.FIXTURE_PATH} must contain at least one procurements.category "
            "entry so the frontend category dropdown has options"
        )

    def test_fixture_has_active_categories(self):
        """Fixture must contain categories with is_active=True for the API to return them."""
        import json
        path = os.path.join(ROOT, self.FIXTURE_PATH)
        with open(path) as f:
            data = json.load(f)
        active = [
            obj for obj in data
            if obj.get("model") == "procurements.category"
            and obj.get("fields", {}).get("is_active") is True
        ]
        assert len(active) >= 1, (
            f"{self.FIXTURE_PATH} must have categories with is_active=True.  "
            "CategoryViewSet.get_queryset() filters on is_active=True, so inactive "
            "categories are invisible to the frontend dropdown."
        )


class TestEntrypointLoadsFixture:
    """
    entrypoint.sh must load the initial_categories fixture after running
    migrations so that the category dropdown is populated when the container
    first starts.
    """

    ENTRYPOINT_PATH = "core/entrypoint.sh"

    def test_entrypoint_loads_initial_categories(self):
        src = read_file(self.ENTRYPOINT_PATH)
        assert "initial_categories" in src, (
            f"{self.ENTRYPOINT_PATH} must call `manage.py loaddata "
            "initial_categories` (or equivalent) after running migrations so "
            "that the category dropdown is populated on first start"
        )

    def test_entrypoint_loads_fixture_after_migrate(self):
        """
        The loaddata call must appear AFTER the migrate command so that the
        categories table exists before the fixture is loaded.
        """
        src = read_file(self.ENTRYPOINT_PATH)
        migrate_pos = src.find("manage.py migrate")
        loaddata_pos = src.find("loaddata")
        assert migrate_pos != -1, (
            f"{self.ENTRYPOINT_PATH} must call `manage.py migrate`"
        )
        assert loaddata_pos != -1, (
            f"{self.ENTRYPOINT_PATH} must call `manage.py loaddata initial_categories`"
        )
        assert migrate_pos < loaddata_pos, (
            f"{self.ENTRYPOINT_PATH}: loaddata must come AFTER migrate so the "
            "categories table exists before inserting fixture rows"
        )


class TestCategoryAPIEndpoint:
    """
    CategoryViewSet must be registered at /api/procurements/categories/ and
    the frontend api.js must call that same URL so the dropdown can populate.
    """

    URLS_PATH = "core/procurements/urls.py"
    API_JS_PATH = "frontend-react/src/services/api.js"

    def test_categories_router_registered(self):
        src = read_file(self.URLS_PATH)
        assert "categories" in src and "CategoryViewSet" in src, (
            f"{self.URLS_PATH} must register CategoryViewSet under the "
            "'categories' prefix so GET /api/procurements/categories/ works"
        )

    def test_categories_registered_before_empty_prefix(self):
        """
        'categories' must be registered BEFORE the empty '' prefix in the DRF
        router so that URL matching routes /categories/ to CategoryViewSet and
        not to ProcurementViewSet (which would treat 'categories' as a pk).
        """
        src = read_file(self.URLS_PATH)
        categories_pos = src.find("'categories'")
        # find the empty-prefix register — could be register(r'', ...) or register('', ...)
        empty_prefix_pos = max(src.find("r''"), src.find("''"))
        assert categories_pos != -1, (
            f"{self.URLS_PATH}: 'categories' router registration not found"
        )
        assert empty_prefix_pos != -1, (
            f"{self.URLS_PATH}: empty-prefix ('') router registration not found"
        )
        assert categories_pos < empty_prefix_pos, (
            f"{self.URLS_PATH}: 'categories' must be registered BEFORE the "
            "empty '' prefix router so that URL matching prioritises "
            "CategoryViewSet for /categories/ requests"
        )

    def test_frontend_api_calls_categories_endpoint(self):
        src = read_file(self.API_JS_PATH)
        assert "/procurements/categories/" in src, (
            f"{self.API_JS_PATH}: getCategories() must call "
            "'/procurements/categories/' so the dropdown can load category data"
        )


# ===========================================================================
# Regression guard — entrypoint.sh still uses --fake-initial
# ===========================================================================


class TestEntrypointFakeInitialNotRemoved:
    """
    The --fake-initial flag added in issue #182 must still be present.
    Fixing issue #202 must not regress the #182 fix.
    """

    def test_entrypoint_still_has_fake_initial(self):
        src = read_file("core/entrypoint.sh")
        assert "--fake-initial" in src, (
            "core/entrypoint.sh must still pass --fake-initial to manage.py "
            "migrate (regression guard for issue #182 fix)"
        )
