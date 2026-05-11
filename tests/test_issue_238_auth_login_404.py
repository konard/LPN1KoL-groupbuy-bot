"""Regression tests for issue #238: POST /api/v1/auth/login returns 404.

Root cause: the deployed gateway sent the full path /auth/login to auth-service
instead of stripping the service prefix and sending just /login. NestJS handles
only POST /login (no controller prefix), so it returned:
  {"status": 404, "code": "NOT_FOUND", "message": "Cannot POST /auth/login"}

Fixes:
1. services/gateway/main.py — already had named routes that send the correct
   stripped path; verified here.
2. gateway/main.py — added /auth/{path:path} legacy route and OTP endpoints
   (login/confirm, register/confirm, resend-code) + expanded PUBLIC_PATHS.
3. docker-compose.unified.yml — added JWT_EXPIRES_IN_SECONDS / JWT_REFRESH_EXPIRES_IN_SECONDS
   so app.py picks up the correct token TTL (it reads *_SECONDS, not the *_IN form).
"""

import importlib
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = ROOT / "services" / "gateway"
OLD_GATEWAY_DIR = ROOT / "gateway"
JWT_SECRET = "test-secret"


# ─── Shared stubs ─────────────────────────────────────────────────────────────


class _FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.blacklisted: set[str] = set()

    async def ping(self) -> bool:
        return True

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def exists(self, key: str) -> int:
        return int(key.removeprefix("jwt:blacklist:") in self.blacklisted)

    async def aclose(self) -> None:
        return None


class _StubTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"content-type": "application/json"},
        )


def _make_client(gateway_dir: Path, monkeypatch):
    monkeypatch.syspath_prepend(str(gateway_dir))
    sys.modules.pop("main", None)

    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("RATE_LIMIT_RPM", "100")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:4001")
    monkeypatch.setenv("PURCHASE_SERVICE_URL", "http://purchase-service:4002")
    monkeypatch.setenv("PAYMENT_SERVICE_URL", "http://payment-service:4003")
    monkeypatch.setenv("CHAT_SERVICE_URL", "http://chat-service:4004")
    monkeypatch.setenv("SEARCH_SERVICE_URL", "http://search-service:4007")
    monkeypatch.setenv("REPUTATION_SERVICE_URL", "http://reputation-service:4008")

    main = importlib.import_module("main")
    fake_redis = _FakeRedis()
    stub_transport = _StubTransport()

    async def _fake_lifespan(app):
        app.state.http = httpx.AsyncClient(transport=stub_transport)
        app.state.redis = fake_redis
        yield
        await app.state.http.aclose()

    main.app.router.lifespan_context = asynccontextmanager(_fake_lifespan)
    return main, fake_redis, stub_transport


@pytest.fixture()
def services_gateway(monkeypatch):
    main, fake_redis, stub_transport = _make_client(GATEWAY_DIR, monkeypatch)
    with TestClient(main.app) as client:
        yield client, fake_redis, stub_transport
    sys.modules.pop("main", None)
    sys.path.remove(str(GATEWAY_DIR))


@pytest.fixture()
def old_gateway(monkeypatch):
    main, fake_redis, stub_transport = _make_client(OLD_GATEWAY_DIR, monkeypatch)
    with TestClient(main.app) as client:
        yield client, fake_redis, stub_transport
    sys.modules.pop("main", None)
    sys.path.remove(str(OLD_GATEWAY_DIR))


def _bearer(payload: dict[str, Any]) -> dict[str, str]:
    from jose import jwt

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


# ─── Static source checks ─────────────────────────────────────────────────────


class TestGatewaySourceRoutingContract:
    """Verify source-level invariants that prevent the issue-238 regression."""

    def test_services_gateway_sends_login_not_auth_login_to_auth_service(self):
        source = (GATEWAY_DIR / "main.py").read_text()
        assert '_proxy_request(request, "auth", "login")' in source, (
            "services/gateway/main.py must call _proxy_request with path='login' "
            "so auth-service receives POST /login, not POST /auth/login."
        )

    def test_services_gateway_has_legacy_auth_route(self):
        source = (GATEWAY_DIR / "main.py").read_text()
        assert '"/auth/{path:path}"' in source, (
            "services/gateway/main.py must expose /auth/{path:path} so nginx's "
            "location /auth/ block reaches auth-service correctly."
        )

    def test_services_gateway_public_paths_include_otp_endpoints(self):
        source = (GATEWAY_DIR / "main.py").read_text()
        assert '"auth/login/confirm"' in source
        assert '"auth/register/confirm"' in source
        assert '"auth/resend-code"' in source

    def test_old_gateway_sends_login_not_auth_login_to_auth_service(self):
        source = (OLD_GATEWAY_DIR / "main.py").read_text()
        assert '_proxy_request(request, "auth", "login")' in source, (
            "gateway/main.py must call _proxy_request with path='login'."
        )

    def test_old_gateway_has_legacy_auth_route(self):
        source = (OLD_GATEWAY_DIR / "main.py").read_text()
        assert '"/auth/{path:path}"' in source, (
            "gateway/main.py must expose /auth/{path:path} legacy route."
        )

    def test_old_gateway_public_paths_include_otp_endpoints(self):
        source = (OLD_GATEWAY_DIR / "main.py").read_text()
        assert '"auth/login/confirm"' in source
        assert '"auth/register/confirm"' in source
        assert '"auth/resend-code"' in source

    def test_compose_auth_service_has_seconds_env_vars(self):
        with open(ROOT / "docker-compose.unified.yml") as f:
            compose = yaml.safe_load(f)
        env = compose["services"]["auth-service"]["environment"]
        assert "JWT_EXPIRES_IN_SECONDS" in env, (
            "docker-compose.unified.yml must set JWT_EXPIRES_IN_SECONDS because "
            "services/auth-service/app.py reads JWT_EXPIRES_IN_SECONDS, not JWT_EXPIRES_IN."
        )
        assert "JWT_REFRESH_EXPIRES_IN_SECONDS" in env, (
            "docker-compose.unified.yml must set JWT_REFRESH_EXPIRES_IN_SECONDS because "
            "services/auth-service/app.py reads JWT_REFRESH_EXPIRES_IN_SECONDS."
        )


# ─── Functional tests: services/gateway ───────────────────────────────────────


class TestServicesGatewayAuthRouting:
    """Ensure the deployed (services/gateway) gateway strips the service prefix."""

    def test_api_v1_auth_login_strips_prefix_and_sends_login_to_auth(self, services_gateway):
        client, _redis, transport = services_gateway
        response = client.post("/api/v1/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login", (
            "Gateway must forward POST /api/v1/auth/login to http://auth-service:4001/login, "
            "not to http://auth-service:4001/auth/login."
        )

    def test_legacy_auth_login_strips_prefix_and_sends_login_to_auth(self, services_gateway):
        client, _redis, transport = services_gateway
        response = client.post("/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login", (
            "Gateway must forward POST /auth/login to http://auth-service:4001/login, "
            "not to http://auth-service:4001/auth/login."
        )

    def test_auth_login_confirm_is_public_and_routed_correctly(self, services_gateway):
        client, _redis, transport = services_gateway
        response = client.post("/api/v1/auth/login/confirm", json={"code": "1234"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login/confirm"

    def test_auth_register_confirm_is_public_and_routed_correctly(self, services_gateway):
        client, _redis, transport = services_gateway
        response = client.post("/api/v1/auth/register/confirm", json={"code": "5678"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/register/confirm"

    def test_auth_resend_code_is_public_and_routed_correctly(self, services_gateway):
        client, _redis, transport = services_gateway
        response = client.post("/api/v1/auth/resend-code", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/resend-code"


# ─── Functional tests: old gateway ────────────────────────────────────────────


class TestOldGatewayAuthRouting:
    """Ensure gateway/main.py (used in non-unified setups) has the same correct routing."""

    def test_api_v1_auth_login_strips_prefix_and_sends_login_to_auth(self, old_gateway):
        client, _redis, transport = old_gateway
        response = client.post("/api/v1/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login"

    def test_legacy_auth_login_strips_prefix_and_sends_login_to_auth(self, old_gateway):
        client, _redis, transport = old_gateway
        response = client.post("/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login"

    def test_auth_login_confirm_is_public_and_routed_correctly(self, old_gateway):
        client, _redis, transport = old_gateway
        response = client.post("/api/v1/auth/login/confirm", json={"code": "1234"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login/confirm"

    def test_auth_register_confirm_is_public_and_routed_correctly(self, old_gateway):
        client, _redis, transport = old_gateway
        response = client.post("/api/v1/auth/register/confirm", json={"code": "5678"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/register/confirm"

    def test_auth_resend_code_is_public_and_routed_correctly(self, old_gateway):
        client, _redis, transport = old_gateway
        response = client.post("/api/v1/auth/resend-code", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/resend-code"
