"""Regression coverage for issue #218: Docker must route /auth/* login calls."""

import importlib
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = ROOT / "services" / "gateway"
NGINX_API_CONF = ROOT / "infrastructure" / "nginx" / "nginx-api.conf"
FRONTEND_NGINX_CONF = ROOT / "frontend-react" / "nginx.conf"


class _FakeRedis:
    async def ping(self) -> bool:
        return True

    async def incr(self, _key: str) -> int:
        return 1

    async def expire(self, _key: str, _ttl: int) -> None:
        return None

    async def exists(self, _key: str) -> int:
        return 0

    async def aclose(self) -> None:
        return None


class _StubTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return httpx.Response(200, json={"ok": True})


@pytest.fixture()
def gateway(monkeypatch):
    monkeypatch.syspath_prepend(str(GATEWAY_DIR))
    sys.modules.pop("main", None)

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("RATE_LIMIT_RPM", "100")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service:4001")

    main = importlib.import_module("main")
    transport = _StubTransport()

    async def _fake_lifespan(app):
        app.state.http = httpx.AsyncClient(transport=transport)
        app.state.redis = _FakeRedis()
        yield
        await app.state.http.aclose()

    main.app.router.lifespan_context = asynccontextmanager(_fake_lifespan)

    with TestClient(main.app) as client:
        yield client, transport

    sys.modules.pop("main", None)
    sys.path.remove(str(GATEWAY_DIR))


def test_unified_nginx_routes_legacy_auth_to_gateway():
    conf = NGINX_API_CONF.read_text()

    assert conf.count("location /auth/") >= 2, (
        "nginx-api.conf must route legacy /auth/* requests in both HTTP and HTTPS "
        "server blocks so Docker traffic does not fall through to the frontend."
    )
    assert "proxy_pass http://gateway;" in conf
    assert "proxy_pass http://frontend;" in conf


def test_frontend_container_routes_legacy_auth_to_gateway():
    conf = FRONTEND_NGINX_CONF.read_text()

    assert "location /auth/" in conf, (
        "frontend-react nginx must proxy legacy /auth/* requests to the gateway "
        "when the frontend container is accessed directly."
    )
    assert "proxy_pass $gateway_upstream;" in conf


def test_gateway_legacy_auth_login_alias_targets_auth_service(gateway):
    client, transport = gateway

    response = client.post("/auth/login", json={"phone": "+375447372111"})

    assert response.status_code == 200
    assert transport.calls, "request must reach auth-service instead of 404ing"
    assert str(transport.calls[-1].url) == "http://auth-service:4001/login"
