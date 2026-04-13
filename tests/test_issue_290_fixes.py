"""
Tests for issue #290 fixes:

  1. WebSocket 1008 Unauthorized loop — the frontend never obtained a JWT for
     the WebSocket server because the backend had no endpoint to issue one.
     Fixed by:
     a) Adding GET /api/users/{id}/ws_token/ action to UserViewSet that returns
        a signed JWT (PyJWT HS256) using the shared JWT_SECRET env var.
     b) Updating useStore.loadUser() to call getWsToken() after loading the user
        and persist the token to localStorage so wsManager.connect() finds it.

  2. GET /api/procurements/user/{id}/ returning 404 — the ProcurementViewSet
     user_procurements action was registered via DRF router with an empty prefix
     which should work, but added an explicit path() guard in procurements/urls.py
     to guarantee the endpoint is always reachable regardless of DRF version.

All tests are static-analysis assertions (no live server required).
"""
import ast
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

USERS_VIEWS = os.path.join(ROOT, "core", "users", "views.py")
PROCUREMENT_URLS = os.path.join(ROOT, "core", "procurements", "urls.py")
API_JS = os.path.join(ROOT, "frontend-react", "src", "services", "api.js")
USE_STORE_JS = os.path.join(ROOT, "frontend-react", "src", "store", "useStore.js")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Fix 1a — Backend: ws_token endpoint exists on UserViewSet
# ===========================================================================

class TestWsTokenEndpoint:
    """GET /api/users/{id}/ws_token/ must exist and return a signed JWT."""

    def test_jwt_import_in_users_views(self):
        source = read(USERS_VIEWS)
        assert "import jwt" in source, (
            "core/users/views.py must import PyJWT (import jwt) to sign WS tokens."
        )

    def test_ws_token_action_defined(self):
        source = read(USERS_VIEWS)
        assert "def ws_token" in source, (
            "UserViewSet must have a ws_token action method for WebSocket JWT generation."
        )

    def test_ws_token_action_decorator(self):
        source = read(USERS_VIEWS)
        # Decorator should be @action(detail=True, ...)
        assert "@action(detail=True" in source, (
            "ws_token must be a detail=True action (called with a specific user id)."
        )

    def test_ws_token_uses_jwt_encode(self):
        source = read(USERS_VIEWS)
        assert "jwt.encode" in source, (
            "ws_token action must call jwt.encode() to produce a signed token."
        )

    def test_ws_token_reads_jwt_secret_from_env(self):
        source = read(USERS_VIEWS)
        assert "JWT_SECRET" in source, (
            "ws_token must read JWT_SECRET from env so it matches the WS server secret."
        )

    def test_ws_token_includes_user_id_in_payload(self):
        source = read(USERS_VIEWS)
        assert "'user_id'" in source or '"user_id"' in source, (
            "JWT payload must include 'user_id' so the WS server can identify the user."
        )

    def test_ws_token_sets_expiry(self):
        source = read(USERS_VIEWS)
        assert "'exp'" in source or '"exp"' in source, (
            "JWT payload must include 'exp' (expiration) to limit token lifetime."
        )

    def test_ws_token_returns_token_in_response(self):
        source = read(USERS_VIEWS)
        assert "'token'" in source or '"token"' in source, (
            "ws_token response must contain a 'token' key with the encoded JWT."
        )


# ===========================================================================
# Fix 1b — Frontend: api.js exposes getWsToken, useStore calls it after loadUser
# ===========================================================================

class TestFrontendWsTokenIntegration:
    """Frontend must fetch and persist the WS JWT after loading a user."""

    def test_get_ws_token_in_api_js(self):
        source = read(API_JS)
        assert "getWsToken" in source, (
            "api.js must expose a getWsToken(userId) function that calls "
            "GET /api/users/{id}/ws_token/."
        )

    def test_get_ws_token_calls_correct_endpoint(self):
        source = read(API_JS)
        assert "ws_token" in source, (
            "api.js getWsToken must call the /ws_token/ endpoint."
        )

    def test_use_store_calls_get_ws_token(self):
        source = read(USE_STORE_JS)
        assert "getWsToken" in source, (
            "useStore.loadUser must call api.getWsToken() to obtain a WebSocket JWT "
            "after the user is loaded."
        )

    def test_use_store_persists_token_to_local_storage(self):
        source = read(USE_STORE_JS)
        assert "authToken" in source and "setItem" in source, (
            "useStore.loadUser must persist the WS JWT to localStorage under 'authToken' "
            "so wsManager.connect() can read it."
        )

    def test_ws_manager_reads_auth_token(self):
        """Existing wsManager.connect() already reads localStorage.getItem('authToken')."""
        ws_js = os.path.join(ROOT, "frontend-react", "src", "services", "websocket.js")
        source = read(ws_js)
        assert "authToken" in source, (
            "websocket.js wsManager.connect() must read 'authToken' from localStorage."
        )


# ===========================================================================
# Fix 2 — procurement URL routing: explicit path for /procurements/user/<id>/
# ===========================================================================

class TestProcurementUserUrlRouting:
    """GET /api/procurements/user/{id}/ must resolve to user_procurements action."""

    def test_explicit_user_path_in_procurements_urls(self):
        source = read(PROCUREMENT_URLS)
        assert "user/" in source, (
            "procurements/urls.py must contain an explicit 'user/' path to guarantee "
            "/api/procurements/user/{id}/ resolves correctly."
        )

    def test_user_procurements_action_still_in_views(self):
        views = os.path.join(ROOT, "core", "procurements", "views.py")
        source = read(views)
        assert "def user_procurements" in source, (
            "ProcurementViewSet must still define the user_procurements action."
        )

    def test_explicit_path_maps_get_to_user_procurements(self):
        source = read(PROCUREMENT_URLS)
        assert "user_procurements" in source, (
            "The explicit URL path in procurements/urls.py must map GET to the "
            "user_procurements view action."
        )

    def test_explicit_path_comes_before_router_include(self):
        source = read(PROCUREMENT_URLS)
        user_pos = source.find("user/")
        include_pos = source.find("include(router.urls)")
        assert user_pos < include_pos, (
            "The explicit 'user/' path must appear BEFORE include(router.urls) so it "
            "takes precedence over the router's catch-all detail route."
        )


# ===========================================================================
# Integration sanity — WS server still validates the same JWT_SECRET
# ===========================================================================

class TestWsServerJwtCompatibility:
    """WS server and Django backend must use the same JWT_SECRET env var."""

    def test_ws_server_reads_jwt_secret(self):
        ws_server = os.path.join(ROOT, "infrastructure", "websocket", "chat_server.py")
        source = read(ws_server)
        assert "JWT_SECRET" in source, (
            "chat_server.py must read JWT_SECRET from env to validate tokens issued "
            "by the backend."
        )

    def test_ws_server_uses_hs256(self):
        ws_server = os.path.join(ROOT, "infrastructure", "websocket", "chat_server.py")
        source = read(ws_server)
        assert "HS256" in source, (
            "chat_server.py must use HS256 algorithm (matching the backend's jwt.encode call)."
        )

    def test_backend_uses_hs256(self):
        source = read(USERS_VIEWS)
        assert "HS256" in source, (
            "UserViewSet.ws_token must sign with HS256 to match the WS server algorithm."
        )
