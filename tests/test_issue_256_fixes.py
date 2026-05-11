"""
Tests for issue #256 fixes (Russian: "fix all problems" / "Отсувствует вход в админку"):

  1. /api/users/* — frontend calls like /api/users/{auth-uuid}/balance/ returned 404
     because core auto-generated its own UUID and auth-service never propagated
     the auth UUID. Fixed by:
       a) core-fastapi/app/schemas.py:CreateUser now accepts optional `id: UUID`.
       b) core-fastapi/app/routers/users.py:create_user is now an idempotent
          UPSERT on (platform, platform_user_id) — re-syncing the same user no
          longer raises a constraint error.
       c) services/auth-service/app.py:_sync_user_to_core sends `id` so the
          core record reuses the auth UUID. confirm_registration awaits the
          sync (was fire-and-forget), and confirm_login back-fills the core
          record for stale users.

  2. Telegram bot crash on delete_webhook — when api.telegram.org is unreachable
     (region block, no TELEGRAM_USE_PROXY) the bot exited, taking the adapter
     HTTP server on port 8001 down with it.  Fixed by wrapping delete_webhook
     in try/except TelegramNetworkError in bot/main.py — polling's built-in
     retry loop handles reconnects.

  3. groupbuy-django-admin container restart loop — entrypoint.sh calls `psql`
     to provision django_admin_db on first start, but the image only had
     libpq-dev (headers), not the psql binary.  Fixed by adding
     `postgresql-client` to apt-get install in core/Dockerfile.

  4. Same as (1): /api/users/by_email/, /api/users/{id}/balance/, and
     PATCH /api/users/{id}/ all returned 404 because of UUID drift between
     auth-service and core.  Same fixes as (1).

  5. "Отсувствует вход в админку" — admin panel login at /admin (HTTP/HTTPS)
     returned 404 because nginx-api.conf's `upstream django_admin_api`
     pointed at `core:8000`, which is the FastAPI core service that has no
     admin panel at all.  Fixed by routing /admin and /api/admin/ to
     `django-admin:8000` via the deferred-resolution variable pattern
     (set $django_admin_backend; proxy_pass $django_admin_backend) so nginx
     starts even when django-admin is briefly unavailable.
"""

import os
import re

import pytest


ROOT = os.path.join(os.path.dirname(__file__), "..")

CORE_DOCKERFILE = os.path.join(ROOT, "core", "Dockerfile")
BOT_MAIN = os.path.join(ROOT, "bot", "main.py")
CORE_SCHEMAS = os.path.join(ROOT, "core-fastapi", "app", "schemas.py")
CORE_USERS_ROUTER = os.path.join(ROOT, "core-fastapi", "app", "routers", "users.py")
AUTH_APP = os.path.join(ROOT, "services", "auth-service", "app.py")
NGINX_API_CONF = os.path.join(ROOT, "infrastructure", "nginx", "nginx-api.conf")


def read(path):
    with open(path) as f:
        return f.read()


# ─── 1 & 4. /api/users sync — core schema + upsert + auth-service propagation ──

class TestUserSync:
    def test_create_user_schema_accepts_explicit_id(self):
        """CreateUser must allow an optional `id: UUID` so auth-service can
        propagate its own UUID into core."""
        src = read(CORE_SCHEMAS)
        # Locate the CreateUser class body up to the next blank-line/class
        match = re.search(r"class CreateUser\(BaseModel\):(.*?)\nclass ", src, re.S)
        assert match, "CreateUser class not found in schemas.py"
        body = match.group(1)
        assert re.search(r"\bid:\s*UUID\s*\|\s*None\b", body), (
            "CreateUser should declare `id: UUID | None` to accept an explicit id"
        )

    def test_create_user_is_idempotent_upsert(self):
        """create_user must ON CONFLICT DO UPDATE on (platform, platform_user_id)
        so a retried sync does not raise a duplicate-key error."""
        src = read(CORE_USERS_ROUTER)
        assert "ON CONFLICT (platform, platform_user_id) DO UPDATE" in src, (
            "create_user must upsert on (platform, platform_user_id) to be retry-safe"
        )

    def test_create_user_honors_explicit_id_branch(self):
        """When body.id is provided, the INSERT must include the id column so
        the row's primary key matches the auth-service UUID."""
        src = read(CORE_USERS_ROUTER)
        # The id-branch must include `id` as the first INSERT column
        assert re.search(
            r"if body\.id is not None:.*?INSERT INTO users\s*\(\s*id,",
            src, re.S,
        ), "When body.id is set, INSERT must list `id` as the first column"

    def test_auth_service_passes_id_when_syncing(self):
        """auth-service's _sync_user_to_core must send the auth UUID as `id`."""
        src = read(AUTH_APP)
        assert '"id": str(user["id"])' in src, (
            "_sync_user_to_core must include the auth UUID as `id` in its payload"
        )

    def test_auth_service_awaits_sync_on_registration(self):
        """confirm_registration must await the sync — fire-and-forget masks
        sync failures and lets the frontend hit a non-existent core record."""
        src = read(AUTH_APP)
        # No leftover fire-and-forget on the sync function
        assert "asyncio.create_task(_sync_user_to_core(" not in src, (
            "Sync to core must not be fire-and-forget — use await instead"
        )
        assert "await _sync_user_to_core(" in src, (
            "confirm_registration / confirm_login must await _sync_user_to_core"
        )


# ─── 2. Telegram bot resilient delete_webhook ──────────────────────────────────

class TestBotDeleteWebhook:
    def test_delete_webhook_is_wrapped_in_try_except(self):
        """delete_webhook on startup must not crash the bot when api.telegram.org
        is unreachable — otherwise the adapter server on 8001 dies too."""
        src = read(BOT_MAIN)
        # The wrapper imports TelegramNetworkError and catches it around delete_webhook
        assert "from aiogram.exceptions import TelegramNetworkError" in src
        # The try/except must surround _bot.delete_webhook
        match = re.search(
            r"try:\s*\n\s*await _bot\.delete_webhook\(.*?\)\s*\n"
            r"\s*except TelegramNetworkError",
            src, re.S,
        )
        assert match, (
            "await _bot.delete_webhook(...) must be wrapped in "
            "try / except TelegramNetworkError"
        )


# ─── 3. django-admin container has psql ────────────────────────────────────────

class TestDjangoAdminDockerfile:
    def test_postgresql_client_is_installed(self):
        """entrypoint.sh runs psql to create django_admin_db; without
        postgresql-client the container loops with 'psql: not found'."""
        src = read(CORE_DOCKERFILE)
        # postgresql-client must appear inside an apt-get install block
        match = re.search(
            r"apt-get install\b[^&]*?\bpostgresql-client\b",
            src, re.S,
        )
        assert match, "core/Dockerfile must apt-get install postgresql-client"


# ─── 5. Admin panel routes to django-admin, not core ───────────────────────────

class TestAdminPanelRouting:
    def test_no_stale_django_admin_api_upstream_to_core(self):
        """The buggy upstream `django_admin_api { server core:8000; }` must be
        removed — core has no admin panel."""
        src = read(NGINX_API_CONF)
        # Strip comment lines before searching, so the explanatory comment
        # describing the removed block doesn't trigger a false positive.
        non_comment = "\n".join(
            line for line in src.splitlines() if not line.lstrip().startswith("#")
        )
        upstream_block = re.search(
            r"upstream\s+django_admin_api\s*\{[^}]*\}",
            non_comment,
        )
        assert upstream_block is None, (
            "upstream django_admin_api { ... } must be removed — admin routes "
            "should go to django-admin:8000, not core:8000"
        )

    def test_admin_locations_route_to_django_admin(self):
        """/admin and /api/admin/ must proxy to django-admin:8000."""
        src = read(NGINX_API_CONF)
        # Both /admin and /api/admin/ must use the django-admin backend variable
        assert src.count("set $django_admin_backend http://django-admin:8000;") >= 4, (
            "Both HTTP and HTTPS server blocks should set "
            "$django_admin_backend = http://django-admin:8000 for /admin and "
            "/api/admin/ (4 occurrences total, plus the port-8000 server block "
            "for 5)"
        )
        # No location should still proxy_pass to the removed upstream name
        assert "proxy_pass http://django_admin_api" not in src, (
            "No location may still proxy_pass to the removed django_admin_api upstream"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
