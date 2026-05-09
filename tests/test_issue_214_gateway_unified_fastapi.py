"""Regression tests for issue #214: unified-compose gateway FastAPI rewrite."""

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
JWT_SECRET = "test-secret"


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


@pytest.fixture()
def gateway(monkeypatch):
    monkeypatch.syspath_prepend(str(GATEWAY_DIR))
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

    with TestClient(main.app) as client:
        yield client, fake_redis, stub_transport

    sys.modules.pop("main", None)
    sys.path.remove(str(GATEWAY_DIR))


def _bearer(payload: dict[str, Any]) -> tuple[str, dict[str, str]]:
    from jose import jwt

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token, {"Authorization": f"Bearer {token}"}


class TestUnifiedComposeGatewayService:
    @pytest.fixture(scope="class")
    def gateway_service(self):
        with open(ROOT / "docker-compose.unified.yml") as f:
            return yaml.safe_load(f)["services"]["gateway"]

    def test_builds_the_python_fastapi_gateway(self, gateway_service):
        assert gateway_service["build"]["context"] == "./services/gateway"
        assert gateway_service["ports"] == ["3000:3000"]
        assert gateway_service["environment"]["PORT"] == 3000
        assert gateway_service["environment"]["AUTH_SERVICE_URL"] == "http://auth-service:4001"
        assert (
            gateway_service["environment"]["PAYMENT_SERVICE_URL"]
            == "http://payment-service:4003"
        )

    def test_compose_healthcheck_hits_gateway_health_endpoint(self, gateway_service):
        healthcheck = gateway_service.get("healthcheck", {})
        test_cmd = " ".join(str(part) for part in healthcheck.get("test", []))
        assert "http://localhost:3000/health" in test_cmd
        assert healthcheck.get("retries", 0) >= 3


class TestGatewayDockerImage:
    def test_dockerfile_runs_fastapi_not_go(self):
        dockerfile = (GATEWAY_DIR / "Dockerfile").read_text()
        assert "python:3.12-slim" in dockerfile
        assert "uvicorn" in dockerfile
        assert "main:app" in dockerfile
        assert "go build" not in dockerfile.lower()

    def test_dockerfile_has_runtime_healthcheck(self):
        dockerfile = (GATEWAY_DIR / "Dockerfile").read_text()
        assert "HEALTHCHECK" in dockerfile
        assert "http://localhost:3000/health" in dockerfile

    def test_stale_go_gateway_sources_removed(self):
        assert not (GATEWAY_DIR / "main.go").exists()
        assert not (GATEWAY_DIR / "go.mod").exists()
        assert not (GATEWAY_DIR / "go.sum").exists()


class TestGatewayProxyCompatibility:
    def test_auth_login_stays_public_and_targets_auth_service_root(self, gateway):
        client, _redis, transport = gateway
        response = client.post("/api/v1/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login"

    def test_legacy_auth_login_alias_stays_public_and_targets_auth_service_root(
        self, gateway
    ):
        client, _redis, transport = gateway
        response = client.post("/auth/login", json={"phone": "+79001234567"})
        assert response.status_code == 200
        assert str(transport.calls[-1].url) == "http://auth-service:4001/login"

    def test_payment_legacy_wallet_alias_is_preserved(self, gateway):
        client, _redis, transport = gateway
        _token, headers = _bearer(
            {"sub": "user-42", "email": "u@example.com", "role": "buyer"}
        )
        response = client.get("/api/v1/wallets/me?currency=RUB", headers=headers)
        assert response.status_code == 200
        assert (
            str(transport.calls[-1].url)
            == "http://payment-service:4003/wallets/me?currency=RUB"
        )

    def test_payment_webhooks_do_not_require_jwt(self, gateway):
        client, _redis, transport = gateway
        response = client.post(
            "/webhooks/yookassa/payment",
            json={"event": "payment.succeeded"},
        )
        assert response.status_code == 200
        assert (
            str(transport.calls[-1].url)
            == "http://payment-service:4003/yookassa/payment"
        )

    def test_authenticated_requests_forward_full_user_context(self, gateway):
        client, _redis, transport = gateway
        _token, headers = _bearer(
            {"sub": "user-42", "email": "u@example.com", "role": "organizer"}
        )
        response = client.get("/api/v1/purchases", headers=headers)
        assert response.status_code == 200
        upstream = transport.calls[-1]
        assert upstream.headers["x-user-id"] == "user-42"
        assert upstream.headers["x-user-email"] == "u@example.com"
        assert upstream.headers["x-user-role"] == "organizer"

    def test_blacklisted_jwt_is_rejected_before_proxying(self, gateway):
        client, redis, transport = gateway
        token, headers = _bearer({"sub": "blocked-user", "role": "buyer"})
        redis.blacklisted.add(token)

        response = client.get("/api/v1/purchases", headers=headers)

        assert response.status_code == 401
        assert transport.calls == []
