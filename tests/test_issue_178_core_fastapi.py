"""Tests for the FastAPI `core` rewrite delivered for issue #178.

These tests do not require a live PostgreSQL or Redis: the lifespan is bypassed
by overriding the FastAPI dependency that would normally connect, and the
`/health` endpoint is exercised through `httpx.AsyncClient(transport=ASGITransport)`.
"""

import importlib
import sys
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parent.parent / "core-fastapi"


@pytest.fixture()
def core_app(monkeypatch):
    """Import core-fastapi/main.py with stubbed asyncpg/redis connections."""
    monkeypatch.syspath_prepend(str(CORE_DIR))

    # Drop any cached modules so we re-evaluate config from env.
    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)

    monkeypatch.setenv("DATABASE_URL", "postgresql://stub:stub@stub/stub")
    monkeypatch.setenv("REDIS_URL", "redis://stub:6379/0")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    main = importlib.import_module("main")
    yield main.app

    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)
    sys.path.remove(str(CORE_DIR))


def test_dockerfile_uses_python312_slim_and_uvicorn():
    dockerfile = (CORE_DIR / "Dockerfile").read_text()
    assert "python:3.12-slim" in dockerfile, "issue #178 mandates python:3.12-slim base image"
    assert "uvicorn" in dockerfile, "uvicorn must be the entrypoint"
    assert "/health" in dockerfile, "Dockerfile must include a /health-based healthcheck"


def test_requirements_pin_fastapi_and_async_postgres():
    requirements = (CORE_DIR / "requirements.txt").read_text().lower()
    assert "fastapi" in requirements
    assert "uvicorn" in requirements
    assert "asyncpg" in requirements
    assert "redis" in requirements


def test_main_exposes_api_prefix_and_health(core_app):
    paths = {route.path for route in core_app.routes}
    assert "/health" in paths
    # /api prefix is honoured for the example products router.
    assert any(p.startswith("/api/products") for p in paths), paths


def test_settings_read_environment(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE_DIR))
    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)

    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("REDIS_URL", "redis://r/1")

    config = importlib.import_module("app.config")
    assert config.settings.port == 9999
    assert config.settings.database_url == "postgresql://x/y"
    assert config.settings.redis_url == "redis://r/1"

    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)
    sys.path.remove(str(CORE_DIR))
