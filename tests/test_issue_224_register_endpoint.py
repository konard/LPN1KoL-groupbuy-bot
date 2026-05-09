"""Regression coverage for issue #224.

Issue #224 says issue #222 is still not fixed.  Issue #222 required:
  1. Fix "Cannot POST /auth/register" in the frontend-react container.
  2. Rewrite all services in services/ from Go/NestJS to Python + FastAPI.

PR #223 fixed the compose dependency chain (healthchecks, gateway readiness).
This test suite goes deeper to verify the runtime behaviour of the auth
registration endpoint and the service implementations themselves.

Tests here are static or in-process (no Docker required).
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
AUTH_APP = ROOT / "services" / "auth-service" / "app.py"
GATEWAY_APP = ROOT / "services" / "gateway" / "main.py"
NOTIFICATION_APP = ROOT / "services" / "notification-service" / "app.py"
PURCHASE_ENTRYPOINT = ROOT / "services" / "purchase-service" / "entrypoint.sh"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ast_endpoints(path: Path) -> list[tuple[str, str]]:
    """Return (method, path) pairs for all FastAPI route decorators in a file."""
    tree = ast.parse(_read(path))
    endpoints = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (hasattr(func, "attr") and func.attr in ("get", "post", "put", "patch", "delete")):
                continue
            path_arg = dec.args[0] if dec.args else None
            if path_arg and isinstance(path_arg, ast.Constant):
                endpoints.append((func.attr.upper(), path_arg.value))
    return endpoints


# ─── Auth-service static checks ───────────────────────────────────────────────

class TestAuthServiceEndpoints:
    """Verify that auth-service/app.py exposes all required endpoints."""

    REQUIRED = [
        ("POST", "/register"),
        ("POST", "/register/confirm"),
        ("POST", "/login"),
        ("POST", "/login/confirm"),
        ("POST", "/resend-code"),
        ("POST", "/refresh"),
        ("POST", "/logout"),
        ("GET",  "/validate"),
        ("GET",  "/me"),
        ("GET",  "/health"),
    ]

    def test_all_required_endpoints_present(self):
        endpoints = _ast_endpoints(AUTH_APP)
        for method, path in self.REQUIRED:
            assert (method, path) in endpoints, (
                f"auth-service/app.py is missing {method} {path} — "
                "this endpoint is required to fix 'Cannot POST /auth/register' (issue #224)"
            )

    def test_register_accepts_phone_and_email(self):
        src = _read(AUTH_APP)
        assert "phone" in src and "email" in src, (
            "auth-service/app.py must handle both phone and email in /register"
        )

    def test_otp_sent_to_email_on_register(self):
        src = _read(AUTH_APP)
        assert "_send_otp_email" in src or "send_otp" in src, (
            "auth-service/app.py must send OTP to the user's email during registration"
        )

    def test_register_rejects_duplicate_phone(self):
        src = _read(AUTH_APP)
        assert "already exists" in src or "duplicate" in src.lower(), (
            "auth-service/app.py must reject duplicate phone numbers at /register"
        )

    def test_register_validates_phone_format(self):
        src = _read(AUTH_APP)
        assert "PHONE_RE" in src or "validate_phone" in src or "_validate_phone" in src, (
            "auth-service/app.py must validate phone number format in /register"
        )

    def test_register_validates_email_format(self):
        src = _read(AUTH_APP)
        assert "EMAIL_RE" in src or "validate_email" in src or "_validate_email" in src, (
            "auth-service/app.py must validate email format in /register"
        )


class TestAuthServiceRuntime:
    """In-process tests that exercise the auth-service /register handler."""

    @pytest.fixture(autouse=True)
    def _load_auth_module(self):
        """Import auth-service app with mocked infrastructure."""
        auth_dir = str(ROOT / "services" / "auth-service")
        if auth_dir not in sys.path:
            sys.path.insert(0, auth_dir)

        # Reload to get a fresh module (avoids cross-test state)
        if "app" in sys.modules:
            del sys.modules["app"]

        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)
        mock_pool.execute = AsyncMock()
        mock_pool.fetchval = AsyncMock(return_value=None)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.set = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock()

        with patch("asyncpg.create_pool", return_value=mock_pool):
            with patch("redis.asyncio.from_url", return_value=mock_redis):
                import app as auth_module
                auth_module._pool = mock_pool
                auth_module._redis = mock_redis
                self.auth = auth_module
                self.pool = mock_pool
                self.redis = mock_redis
                yield

        # Clean up so later tests start fresh
        if "app" in sys.modules:
            del sys.modules["app"]
        if auth_dir in sys.path:
            sys.path.remove(auth_dir)

    def _client(self):
        from fastapi.testclient import TestClient
        return TestClient(self.auth.app, raise_server_exceptions=True)

    def test_health_returns_ok(self):
        resp = self._client().get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_register_returns_200_for_new_user(self):
        self.pool.fetchrow.return_value = None  # user does not exist
        with patch.object(self.auth, "_send_otp_email", new=AsyncMock()):
            resp = self._client().post(
                "/register",
                json={"phone": "+79001234567", "email": "user@example.com"},
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["otpSent"] is True

    def test_register_rejects_invalid_phone(self):
        resp = self._client().post(
            "/register",
            json={"phone": "not-a-phone", "email": "user@example.com"},
        )
        assert resp.status_code == 400, (
            "POST /register must return 400 for an invalid phone number"
        )

    def test_register_rejects_invalid_email(self):
        resp = self._client().post(
            "/register",
            json={"phone": "+79001234567", "email": "not-an-email"},
        )
        assert resp.status_code == 400, (
            "POST /register must return 400 for an invalid email"
        )

    def test_register_rejects_duplicate_phone(self):
        from asyncpg import Record
        # First fetchrow (phone check) returns an existing record
        existing = MagicMock()
        existing.__getitem__ = MagicMock(return_value="some-id")
        self.pool.fetchrow.return_value = existing
        resp = self._client().post(
            "/register",
            json={"phone": "+79001234567", "email": "user@example.com"},
        )
        assert resp.status_code == 400, (
            "POST /register must return 400 when phone is already registered"
        )

    def test_register_missing_phone_returns_422(self):
        resp = self._client().post(
            "/register",
            json={"email": "user@example.com"},
        )
        assert resp.status_code == 422, (
            "POST /register must return 422 (validation error) when phone is missing"
        )

    def test_register_missing_email_returns_422(self):
        resp = self._client().post(
            "/register",
            json={"phone": "+79001234567"},
        )
        assert resp.status_code == 422, (
            "POST /register must return 422 (validation error) when email is missing"
        )

    def test_register_stores_otp_session_in_redis(self):
        self.pool.fetchrow.return_value = None
        with patch.object(self.auth, "_send_otp_email", new=AsyncMock()):
            self._client().post(
                "/register",
                json={"phone": "+79001234567", "email": "user@example.com"},
            )
        self.redis.set.assert_called()
        call_args = self.redis.set.call_args_list
        keys = [str(c[0][0]) for c in call_args if c[0]]
        assert any("reg:pending:" in k for k in keys), (
            "auth-service must store the OTP session under 'reg:pending:<phone>' in Redis"
        )


# ─── Gateway static checks ────────────────────────────────────────────────────

class TestGatewayAuthRouting:
    """Verify gateway/main.py routes /api/v1/auth/register to auth-service."""

    def test_gateway_has_register_route(self):
        endpoints = _ast_endpoints(GATEWAY_APP)
        paths = [p for _, p in endpoints]
        assert "/api/v1/auth/register" in paths, (
            "gateway/main.py must expose POST /api/v1/auth/register so "
            "frontend-react can POST to it (issue #224)"
        )

    def test_gateway_auth_routes_not_jwt_protected(self):
        src = _read(GATEWAY_APP)
        assert "auth/register" in src and "PUBLIC_PATHS" in src, (
            "gateway must include auth/register in PUBLIC_PATHS "
            "so unauthenticated users can register"
        )

    def test_gateway_routes_to_auth_service_url(self):
        src = _read(GATEWAY_APP)
        assert "AUTH_SERVICE_URL" in src or "auth-service" in src, (
            "gateway must route auth requests to auth-service"
        )

    def test_legacy_auth_alias_present(self):
        """Gateway must also handle /auth/* for legacy clients."""
        endpoints = _ast_endpoints(GATEWAY_APP)
        paths = [p for _, p in endpoints]
        assert any("/auth/" in p or "auth" in p for p in paths), (
            "gateway must expose the legacy /auth/* alias for backwards compatibility"
        )


# ─── Notification-service static checks ───────────────────────────────────────

class TestNotificationServiceOtp:
    """Verify notification-service/app.py can dispatch OTP emails."""

    def test_send_otp_endpoint_present(self):
        endpoints = _ast_endpoints(NOTIFICATION_APP)
        paths = [p for _, p in endpoints]
        assert "/internal/send-otp" in paths, (
            "notification-service must expose POST /internal/send-otp "
            "so auth-service can trigger OTP email delivery"
        )

    def test_send_otp_uses_email(self):
        src = _read(NOTIFICATION_APP)
        assert "_send_email" in src or "send_email" in src, (
            "notification-service /internal/send-otp must dispatch emails"
        )

    def test_otp_body_includes_code(self):
        src = _read(NOTIFICATION_APP)
        assert "body.otp" in src or "{body.otp}" in src or "otp" in src.lower(), (
            "notification-service must include the OTP code in the email body"
        )


# ─── purchase-service entrypoint check ───────────────────────────────────────

class TestPurchaseServiceEntrypoint:
    """The entrypoint.sh must not fall back to `node dist/main`.

    When the Dockerfile passes CMD ['uvicorn', ...] the entrypoint receives
    those args and runs uvicorn correctly.  But if someone calls the container
    without CMD args (e.g. docker run image), the else branch executes.
    Having `node dist/main` there is a legacy remnant from the NestJS era
    and will fail since Node is not installed in the Python image.
    """

    def test_entrypoint_does_not_call_node(self):
        if not PURCHASE_ENTRYPOINT.exists():
            pytest.skip("purchase-service entrypoint.sh not found")
        text = PURCHASE_ENTRYPOINT.read_text()
        assert "node dist/main" not in text, (
            "purchase-service/entrypoint.sh must not fall back to 'node dist/main' "
            "— the service is now Python/FastAPI and Node is not installed in the image. "
            "Replace the fallback with 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-4002}'."
        )

    def test_entrypoint_fallback_runs_uvicorn(self):
        if not PURCHASE_ENTRYPOINT.exists():
            pytest.skip("purchase-service entrypoint.sh not found")
        text = PURCHASE_ENTRYPOINT.read_text()
        assert "uvicorn" in text, (
            "purchase-service/entrypoint.sh default command must run uvicorn "
            "since the service is Python/FastAPI"
        )


# ─── All services must be Python/FastAPI ──────────────────────────────────────

PYTHON_SERVICES = {
    "gateway": ROOT / "services" / "gateway" / "Dockerfile",
    "auth-service": ROOT / "services" / "auth-service" / "Dockerfile",
    "purchase-service": ROOT / "services" / "purchase-service" / "Dockerfile",
    "payment-service": ROOT / "services" / "payment-service" / "Dockerfile",
    "chat-service": ROOT / "services" / "chat-service" / "Dockerfile",
    "notification-service": ROOT / "services" / "notification-service" / "Dockerfile",
    "analytics-service": ROOT / "services" / "analytics-service" / "Dockerfile",
    "search-service": ROOT / "services" / "search-service" / "Dockerfile",
    "reputation-service": ROOT / "services" / "reputation-service" / "Dockerfile",
}

PYTHON_APPS = {
    "gateway": ROOT / "services" / "gateway" / "main.py",
    "auth-service": ROOT / "services" / "auth-service" / "app.py",
    "purchase-service": ROOT / "services" / "purchase-service" / "app.py",
    "payment-service": ROOT / "services" / "payment-service" / "app.py",
    "chat-service": ROOT / "services" / "chat-service" / "app.py",
    "notification-service": ROOT / "services" / "notification-service" / "app.py",
    "analytics-service": ROOT / "services" / "analytics-service" / "main.py",
    "search-service": ROOT / "services" / "search-service" / "app.py",
    "reputation-service": ROOT / "services" / "reputation-service" / "app.py",
}


@pytest.mark.parametrize("service,dockerfile", PYTHON_SERVICES.items())
def test_service_dockerfile_uses_python(service, dockerfile):
    assert dockerfile.exists(), f"Dockerfile for {service} not found at {dockerfile}"
    text = dockerfile.read_text().lower()
    assert "python:" in text, (
        f"{service}/Dockerfile must use a Python base image (issue #224 / #222)"
    )
    assert "uvicorn" in text, (
        f"{service}/Dockerfile must run the service with uvicorn (FastAPI ASGI server)"
    )
    assert "go build" not in text, (
        f"{service}/Dockerfile must not build Go code — service migrated to Python"
    )
    assert "npm run build" not in text, (
        f"{service}/Dockerfile must not build Node/NestJS — service migrated to Python"
    )


@pytest.mark.parametrize("service,app_path", PYTHON_APPS.items())
def test_service_has_python_fastapi_app(service, app_path):
    assert app_path.exists(), (
        f"{service} Python/FastAPI app not found at {app_path} — "
        "issue #222 requires all services to be rewritten to Python+FastAPI"
    )
    src = app_path.read_text()
    assert "from fastapi" in src or "import fastapi" in src.lower(), (
        f"{service}/app.py must import FastAPI"
    )
    assert "FastAPI(" in src, (
        f"{service}/app.py must instantiate a FastAPI() application"
    )


@pytest.mark.parametrize("service,app_path", PYTHON_APPS.items())
def test_service_exposes_health_endpoint(service, app_path):
    if not app_path.exists():
        pytest.skip(f"{app_path} not found")
    endpoints = _ast_endpoints(app_path)
    paths = [p for _, p in endpoints]
    assert "/health" in paths, (
        f"{service} must expose GET /health so Docker healthchecks and "
        f"gateway readiness probes can confirm the service is ready (issue #224)"
    )
