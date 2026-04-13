"""
Tests for issue #302 fixes:

  1. Centrifugo config: unknown key "log_format" caused a warning on startup.
     Fixed by removing the "log_format" key from centrifugo.json.

  2. Centrifugo config: "allowed_origins": ["*"] triggers a security warning.
     Fixed by documenting use of CENTRIFUGO_ALLOWED_ORIGINS env var in
     docker-compose.microservices.yml to override the wildcard at runtime.

  3. GET /api/users/{id}/ws_token/ returned 404 because the Rust API
     (core-rust) had no handler for this endpoint.
     Fixed by adding get_ws_token() handler in core-rust/src/handlers/users.rs
     and registering the route in core-rust/src/main.rs.

  4. GET /api/chat/notifications/?user_id=8 returned all notifications regardless
     of the user_id filter because the Rust API's NotificationQuery struct used
     the field name "user" while the frontend sent "user_id".
     Fixed by renaming the field to "user_id" in NotificationQuery and updating
     the handler in core-rust/src/handlers/chat.rs.

  5. Kafka consumer group coordinator errors in notification-service caused the
     consumer to fail repeatedly on Kafka broker restart.
     Fixed by:
     - Adding sessionTimeout, heartbeatInterval, and retry configuration to
       the KafkaJS consumer.
     - Disconnecting the consumer before each retry attempt in
       startConsumerWithRetry() so reconnections start from a clean state.
     - Increasing the Kafka client-level retry count and backoff parameters.

All tests are static-analysis assertions (no live server required).
"""
import json
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

CENTRIFUGO_JSON = os.path.join(ROOT, "services", "chat-service", "centrifugo", "centrifugo.json")
MICROSERVICES_COMPOSE = os.path.join(ROOT, "docker-compose.microservices.yml")
RUST_USERS_HANDLER = os.path.join(ROOT, "core-rust", "src", "handlers", "users.rs")
RUST_CHAT_HANDLER = os.path.join(ROOT, "core-rust", "src", "handlers", "chat.rs")
RUST_CHAT_MODELS = os.path.join(ROOT, "core-rust", "src", "models", "chat.rs")
RUST_MAIN = os.path.join(ROOT, "core-rust", "src", "main.rs")
NOTIFICATION_SERVICE = os.path.join(ROOT, "services", "notification-service", "src", "index.js")


def read(path):
    with open(path) as f:
        return f.read()


def read_json(path):
    with open(path) as f:
        return json.load(f)


# ===========================================================================
# Fix 1 — Centrifugo: remove unknown "log_format" key
# ===========================================================================

class TestCentrifugoConfig:
    def test_log_format_key_removed(self):
        """
        The "log_format" key in centrifugo.json is not recognised by Centrifugo v5
        and produces: warn key="log_format" message="unknown key found in config".
        It must be removed.
        """
        cfg = read_json(CENTRIFUGO_JSON)
        assert "log_format" not in cfg, (
            'centrifugo.json must not contain the "log_format" key — it is '
            "unrecognised by Centrifugo v5 and generates a startup warning."
        )

    def test_log_level_still_present(self):
        """
        Removing log_format must not also remove log_level, which is valid.
        """
        cfg = read_json(CENTRIFUGO_JSON)
        assert "log_level" in cfg, (
            'centrifugo.json must still contain "log_level" (a valid Centrifugo key).'
        )

    def test_allowed_origins_present(self):
        """
        The allowed_origins key must remain in centrifugo.json (even as ["*"]
        for development); production deployments override it via the
        CENTRIFUGO_ALLOWED_ORIGINS environment variable.
        """
        cfg = read_json(CENTRIFUGO_JSON)
        assert "allowed_origins" in cfg, (
            'centrifugo.json must still define "allowed_origins".'
        )

    def test_microservices_compose_documents_allowed_origins_override(self):
        """
        docker-compose.microservices.yml must document that operators should
        set CENTRIFUGO_ALLOWED_ORIGINS in their .env file to restrict WebSocket
        origins and suppress the security warning about wildcard "*".
        """
        source = read(MICROSERVICES_COMPOSE)
        assert "CENTRIFUGO_ALLOWED_ORIGINS" in source, (
            "docker-compose.microservices.yml must reference CENTRIFUGO_ALLOWED_ORIGINS "
            "so operators know how to restrict the allowed origins in production."
        )


# ===========================================================================
# Fix 2 — Rust API: GET /api/users/{id}/ws_token/ endpoint
# ===========================================================================

class TestWsTokenRustEndpoint:
    def test_get_ws_token_handler_exists(self):
        """
        core-rust/src/handlers/users.rs must contain a get_ws_token handler.
        """
        source = read(RUST_USERS_HANDLER)
        assert "pub async fn get_ws_token" in source, (
            "core-rust/src/handlers/users.rs must define a get_ws_token async handler "
            "to serve GET /api/users/{id}/ws_token/ requests."
        )

    def test_ws_token_uses_jwt_encode(self):
        """
        The get_ws_token handler must use the jsonwebtoken crate to encode the JWT.
        """
        source = read(RUST_USERS_HANDLER)
        assert "encode(" in source, (
            "get_ws_token must call jsonwebtoken::encode() to produce a signed JWT."
        )

    def test_ws_token_reads_jwt_secret_from_env(self):
        """
        The handler must read JWT_SECRET from the environment so it matches
        the secret used by the WebSocket server.
        """
        source = read(RUST_USERS_HANDLER)
        assert "JWT_SECRET" in source, (
            "get_ws_token must read JWT_SECRET from the environment to produce "
            "a token compatible with the WebSocket server."
        )

    def test_ws_token_includes_user_id_in_claims(self):
        """
        The JWT claims struct must include user_id.
        """
        source = read(RUST_USERS_HANDLER)
        assert "user_id" in source, (
            "The JWT claims struct for ws_token must include user_id."
        )

    def test_ws_token_includes_expiry(self):
        """
        The JWT claims must set an expiry (exp field) so tokens are short-lived.
        """
        source = read(RUST_USERS_HANDLER)
        assert "exp:" in source or "exp :" in source, (
            "The WsClaims struct used by get_ws_token must include an 'exp' field."
        )

    def test_ws_token_route_registered_in_main(self):
        """
        The /api/users/{id}/ws_token/ route must be registered in main.rs.
        """
        source = read(RUST_MAIN)
        assert "ws_token" in source, (
            'core-rust/src/main.rs must register the /api/users/{id}/ws_token/ route '
            "using handlers::users::get_ws_token."
        )

    def test_ws_token_openapi_path_registered(self):
        """
        The get_ws_token handler must be included in the OpenAPI #[openapi(paths(...))]
        macro so the endpoint is visible in the Swagger UI.
        """
        source = read(RUST_MAIN)
        assert "handlers::users::get_ws_token" in source, (
            "handlers::users::get_ws_token must be listed in the OpenAPI paths() "
            "in main.rs so the endpoint appears in the API documentation."
        )

    def test_ws_token_verifies_user_exists(self):
        """
        get_ws_token must verify the user exists in the database before issuing
        a token, returning 404 for unknown user IDs.
        """
        source = read(RUST_USERS_HANDLER)
        # The handler should query the DB for the user
        assert "SELECT EXISTS" in source or "SELECT * FROM users WHERE id" in source, (
            "get_ws_token must verify the user exists in the database before "
            "issuing a JWT, to prevent issuing tokens for non-existent user IDs."
        )


# ===========================================================================
# Fix 3 — Rust API: notifications filter by user_id
# ===========================================================================

class TestNotificationsUserIdFilter:
    def test_notification_query_uses_user_id_field(self):
        """
        NotificationQuery in core-rust/src/models/chat.rs must use the field
        name 'user_id' (not 'user') to match the query parameter sent by the
        frontend (?user_id=<N>).
        """
        source = read(RUST_CHAT_MODELS)
        # Must contain user_id field in NotificationQuery
        assert "user_id" in source, (
            "NotificationQuery in models/chat.rs must have a 'user_id' field "
            "to correctly deserialise the ?user_id=<N> query parameter."
        )
        # Must NOT use bare 'pub user:' (old broken field name)
        match = re.search(
            r'struct NotificationQuery\s*\{(.*?)\}', source, re.DOTALL
        )
        assert match, "NotificationQuery struct not found in models/chat.rs"
        struct_body = match.group(1)
        assert "pub user:" not in struct_body, (
            "NotificationQuery must not have a bare 'user' field — the frontend "
            "sends 'user_id', so the struct field must also be named 'user_id'."
        )

    def test_list_notifications_handler_uses_user_id(self):
        """
        The list_notifications handler must dereference query.user_id (not
        query.user) to filter notifications by the correct query parameter.
        """
        source = read(RUST_CHAT_HANDLER)
        assert "query.user_id" in source, (
            "list_notifications in handlers/chat.rs must filter by query.user_id "
            "(not query.user) to match the ?user_id=<N> query parameter."
        )

    def test_list_notifications_openapi_param_is_user_id(self):
        """
        The utoipa OpenAPI docs for list_notifications must describe the
        query parameter as 'user_id', not 'user'.
        """
        source = read(RUST_CHAT_HANDLER)
        # Find the doc comment / utoipa path macro above list_notifications
        match = re.search(
            r'/// GET /api/chat/notifications/\?user_id.*?pub async fn list_notifications',
            source, re.DOTALL
        )
        assert match, (
            "The docstring / utoipa path above list_notifications must document "
            "the query parameter as 'user_id' (e.g. '?user_id=...')."
        )


# ===========================================================================
# Fix 4 — Kafka consumer group coordinator fix in notification-service
# ===========================================================================

class TestKafkaConsumerConfig:
    def test_consumer_has_session_timeout(self):
        """
        The KafkaJS consumer must be created with a sessionTimeout so that the
        broker considers it alive during rebalances caused by a Kafka restart.
        """
        source = read(NOTIFICATION_SERVICE)
        assert "sessionTimeout" in source, (
            "notification-service must set sessionTimeout on the KafkaJS consumer "
            "to reduce 'not the correct coordinator' errors after broker restarts."
        )

    def test_consumer_has_heartbeat_interval(self):
        """
        The KafkaJS consumer must set heartbeatInterval to keep the session alive
        during long message processing operations.
        """
        source = read(NOTIFICATION_SERVICE)
        assert "heartbeatInterval" in source, (
            "notification-service must configure heartbeatInterval on the KafkaJS "
            "consumer so the broker does not consider it dead during processing."
        )

    def test_retry_disconnect_before_reconnect(self):
        """
        startConsumerWithRetry must call consumer.disconnect() before retrying
        so that a stale connection state does not prevent a clean reconnect.
        """
        source = read(NOTIFICATION_SERVICE)
        assert "consumer.disconnect()" in source, (
            "startConsumerWithRetry must call consumer.disconnect() before each "
            "retry attempt to reset the consumer state for a clean reconnect."
        )

    def test_kafka_client_retry_config_increased(self):
        """
        The Kafka client must have an increased retry count (retries >= 10) to
        survive transient broker restarts without giving up too early.
        """
        source = read(NOTIFICATION_SERVICE)
        # Check that retries is set to at least 10 somewhere
        match = re.search(r'retries:\s*(\d+)', source)
        assert match, "Kafka client or consumer must configure a 'retries' value."
        retries_value = int(match.group(1))
        assert retries_value >= 10, (
            f"Kafka retry count should be >= 10 to tolerate broker restarts, "
            f"but found retries: {retries_value}."
        )
