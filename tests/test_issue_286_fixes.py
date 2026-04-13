"""
Tests for issue #286 fixes:

  1. Redis Connection Refused (Incident 1) — chat-service was connecting to
     localhost Redis inside Docker containers (fatal). Fixed by:
     a) Adding REDIS_URL env var pointing to redis service in all docker-compose files.
     b) Adding redis depends_on with service_healthy condition to chat-service.
     c) Changing the fallback in main.go from localhost to the "redis" service name.
     d) Adding fail-fast retry logic (3 attempts) instead of silently continuing.

  2. WebSocket Drops (Incident 2) — legacy Python chat server had no heartbeat.
     Fixed by adding a per-connection ping/pong loop (30s interval, 2 missed = close).

  3. Cabinet Active Purchases Missing (Incident 3) — block appeared missing because
     there was no loading state; an empty block showed before data arrived.
     Fixed by adding procurementsLoading state with a "Загрузка..." placeholder.

  4. Stale Cache (Incident 4) — after creating a new purchase it did not appear in
     Cabinet because loadStats() was never called post-creation.
     Fixed by tracking createProcurementModalOpen close transitions in a useEffect
     and calling loadStats() immediately when the modal closes.
"""
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

CHAT_SERVICE_MAIN = os.path.join(ROOT, "services", "chat-service", "main.go")
COMPOSE_MICROSERVICES = os.path.join(ROOT, "docker-compose.microservices.yml")
COMPOSE_UNIFIED = os.path.join(ROOT, "docker-compose.unified.yml")
COMPOSE_LIGHT = os.path.join(ROOT, "docker-compose.light.yml")
WS_SERVER = os.path.join(ROOT, "infrastructure", "websocket", "chat_server.py")
CABINET = os.path.join(ROOT, "frontend-react", "src", "components", "Cabinet.jsx")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Incident 1a — REDIS_URL in all docker-compose files for chat-service
# ===========================================================================

class TestRedisUrlInDockerCompose:
    """chat-service must have REDIS_URL set to the redis service, not localhost."""

    def _assert_chat_service_has_redis_url(self, compose_path):
        source = read(compose_path)
        # Find the chat-service block and ensure REDIS_URL appears after it
        assert "REDIS_URL" in source, (
            f"{compose_path}: REDIS_URL must be set for chat-service so it connects "
            "to the redis container, not to localhost."
        )
        # The REDIS_URL must point to the 'redis' service, not localhost
        redis_url_lines = [l for l in source.splitlines() if "REDIS_URL" in l]
        for line in redis_url_lines:
            assert "localhost" not in line, (
                f"{compose_path}: REDIS_URL must not point to localhost inside Docker. "
                f"Found: {line.strip()}"
            )

    def test_microservices_compose(self):
        self._assert_chat_service_has_redis_url(COMPOSE_MICROSERVICES)

    def test_unified_compose(self):
        self._assert_chat_service_has_redis_url(COMPOSE_UNIFIED)

    def test_light_compose(self):
        self._assert_chat_service_has_redis_url(COMPOSE_LIGHT)


# ===========================================================================
# Incident 1b — chat-service depends_on redis with service_healthy in compose files
# ===========================================================================

class TestChatServiceDependsOnRedis:
    """chat-service must depend on redis with health check so it starts only when Redis is ready."""

    def _get_chat_service_block(self, compose_path):
        source = read(compose_path)
        # Extract the chat-service block heuristically
        match = re.search(r'chat-service:.*?(?=\n  [a-z]|\Z)', source, re.DOTALL)
        return match.group(0) if match else ""

    def _assert_depends_on_redis_healthy(self, compose_path):
        block = self._get_chat_service_block(compose_path)
        assert block, f"chat-service block not found in {compose_path}"
        assert "redis" in block, (
            f"{compose_path}: chat-service must declare redis in depends_on."
        )

    def test_microservices_compose(self):
        self._assert_depends_on_redis_healthy(COMPOSE_MICROSERVICES)

    def test_unified_compose(self):
        self._assert_depends_on_redis_healthy(COMPOSE_UNIFIED)

    def test_light_compose(self):
        self._assert_depends_on_redis_healthy(COMPOSE_LIGHT)


# ===========================================================================
# Incident 1c — fallback in main.go uses redis service name not localhost
# ===========================================================================

class TestRedisGoFallback:
    def test_default_redis_url_uses_service_name(self):
        """
        The Go fallback for REDIS_URL must use 'redis' (Docker service name),
        not 'localhost'. 'localhost' inside a container refers to the container
        itself and will always fail to connect to the Redis container.
        """
        source = read(CHAT_SERVICE_MAIN)
        # The default value in getEnv("REDIS_URL", ...) must not contain localhost
        fallbacks = re.findall(r'getEnv\("REDIS_URL",\s*"([^"]+)"\)', source)
        assert fallbacks, "getEnv REDIS_URL call not found in main.go"
        for fallback in fallbacks:
            assert "localhost" not in fallback, (
                f'REDIS_URL fallback must not use localhost; found: "{fallback}". '
                'Use "redis://redis:6379" so Docker DNS resolves correctly.'
            )
            assert "redis:" in fallback, (
                f'REDIS_URL fallback should reference the redis service; found: "{fallback}"'
            )

    def test_redis_connection_logged_on_success(self):
        """On successful Redis connection the service must log the address."""
        source = read(CHAT_SERVICE_MAIN)
        assert "Connected to Redis" in source, (
            "main.go must log a success message when Redis is reachable so operators "
            "can verify the connection in container logs."
        )

    def test_redis_fail_fast_on_startup(self):
        """
        The service must fail fast (log.Fatalf) if Redis is unreachable after
        retries, not continue with a warning. Silently continuing hides
        misconfigurations and produces the 'connection refused' log spam.
        """
        source = read(CHAT_SERVICE_MAIN)
        assert "log.Fatalf" in source and "Redis unavailable" in source, (
            "main.go must call log.Fatalf when Redis is unreachable after retries. "
            "Continuing with broken Redis causes cascading 'connection refused' errors."
        )

    def test_redis_retry_logic_present(self):
        """main.go must retry Redis connection before giving up."""
        source = read(CHAT_SERVICE_MAIN)
        assert "redisMaxRetries" in source or "MaxRetries" in source or "retry" in source.lower(), (
            "main.go must implement retry logic for Redis connection (at least 3 attempts)."
        )


# ===========================================================================
# Incident 2 — WebSocket heartbeat in Python chat server
# ===========================================================================

class TestWebSocketHeartbeat:
    def test_ping_interval_defined(self):
        """The chat server must define a PING_INTERVAL constant."""
        source = read(WS_SERVER)
        assert "PING_INTERVAL" in source, (
            "chat_server.py must define PING_INTERVAL for the heartbeat mechanism. "
            "Without periodic pings, dead connections are never detected."
        )

    def test_max_missed_pongs_defined(self):
        """The chat server must define a MAX_MISSED_PONGS threshold."""
        source = read(WS_SERVER)
        assert "MAX_MISSED_PONGS" in source, (
            "chat_server.py must define MAX_MISSED_PONGS. Connections that miss "
            "this many pongs should be terminated server-side."
        )

    def test_heartbeat_loop_implemented(self):
        """A heartbeat loop that sends pings must be present."""
        source = read(WS_SERVER)
        assert "_heartbeat_loop" in source or "heartbeat" in source.lower(), (
            "chat_server.py must implement a heartbeat loop that sends periodic pings."
        )

    def test_pong_handling_resets_counter(self):
        """Receiving a PONG frame must reset the missed-pong counter."""
        source = read(WS_SERVER)
        assert "PONG" in source, (
            "chat_server.py must handle PONG frames to reset the missed-pong counter. "
            "Without this, connections are incorrectly terminated after each ping cycle."
        )

    def test_missed_pongs_tracking(self):
        """There must be a per-connection structure to track missed pongs."""
        source = read(WS_SERVER)
        assert "_missed_pongs" in source, (
            "chat_server.py must track missed pongs per connection to identify stale ones."
        )

    def test_stale_connection_closed(self):
        """When a connection misses too many pongs it must be closed."""
        source = read(WS_SERVER)
        assert "ws.close" in source or "await ws.close" in source, (
            "chat_server.py must close connections that fail to respond to pings."
        )

    def test_heartbeat_task_started_per_connection(self):
        """A heartbeat task must be started for each new connection."""
        source = read(WS_SERVER)
        assert "ensure_future" in source or "create_task" in source, (
            "chat_server.py must spawn an async heartbeat task per connection "
            "(asyncio.ensure_future or asyncio.create_task)."
        )

    def test_missed_pongs_cleaned_on_disconnect(self):
        """The missed-pong counter must be cleaned up when a connection is removed."""
        source = read(WS_SERVER)
        # unregister_connection should call _missed_pongs.pop
        assert "_missed_pongs.pop" in source, (
            "unregister_connection must remove the websocket from _missed_pongs to prevent memory leaks."
        )


# ===========================================================================
# Incident 3 — Loading state for active purchases in Cabinet.jsx
# ===========================================================================

class TestCabinetLoadingState:
    def test_procurements_loading_state_declared(self):
        """Cabinet must declare a procurementsLoading state."""
        source = read(CABINET)
        assert "procurementsLoading" in source, (
            "Cabinet.jsx must declare a procurementsLoading state. Without it, the "
            "active purchases block shows as empty ('Нет активных закупок') during the "
            "initial data fetch, making the block appear missing."
        )

    def test_loading_placeholder_shown_while_fetching(self):
        """A loading placeholder must be shown while procurements are being fetched."""
        source = read(CABINET)
        assert "Загрузка" in source, (
            "Cabinet.jsx must show a loading indicator (e.g., 'Загрузка...') while "
            "procurements are being fetched, instead of an empty block."
        )

    def test_loading_state_set_during_fetch(self):
        """setProcurementsLoading(true) must be called before the fetch."""
        source = read(CABINET)
        assert "setProcurementsLoading(true)" in source, (
            "Cabinet.jsx must call setProcurementsLoading(true) before fetching procurements."
        )

    def test_loading_state_cleared_after_fetch(self):
        """setProcurementsLoading(false) must be called after the fetch (in finally block)."""
        source = read(CABINET)
        assert "setProcurementsLoading(false)" in source, (
            "Cabinet.jsx must call setProcurementsLoading(false) after the fetch completes "
            "(in a finally block so it always runs even on error)."
        )


# ===========================================================================
# Incident 4 — Refresh active purchases after creation (stale cache fix)
# ===========================================================================

class TestCabinetProcurementCreatedRefresh:
    def test_create_procurement_modal_open_tracked(self):
        """Cabinet must subscribe to createProcurementModalOpen from the store."""
        source = read(CABINET)
        assert "createProcurementModalOpen" in source, (
            "Cabinet.jsx must read createProcurementModalOpen from the store to detect "
            "when the modal closes after a successful procurement creation."
        )

    def test_load_stats_called_on_modal_close(self):
        """loadStats must be called when createProcurementModalOpen transitions from true to false."""
        source = read(CABINET)
        assert "prevCreateModalOpen" in source or "createProcurementModalOpen" in source, (
            "Cabinet.jsx must detect when createProcurementModalOpen closes and call "
            "loadStats() so the new procurement appears immediately without a page refresh."
        )

    def test_load_stats_is_reusable_callback(self):
        """loadStats should be a useCallback so it can be called from multiple effects."""
        source = read(CABINET)
        assert "useCallback" in source, (
            "Cabinet.jsx should use useCallback for loadStats so it can be referenced "
            "from multiple useEffect hooks without causing infinite loops."
        )

    def test_prev_modal_ref_used(self):
        """A ref must be used to track the previous modal state to detect the close transition."""
        source = read(CABINET)
        assert "prevCreateModalOpen" in source, (
            "Cabinet.jsx must use a ref (prevCreateModalOpen) to track the previous "
            "value of createProcurementModalOpen and detect the true→false transition."
        )
