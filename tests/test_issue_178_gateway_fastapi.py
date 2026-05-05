"""Tests for the FastAPI `gateway` rewrite delivered for issue #178."""

import importlib
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

GATEWAY_DIR = Path(__file__).resolve().parent.parent / "gateway"

JWT_SECRET = "test-secret"


class _FakeRedis:
    """In-memory replacement for `redis.asyncio.Redis` (the calls we use)."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def ping(self) -> bool:  # pragma: no cover - lifespan path
        return True

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        return None

    async def aclose(self) -> None:  # pragma: no cover - lifespan path
        return None


class _StubTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(
            200,
            json={"echoed": str(request.url), "method": request.method},
            headers={"content-type": "application/json"},
        )


@pytest.fixture()
def gateway(monkeypatch):
    """Import the gateway with a stub Redis and stub upstream HTTP transport."""
    monkeypatch.syspath_prepend(str(GATEWAY_DIR))
    sys.modules.pop("main", None)

    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("RATE_LIMIT_RPM", "3")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:4001")
    monkeypatch.setenv("PURCHASE_SERVICE_URL", "http://purchase-service:4002")

    main = importlib.import_module("main")

    fake_redis = _FakeRedis()
    stub_transport = _StubTransport()

    async def _fake_lifespan(app):
        app.state.http = httpx.AsyncClient(transport=stub_transport)
        app.state.redis = fake_redis
        yield
        await app.state.http.aclose()

    # Replace the registered lifespan with our stub.
    from contextlib import asynccontextmanager

    main.app.router.lifespan_context = asynccontextmanager(_fake_lifespan)

    with TestClient(main.app) as client:
        yield client, fake_redis, stub_transport, main

    sys.modules.pop("main", None)
    sys.path.remove(str(GATEWAY_DIR))


def _bearer(payload: dict[str, Any]) -> dict[str, str]:
    from jose import jwt

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_dockerfile_pins_python312_and_port_3000():
    dockerfile = (GATEWAY_DIR / "Dockerfile").read_text()
    assert "python:3.12-slim" in dockerfile
    assert "EXPOSE 3000" in dockerfile
    assert "uvicorn" in dockerfile


def test_requirements_pin_required_dependencies():
    deps = (GATEWAY_DIR / "requirements.txt").read_text().lower()
    for required in ("fastapi", "uvicorn", "httpx", "redis", "python-jose"):
        assert required in deps, f"missing dependency: {required}"


def test_health_is_open(gateway):
    client, *_ = gateway
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gateway"}


def test_proxy_requires_jwt(gateway):
    client, _redis, transport, _ = gateway
    response = client.get("/api/v1/purchases/items")
    assert response.status_code == 401
    assert transport.calls == []


def test_public_auth_login_bypasses_jwt(gateway):
    client, _redis, transport, _ = gateway
    response = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "p"})
    assert response.status_code == 200
    assert transport.calls, "expected the request to reach the upstream auth service"
    upstream = transport.calls[-1]
    assert str(upstream.url).startswith("http://auth-service:4001/login")


def test_authenticated_request_proxies_with_user_headers(gateway):
    client, _redis, transport, _ = gateway
    headers = _bearer({"sub": "user-42", "role": "organizer"})
    response = client.get("/api/v1/purchases/items?page=2", headers=headers)
    assert response.status_code == 200
    upstream = transport.calls[-1]
    assert str(upstream.url) == "http://purchase-service:4002/items?page=2"
    assert upstream.headers.get("x-user-id") == "user-42"
    assert upstream.headers.get("x-user-role") == "organizer"


def test_unknown_service_returns_404(gateway):
    client, *_ = gateway
    headers = _bearer({"sub": "u"})
    response = client.get("/api/v1/does-not-exist/foo", headers=headers)
    assert response.status_code == 404


def test_rate_limit_enforced(gateway):
    client, _redis, _transport, _main = gateway
    headers = _bearer({"sub": "user-rate-limit-test"})
    statuses = [
        client.get("/api/v1/purchases/items", headers=headers).status_code for _ in range(5)
    ]
    # RATE_LIMIT_RPM=3 → first three pass, the next ones are 429.
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_invalid_jwt_is_rejected(gateway):
    client, *_ = gateway
    response = client.get(
        "/api/v1/purchases/items", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
