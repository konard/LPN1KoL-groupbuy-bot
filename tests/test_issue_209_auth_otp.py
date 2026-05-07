"""
Tests for issue #209: authentication for personal cabinet (личный кабинет).

The issue reports that POST api/v1/auth/login returns 422.
Root causes identified:
  1. notification-service/app.py is missing POST /internal/send-otp endpoint,
     which auth-service calls to deliver OTP codes by email.
  2. gateway/main.py is missing PUBLIC_PATHS entries and route handlers for
     auth/login/confirm, auth/register/confirm, and auth/resend-code.

This test suite verifies both fixes are in place.
"""
import importlib
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = ROOT / "services" / "gateway"
NOTIF_APP = ROOT / "services" / "notification-service" / "app.py"

JWT_SECRET = "test-secret"


def read_file(relpath: str) -> str:
    with open(ROOT / relpath) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Notification service: /internal/send-otp endpoint
# ---------------------------------------------------------------------------

class TestNotificationServiceSendOtpEndpoint:
    """
    auth-service calls POST /internal/send-otp on the notification-service to
    deliver OTP verification codes by email.  This endpoint was missing, which
    caused the auth flow to silently fail to send emails.
    """

    def test_send_otp_endpoint_defined(self):
        src = NOTIF_APP.read_text()
        assert "/internal/send-otp" in src, (
            "notification-service/app.py must expose POST /internal/send-otp "
            "so auth-service can trigger OTP email delivery (issue #209)."
        )

    def test_send_otp_accepts_email_and_otp(self):
        src = NOTIF_APP.read_text()
        assert "email" in src and "otp" in src, (
            "The /internal/send-otp handler must accept 'email' and 'otp' fields "
            "(issue #209)."
        )

    def test_send_otp_calls_send_email(self):
        src = NOTIF_APP.read_text()
        # The handler should call the existing _send_email helper
        assert "_send_email" in src, (
            "The /internal/send-otp handler must call _send_email() to deliver the "
            "OTP code (issue #209)."
        )

    def test_send_otp_uses_context_field(self):
        src = NOTIF_APP.read_text()
        # context distinguishes 'login' from 'registration' subject lines
        assert "context" in src, (
            "The /internal/send-otp handler must accept a 'context' field "
            "('login' or 'registration') to set the correct email subject (issue #209)."
        )

    def test_send_otp_returns_success(self):
        src = NOTIF_APP.read_text()
        assert '"success"' in src or "'success'" in src, (
            "The /internal/send-otp handler must return {success: True} on success "
            "(issue #209)."
        )

    def test_send_otp_pydantic_model_defined(self):
        src = NOTIF_APP.read_text()
        assert "SendOtpRequest" in src, (
            "notification-service/app.py must define a SendOtpRequest Pydantic model "
            "for the /internal/send-otp endpoint (issue #209)."
        )


# ---------------------------------------------------------------------------
# Gateway: public paths include OTP confirmation endpoints
# ---------------------------------------------------------------------------

class TestGatewayPublicPaths:
    """
    auth/login/confirm, auth/register/confirm, and auth/resend-code must be
    listed in PUBLIC_PATHS so unauthenticated users can complete the OTP flow
    without being rejected by the JWT guard.
    """

    GATEWAY_PATH = "services/gateway/main.py"

    def test_login_confirm_is_public(self):
        src = read_file(self.GATEWAY_PATH)
        assert "auth/login/confirm" in src, (
            f"{self.GATEWAY_PATH}: 'auth/login/confirm' must be in PUBLIC_PATHS so "
            "users can complete OTP login without a JWT token (issue #209)."
        )

    def test_register_confirm_is_public(self):
        src = read_file(self.GATEWAY_PATH)
        assert "auth/register/confirm" in src, (
            f"{self.GATEWAY_PATH}: 'auth/register/confirm' must be in PUBLIC_PATHS "
            "so users can complete OTP registration without a JWT token (issue #209)."
        )

    def test_resend_code_is_public(self):
        src = read_file(self.GATEWAY_PATH)
        assert "auth/resend-code" in src, (
            f"{self.GATEWAY_PATH}: 'auth/resend-code' must be in PUBLIC_PATHS so "
            "users can request a new OTP without a JWT token (issue #209)."
        )


# ---------------------------------------------------------------------------
# Gateway: route handlers for OTP confirmation endpoints
# ---------------------------------------------------------------------------

class TestGatewayAuthRouteHandlers:
    """
    The gateway must expose route handlers that proxy the OTP confirmation
    endpoints to the auth-service.
    """

    GATEWAY_PATH = "services/gateway/main.py"

    def test_login_confirm_route_handler(self):
        src = read_file(self.GATEWAY_PATH)
        assert "/api/v1/auth/login/confirm" in src, (
            f"{self.GATEWAY_PATH}: must have a POST /api/v1/auth/login/confirm route "
            "handler that proxies requests to auth-service (issue #209)."
        )

    def test_register_confirm_route_handler(self):
        src = read_file(self.GATEWAY_PATH)
        assert "/api/v1/auth/register/confirm" in src, (
            f"{self.GATEWAY_PATH}: must have a POST /api/v1/auth/register/confirm route "
            "handler that proxies requests to auth-service (issue #209)."
        )

    def test_resend_code_route_handler(self):
        src = read_file(self.GATEWAY_PATH)
        assert "/api/v1/auth/resend-code" in src, (
            f"{self.GATEWAY_PATH}: must have a POST /api/v1/auth/resend-code route "
            "handler that proxies requests to auth-service (issue #209)."
        )


# ---------------------------------------------------------------------------
# Gateway integration: OTP endpoints bypass JWT, reach upstream
# ---------------------------------------------------------------------------

class _FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def ping(self) -> bool:
        return True

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _StubTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(
            200,
            json={"success": True},
            headers={"content-type": "application/json"},
        )


@pytest.fixture()
def gateway(monkeypatch):
    monkeypatch.syspath_prepend(str(GATEWAY_DIR))
    sys.modules.pop("main", None)

    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("RATE_LIMIT_RPM", "100")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:4001")

    main = importlib.import_module("main")

    fake_redis = _FakeRedis()
    stub_transport = _StubTransport()

    async def _fake_lifespan(app):
        app.state.http = httpx.AsyncClient(transport=stub_transport)
        app.state.redis = fake_redis
        yield
        await app.state.http.aclose()

    from contextlib import asynccontextmanager
    main.app.router.lifespan_context = asynccontextmanager(_fake_lifespan)

    with TestClient(main.app) as client:
        yield client, fake_redis, stub_transport, main

    sys.modules.pop("main", None)
    sys.path.remove(str(GATEWAY_DIR))


class TestGatewayOtpEndpointsIntegration:
    """Integration tests: OTP flow endpoints reach upstream without JWT."""

    def test_login_confirm_bypasses_jwt_check(self, gateway):
        client, _redis, transport, _ = gateway
        response = client.post(
            "/api/v1/auth/login/confirm",
            json={"phone": "+79001234567", "otp": "123456"},
        )
        assert response.status_code != 401, (
            "POST /api/v1/auth/login/confirm must not require a JWT token — "
            "the user has no token yet when confirming OTP (issue #209)."
        )
        assert transport.calls, "request must reach the upstream auth-service"
        upstream = transport.calls[-1]
        assert "login/confirm" in str(upstream.url), (
            f"upstream URL should contain 'login/confirm', got {upstream.url}"
        )

    def test_register_confirm_bypasses_jwt_check(self, gateway):
        client, _redis, transport, _ = gateway
        response = client.post(
            "/api/v1/auth/register/confirm",
            json={"phone": "+79001234567", "otp": "654321"},
        )
        assert response.status_code != 401, (
            "POST /api/v1/auth/register/confirm must not require a JWT token (issue #209)."
        )
        assert transport.calls
        upstream = transport.calls[-1]
        assert "register/confirm" in str(upstream.url)

    def test_resend_code_bypasses_jwt_check(self, gateway):
        client, _redis, transport, _ = gateway
        response = client.post(
            "/api/v1/auth/resend-code",
            json={"phone": "+79001234567", "context": "login"},
        )
        assert response.status_code != 401, (
            "POST /api/v1/auth/resend-code must not require a JWT token (issue #209)."
        )
        assert transport.calls
        upstream = transport.calls[-1]
        assert "resend-code" in str(upstream.url)

    def test_login_still_bypasses_jwt_check(self, gateway):
        """Regression: original login endpoint must still be public."""
        client, _redis, transport, _ = gateway
        response = client.post(
            "/api/v1/auth/login",
            json={"phone": "+79001234567"},
        )
        assert response.status_code != 401, (
            "POST /api/v1/auth/login must remain public after the fix (issue #209)."
        )


# ---------------------------------------------------------------------------
# Notification service integration: /internal/send-otp works end-to-end
# ---------------------------------------------------------------------------

class TestNotificationSendOtpIntegration:
    """
    Import notification-service app and verify the /internal/send-otp endpoint
    is reachable and returns {success: True} (email sending is skipped when
    SMTP_USER is unset).
    """

    @pytest.fixture()
    def notif_client(self, monkeypatch):
        notif_dir = str(ROOT / "services" / "notification-service")
        monkeypatch.syspath_prepend(notif_dir)
        sys.modules.pop("app", None)

        monkeypatch.setenv("SMTP_USER", "")  # Disable actual SMTP
        monkeypatch.setenv("KAFKA_BROKERS", "localhost:9092")

        import app as notif_app

        # Override lifespan to avoid starting the Kafka consumer
        from contextlib import asynccontextmanager

        async def _noop_lifespan(application):
            yield

        notif_app.app.router.lifespan_context = asynccontextmanager(_noop_lifespan)

        from starlette.testclient import TestClient
        with TestClient(notif_app.app) as client:
            yield client

        sys.modules.pop("app", None)
        sys.path.remove(notif_dir)

    def test_send_otp_login_returns_success(self, notif_client):
        response = notif_client.post(
            "/internal/send-otp",
            json={"email": "user@example.com", "otp": "123456", "context": "login"},
        )
        assert response.status_code == 200, (
            f"POST /internal/send-otp returned {response.status_code}: {response.text}"
        )
        assert response.json().get("success") is True

    def test_send_otp_registration_returns_success(self, notif_client):
        response = notif_client.post(
            "/internal/send-otp",
            json={"email": "new@example.com", "otp": "654321", "context": "registration"},
        )
        assert response.status_code == 200
        assert response.json().get("success") is True

    def test_send_otp_accepts_subject_override(self, notif_client):
        response = notif_client.post(
            "/internal/send-otp",
            json={
                "email": "test@example.com",
                "otp": "111222",
                "subject": "Custom subject",
                "context": "login",
            },
        )
        assert response.status_code == 200
        assert response.json().get("success") is True

    def test_send_otp_requires_email(self, notif_client):
        response = notif_client.post(
            "/internal/send-otp",
            json={"otp": "123456", "context": "login"},
        )
        assert response.status_code == 422, (
            "Missing 'email' field must return HTTP 422 Unprocessable Entity."
        )

    def test_send_otp_requires_otp(self, notif_client):
        response = notif_client.post(
            "/internal/send-otp",
            json={"email": "user@example.com", "context": "login"},
        )
        assert response.status_code == 422, (
            "Missing 'otp' field must return HTTP 422 Unprocessable Entity."
        )
