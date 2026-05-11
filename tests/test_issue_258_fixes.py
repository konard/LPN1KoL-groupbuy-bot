"""
Tests for issue #258 fixes (Russian: comprehensive cross-service audit).

The issue asked to audit every service listed in ``docker-compose.unified.yml``,
build a complete endpoint map and find every mismatch between callers and the
services they call (wrong host, wrong port, missing route, wrong method, etc.).
This test suite encodes the regression checks for the concrete defects that
the audit uncovered and fixed.

Fixes covered:

  1. ``POST /procurements/{proc_id}/check_access/`` was missing from
     ``core-fastapi`` even though the Telegram bot and the websocket-server
     called it.  Restored as a router-level endpoint.

  2. ``GET /payments/`` was missing — ``bot.api_client.get_payment_history``
     hit a 404.  Re-introduced as a paginated list endpoint.

  3. ``GET /chat/messages/unread_count/`` was missing — the bot's
     ``get_unread_count`` and the unread-badge logic both relied on it.

  4. Gateway WebSocket proxy was pointing at chat-service:4004 (which has no
     ``/ws`` handler).  A dedicated ``WEBSOCKET_URL`` env var now defaults to
     ``http://websocket-server:8765`` so /ws lands on the right container.

  5. Several services and the frontend dev proxy hard-coded ``localhost``
     defaults that break inside the docker-compose network.  Replaced with the
     docker service hostnames:
       * services/chat-service/app.py:        REDIS_URL → redis://redis:6379
       * services/search-service/app.py:      REDIS_URL → redis://redis:6379
       * services/analytics-service/main.py:  KAFKA_BROKERS → kafka:9092
                                              S3_ENDPOINT  → http://minio:9000
       * services/shared-lib/groupbuy_shared/config.py:
                                              redis_url    → redis://redis:6379
                                              kafka_brokers → kafka:9092
       * frontend-react/vite.config.js:       gateway/api/ws defaults switched
                                              from localhost to docker hostnames.

  6. Role-change error ("Ошибка изменения роли") — verified that the user_commands
     router is wired into the bot dispatcher and that the change-role callback
     handlers post to PATCH /users/{id}/ which already accepts ``role`` per
     ``core-fastapi/app/schemas.py:UpdateUser``.  Test guards against regression
     of either side of that contract.
"""

import os
import re

import pytest


ROOT = os.path.join(os.path.dirname(__file__), "..")

CORE_PROCUREMENTS = os.path.join(ROOT, "core-fastapi", "app", "routers", "procurements.py")
CORE_PAYMENTS = os.path.join(ROOT, "core-fastapi", "app", "routers", "payments.py")
CORE_CHAT = os.path.join(ROOT, "core-fastapi", "app", "routers", "chat.py")
CORE_SCHEMAS = os.path.join(ROOT, "core-fastapi", "app", "schemas.py")
CORE_USERS_ROUTER = os.path.join(ROOT, "core-fastapi", "app", "routers", "users.py")

GATEWAY_MAIN = os.path.join(ROOT, "services", "gateway", "main.py")
CHAT_SERVICE_APP = os.path.join(ROOT, "services", "chat-service", "app.py")
SEARCH_SERVICE_APP = os.path.join(ROOT, "services", "search-service", "app.py")
ANALYTICS_SERVICE_MAIN = os.path.join(ROOT, "services", "analytics-service", "main.py")
SHARED_CONFIG = os.path.join(ROOT, "services", "shared-lib", "groupbuy_shared", "config.py")
VITE_CONFIG = os.path.join(ROOT, "frontend-react", "vite.config.js")

BOT_API_CLIENT = os.path.join(ROOT, "bot", "api_client.py")
BOT_MAIN = os.path.join(ROOT, "bot", "main.py")
BOT_USER_COMMANDS = os.path.join(ROOT, "bot", "handlers", "user_commands.py")


def read(path):
    with open(path) as f:
        return f.read()


# ─── 1. Missing core-fastapi endpoints (check_access / payments / unread) ─────


class TestCoreFastApiMissingEndpoints:
    def test_procurements_check_access_endpoint_exists(self):
        """POST /procurements/{proc_id}/check_access/ must be defined."""
        src = read(CORE_PROCUREMENTS)
        assert re.search(
            r'@router\.post\(\s*["\']/\{proc_id\}/check_access/["\']',
            src,
        ), "POST /procurements/{proc_id}/check_access/ is missing"
        # Body validation: returns access boolean / 403 on no access
        assert '"access": True' in src and 'access": False' in src, (
            "check_access must distinguish access granted vs denied"
        )

    def test_check_access_validates_user_id_uuid(self):
        """The endpoint must require user_id and validate it as a UUID."""
        src = read(CORE_PROCUREMENTS)
        match = re.search(
            r"async def check_access\(.*?\):\n(.*?)\n@router\.",
            src, re.S,
        )
        assert match, "check_access body not found"
        body = match.group(1)
        assert "user_id" in body and "UUID" in body, (
            "check_access must parse user_id as UUID"
        )

    def test_payments_list_endpoint_exists(self):
        """GET /payments/ must list payments (filterable by user_id)."""
        src = read(CORE_PAYMENTS)
        # The router has prefix "/payments" already; the new route is "/"
        match = re.search(
            r'@router\.get\(\s*["\']/["\'].*?\)\s*\n\s*async def list_payments\(',
            src, re.S,
        )
        assert match, "GET /payments/ (list_payments) is missing"
        assert "user_id: UUID | None" in src, (
            "list_payments should accept an optional user_id query parameter"
        )
        assert "ORDER BY created_at DESC" in src, (
            "list_payments should return payments sorted by created_at DESC"
        )

    def test_chat_unread_count_endpoint_exists(self):
        """GET /chat/messages/unread_count/ must be defined."""
        src = read(CORE_CHAT)
        assert re.search(
            r'@router\.get\(\s*["\']/messages/unread_count/["\']',
            src,
        ), "GET /chat/messages/unread_count/ is missing"
        # Endpoint must accept user_id and procurement_id query params
        assert "user_id: UUID = Query" in src and "procurement_id: int = Query" in src, (
            "unread_count must accept user_id (UUID) and procurement_id (int) as Query params"
        )

    def test_bot_api_client_paths_match_core_routes(self):
        """The bot's api_client must call the exact routes the core exposes."""
        api = read(BOT_API_CLIENT)
        assert "check_procurement_access" in api
        # check_access endpoint
        assert re.search(
            r"f?\"/procurements/\{[^}]+\}/check_access/?\"",
            api,
        ), "bot.api_client must call /procurements/{id}/check_access/"
        # payments list
        assert re.search(
            r'"/payments/?"',
            api,
        ), "bot.api_client must hit GET /payments/ for history"
        # unread count
        assert re.search(
            r'"/chat/messages/unread_count/?"',
            api,
        ), "bot.api_client must call /chat/messages/unread_count/"


# ─── 2. Gateway WebSocket proxy targets websocket-server ──────────────────────


class TestGatewayWebSocketRouting:
    def test_websocket_url_env_var_exists(self):
        """Gateway must read a dedicated WEBSOCKET_URL env var and default it
        to the docker hostname of the websocket-server container."""
        src = read(GATEWAY_MAIN)
        assert re.search(
            r'WEBSOCKET_URL[^\n]*os\.getenv\(\s*"WEBSOCKET_URL"\s*,\s*'
            r'"http://websocket-server:8765"\s*\)',
            src,
        ), "gateway must define WEBSOCKET_URL default = http://websocket-server:8765"

    def test_websocket_target_uses_websocket_url(self):
        """_websocket_target must build its base URL from WEBSOCKET_URL, not
        from SERVICE_URLS['chat']."""
        src = read(GATEWAY_MAIN)
        match = re.search(
            r"def _websocket_target\([^)]*\)[^:]*:\n(.*?)\n\s*(?:def |async def |@)",
            src, re.S,
        )
        assert match, "_websocket_target function body not found"
        body = match.group(1)
        assert "WEBSOCKET_URL" in body, (
            "_websocket_target must base its URL on WEBSOCKET_URL"
        )
        assert 'SERVICE_URLS["chat"]' not in body, (
            "_websocket_target must NOT route to chat-service — chat-service has no /ws"
        )


# ─── 3. Localhost defaults replaced with docker service hostnames ─────────────


class TestDockerHostnameDefaults:
    @pytest.mark.parametrize(
        "path,bad,good",
        [
            (CHAT_SERVICE_APP,    'REDIS_URL", "redis://localhost:6379"', 'REDIS_URL", "redis://redis:6379"'),
            (SEARCH_SERVICE_APP,  'REDIS_URL", "redis://localhost:6379"', 'REDIS_URL", "redis://redis:6379"'),
            (ANALYTICS_SERVICE_MAIN, 'KAFKA_BROKERS", "localhost:9092"', 'KAFKA_BROKERS", "kafka:9092"'),
            (ANALYTICS_SERVICE_MAIN, 'S3_ENDPOINT", "http://localhost:9000"', 'S3_ENDPOINT", "http://minio:9000"'),
        ],
    )
    def test_localhost_default_replaced(self, path, bad, good):
        """Per-service localhost defaults must point at the docker-compose
        service hostname so the container can reach its peers inside the
        compose network."""
        src = read(path)
        assert bad not in src, f"{path} still has localhost default: {bad!r}"
        assert good in src, f"{path} is missing docker-hostname default: {good!r}"

    def test_shared_lib_defaults(self):
        """The shared BaseServiceSettings defaults must use docker hostnames."""
        src = read(SHARED_CONFIG)
        assert 'default="redis://localhost:6379"' not in src
        assert 'default="redis://redis:6379"' in src
        assert 'default="localhost:9092"' not in src
        assert 'default="kafka:9092"' in src

    def test_vite_proxy_defaults(self):
        """The frontend dev proxy defaults must point inside the docker network
        — running the React container with no env overrides should still proxy
        to the correct upstreams."""
        src = read(VITE_CONFIG)
        assert "'http://localhost:3001'" not in src, "gateway default must not be localhost"
        assert "'http://localhost:8000'" not in src, "core default must not be localhost"
        assert "'ws://localhost:8000'" not in src, "websocket default must not be localhost"
        assert "'http://gateway:3000'" in src
        assert "'http://core:8000'" in src
        assert "'ws://websocket-server:8765'" in src


# ─── 4. Role change error — handler + schema contract preserved ───────────────


class TestRoleChangeFlow:
    def test_user_commands_router_registered_in_bot(self):
        """The bot dispatcher must include the user_commands router or the
        change-role callbacks never fire and the user sees 'Ошибка изменения роли'."""
        src = read(BOT_MAIN)
        assert "user_commands" in src and "include_router(user_commands.router)" in src, (
            "bot/main.py must include_router(user_commands.router)"
        )

    def test_change_role_callbacks_exist(self):
        """user_commands.py must register callbacks for change_role and the
        role_<role> selection that PATCH the user's role through api_client."""
        src = read(BOT_USER_COMMANDS)
        assert 'F.data == "change_role"' in src, (
            "callback handler for 'change_role' button is missing"
        )
        # The role selection handler uses F.data.startswith("role_") — this
        # outside-FSM handler is what makes the profile-page role switch work.
        assert 'F.data.startswith("role_")' in src, (
            "callback handler for 'role_<role>' selection is missing"
        )
        # The selection handler must call api_client.update_user with the chosen role
        assert re.search(
            r"update_user\([^)]*\{\s*['\"]role['\"]\s*:\s*\w+\s*\}\s*\)",
            src,
        ), "role selection must call update_user(..., {'role': ...})"

    def test_api_client_update_user_uses_patch(self):
        """api_client.update_user must use PATCH on /users/{id}/ so the core
        UpdateUser schema accepts the partial payload."""
        src = read(BOT_API_CLIENT)
        match = re.search(
            r"async def update_user\([^)]*\) ->[^:]*:\n((?:        .*\n|\n)+?)(?=\n    (?:async )?def |\nclass |\Z)",
            src,
        )
        assert match, "update_user not found in api_client.py"
        body = match.group(1)
        assert ('"PATCH"' in body or "'PATCH'" in body), (
            "update_user must issue a PATCH request"
        )
        assert "/users/" in body, "update_user must target /users/{id}/"

    def test_core_update_user_schema_accepts_role(self):
        """core-fastapi UpdateUser schema must allow `role` as an optional field."""
        src = read(CORE_SCHEMAS)
        match = re.search(r"class UpdateUser\(BaseModel\):(.*?)(?:\nclass |\Z)", src, re.S)
        assert match, "UpdateUser class not found"
        body = match.group(1)
        assert re.search(r"\brole:\s*str\s*\|\s*None\b", body), (
            "UpdateUser must declare `role: str | None` so role updates aren't rejected"
        )

    def test_core_users_router_patches_role(self):
        """The PATCH /users/{id}/ endpoint must actually persist the role
        change when the payload provides one."""
        src = read(CORE_USERS_ROUTER)
        # PATCH on /users/{user_id}/ must be declared.
        assert re.search(
            r'@router\.patch\(\s*"/\{user_id\}/"',
            src,
        ), "PATCH /users/{user_id}/ must be defined"
        # Slice the handler body by line markers — find the `async def
        # update_user` line and walk forward until the next @router decorator.
        lines = src.splitlines()
        start = next(
            (i for i, line in enumerate(lines) if line.startswith("async def update_user(")),
            None,
        )
        assert start is not None, "async def update_user not found"
        end = next(
            (j for j in range(start + 1, len(lines)) if lines[j].startswith("@router.")),
            len(lines),
        )
        body = "\n".join(lines[start:end])
        assert '("role", "role")' in body, (
            "update_user must include ('role', 'role') in its updatable column list"
        )
        assert "UPDATE users SET" in body, (
            "update_user must issue an UPDATE users SET ... query"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
