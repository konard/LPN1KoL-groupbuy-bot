"""
Tests for issue #188 fixes:
  1. selfie_file_id NOT NULL constraint — Rust core migration adds the column
     with a default empty string so user creation does not violate NOT NULL.
  2. Routing — /api/users/by_email/ and /api/users/by_phone/ are registered
     as dedicated routes before the /api/users/{id}/ catch-all so they no
     longer produce "cannot parse 'by_email' to i32" warnings.
  3. Django Admin DisallowedHost — external IP (95.81.123.52) added to
     ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, and CORS_ALLOWED_ORIGINS.
"""
import os
import re

import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_unified_compose():
    """Load docker-compose.unified.yml as a dict."""
    path = os.path.join(ROOT, "docker-compose.unified.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def parse_env_var(env_list, key):
    """Return the value string for KEY=VALUE in env_list, or None."""
    for entry in env_list:
        if isinstance(entry, str) and entry.startswith(key + "="):
            return entry[len(key) + 1:]
        if isinstance(entry, dict) and key in entry:
            return str(entry[key])
    return None


def read_file(relpath):
    """Read a file relative to the repo root."""
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


# ===========================================================================
# Fix 1 — selfie_file_id in Rust core
# ===========================================================================


class TestSelfieFileIdRustMigration:
    """
    The users table must include selfie_file_id (VARCHAR, NOT NULL DEFAULT '')
    in the Rust core migration so that INSERT statements from the core API do
    not trigger NOT NULL constraint violations when Django has already added
    the column.
    """

    def test_initial_migration_has_selfie_file_id(self):
        sql = read_file("core-rust/migrations/001_initial.sql")
        assert "selfie_file_id" in sql, (
            "001_initial.sql must define selfie_file_id column"
        )

    def test_initial_migration_selfie_default_empty_string(self):
        sql = read_file("core-rust/migrations/001_initial.sql")
        # Match the column definition allowing for flexible whitespace
        pattern = r"selfie_file_id\s+VARCHAR\(\d+\)\s+NOT\s+NULL\s+DEFAULT\s+''"
        assert re.search(pattern, sql, re.IGNORECASE), (
            "selfie_file_id must be VARCHAR NOT NULL DEFAULT '' in 001_initial.sql"
        )

    def test_idempotent_migration_exists(self):
        sql = read_file("core-rust/migrations/002_add_selfie_file_id.sql")
        assert "selfie_file_id" in sql, (
            "002_add_selfie_file_id.sql must add selfie_file_id for existing databases"
        )
        assert "IF NOT EXISTS" in sql, (
            "002_add_selfie_file_id.sql must be idempotent (IF NOT EXISTS check)"
        )


class TestSelfieFileIdRustModel:
    """
    The Rust User struct must include selfie_file_id so that
    SELECT * FROM users does not fail with a missing-column error.
    """

    def test_user_struct_has_selfie_file_id(self):
        src = read_file("core-rust/src/models/user.rs")
        assert "selfie_file_id" in src, (
            "User struct in models/user.rs must include selfie_file_id field"
        )


class TestSelfieFileIdRustMigrationRunner:
    """
    The migration runner (db/mod.rs) must execute 002_add_selfie_file_id.sql
    so that existing databases get the column added.
    """

    def test_migration_runner_includes_002(self):
        src = read_file("core-rust/src/db/mod.rs")
        assert "002_add_selfie_file_id" in src, (
            "db/mod.rs must include and run 002_add_selfie_file_id.sql"
        )


# ===========================================================================
# Fix 2 — by_email and by_phone routes in Rust core
# ===========================================================================


class TestByEmailRoute:
    """
    /api/users/by_email/ must be a dedicated route in the Rust core so
    requests do not fall through to /api/users/{id}/ and fail to parse
    'by_email' as an integer.
    """

    def test_by_email_route_registered(self):
        src = read_file("core-rust/src/main.rs")
        assert "/api/users/by_email/" in src, (
            "main.rs must register /api/users/by_email/ route"
        )

    def test_by_email_handler_exists(self):
        src = read_file("core-rust/src/handlers/users.rs")
        assert "get_user_by_email" in src, (
            "handlers/users.rs must define get_user_by_email handler"
        )

    def test_by_email_case_insensitive(self):
        src = read_file("core-rust/src/handlers/users.rs")
        assert "LOWER" in src, (
            "by_email lookup should use case-insensitive comparison (LOWER)"
        )


class TestByPhoneRoute:
    """
    /api/users/by_phone/ must be a dedicated route in the Rust core so
    requests do not fall through to /api/users/{id}/ and fail to parse
    'by_phone' as an integer.
    """

    def test_by_phone_route_registered(self):
        src = read_file("core-rust/src/main.rs")
        assert "/api/users/by_phone/" in src, (
            "main.rs must register /api/users/by_phone/ route"
        )

    def test_by_phone_handler_exists(self):
        src = read_file("core-rust/src/handlers/users.rs")
        assert "get_user_by_phone" in src, (
            "handlers/users.rs must define get_user_by_phone handler"
        )

    def test_by_phone_normalizes_prefix(self):
        """Phone lookup should normalize numbers by adding + prefix."""
        src = read_file("core-rust/src/handlers/users.rs")
        # The handler should contain logic to add + prefix
        assert "starts_with('+')" in src or 'starts_with(\'+\')' in src, (
            "by_phone handler should normalize phone numbers with + prefix"
        )


class TestRoutePriority:
    """
    Named routes (/api/users/by_email/, /api/users/by_phone/) must be
    registered BEFORE the parameterized route /api/users/{id}/ so Actix
    matches them first.
    """

    def test_named_routes_before_id_route(self):
        src = read_file("core-rust/src/main.rs")
        by_email_pos = src.index("/api/users/by_email/")
        by_phone_pos = src.index("/api/users/by_phone/")
        id_route_pos = src.index('/api/users/{id}/')
        assert by_email_pos < id_route_pos, (
            "/api/users/by_email/ must be registered before /api/users/{id}/"
        )
        assert by_phone_pos < id_route_pos, (
            "/api/users/by_phone/ must be registered before /api/users/{id}/"
        )


# ===========================================================================
# Fix 3 — Django ALLOWED_HOSTS includes external IP
# ===========================================================================


class TestDjangoAllowedHostsExternalIp:
    """
    ALLOWED_HOSTS must include the external server IP (95.81.123.52) so
    that Django does not reject requests from that IP with DisallowedHost.
    """

    def test_allowed_hosts_includes_external_ip(self):
        compose = load_unified_compose()
        env = compose["services"]["django-admin"].get("environment", [])
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None, "ALLOWED_HOSTS must be set"
        assert "95.81.123.52" in value, (
            f"ALLOWED_HOSTS='{value}' must include '95.81.123.52' "
            f"to accept requests from the external server IP."
        )


class TestDjangoCsrfTrustedOriginsExternalIp:
    """
    CSRF_TRUSTED_ORIGINS must include the external IP so admin panel
    POST requests from the external IP are not rejected.
    """

    def test_csrf_trusted_origins_includes_external_ip(self):
        compose = load_unified_compose()
        env = compose["services"]["django-admin"].get("environment", [])
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        assert value is not None, "CSRF_TRUSTED_ORIGINS must be set"
        assert "95.81.123.52" in value, (
            f"CSRF_TRUSTED_ORIGINS='{value}' must include the external IP."
        )


class TestDjangoCorsAllowedOriginsExternalIp:
    """
    CORS_ALLOWED_ORIGINS must include http://95.81.123.52 so browser
    requests from the external IP are not blocked by CORS.
    """

    def test_cors_allowed_origins_includes_external_ip(self):
        compose = load_unified_compose()
        env = compose["services"]["django-admin"].get("environment", [])
        value = parse_env_var(env, "CORS_ALLOWED_ORIGINS")
        assert value is not None, "CORS_ALLOWED_ORIGINS must be set"
        assert "95.81.123.52" in value, (
            f"CORS_ALLOWED_ORIGINS='{value}' must include the external IP."
        )


# ===========================================================================
# Fix 4 — docker-compose.unified.yml general requirements
# ===========================================================================


class TestDockerComposeRestartPolicy:
    """All services should have restart: on-failure:3."""

    def test_all_services_have_restart_policy(self):
        compose = load_unified_compose()
        for name, svc in compose["services"].items():
            restart = svc.get("restart")
            assert restart is not None, (
                f"Service '{name}' must have a restart policy"
            )

    def test_all_services_restart_on_failure(self):
        compose = load_unified_compose()
        for name, svc in compose["services"].items():
            restart = svc.get("restart", "")
            assert "on-failure" in restart, (
                f"Service '{name}' restart='{restart}' should be 'on-failure:3'"
            )


class TestDockerComposeMemoryLimits:
    """Every service must have a deploy.resources.limits.memory set."""

    def test_all_services_have_memory_limit(self):
        compose = load_unified_compose()
        for name, svc in compose["services"].items():
            mem = svc.get("deploy", {}).get("resources", {}).get("limits", {}).get("memory")
            assert mem is not None, (
                f"Service '{name}' must have deploy.resources.limits.memory set"
            )
