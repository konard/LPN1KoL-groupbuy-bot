"""Regression coverage for issue #236: unified stack must be Python/FastAPI.

The microservices had already been rewritten to Python in earlier issues, but
``docker-compose.unified.yml`` still used the Rust core service and omitted
healthchecks for several FastAPI services.  This suite keeps the unified stack
aligned with the Python/FastAPI implementation that ``docker compose -f
docker-compose.unified.yml up --build`` should run.
"""

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.unified.yml"

FASTAPI_SERVICES = {
    "core": ("./core-fastapi", "Dockerfile", 8000),
    "gateway": ("./services/gateway", "Dockerfile", 3000),
    "auth-service": ("./services/auth-service", "Dockerfile", 4001),
    "purchase-service": ("./services/purchase-service", "Dockerfile", 4002),
    "payment-service": ("./services/payment-service", "Dockerfile", 4003),
    "chat-service": ("./services/chat-service", "Dockerfile", 4004),
    "notification-service": ("./services/notification-service", "Dockerfile", 4005),
    "analytics-service": ("./services/analytics-service", "Dockerfile", 4006),
    "search-service": ("./services/search-service", "Dockerfile", 4007),
    "reputation-service": ("./services/reputation-service", "Dockerfile", 4008),
}

STALE_RUNTIME_SNIPPETS = (
    "Gateway | Go",
    "Auth | NestJS",
    "Purchase | NestJS",
    "Payment | Go",
    "Chat | Go",
    "Notification | Node.js",
    "Search | Go",
    "Reputation | NestJS",
    "Core API (Rust)",
    "Go Microservices",
)


def _load_compose() -> dict:
    with COMPOSE.open() as f:
        return yaml.safe_load(f)


def _build_context(service: dict) -> str:
    build = service.get("build")
    if isinstance(build, str):
        return build
    if isinstance(build, dict):
        return build.get("context", "")
    return ""


def _dockerfile_name(service: dict) -> str:
    build = service.get("build")
    if isinstance(build, dict):
        return build.get("dockerfile", "Dockerfile")
    return "Dockerfile"


@pytest.mark.parametrize("service_name,expected", FASTAPI_SERVICES.items())
def test_unified_service_builds_fastapi_runtime(service_name: str, expected: tuple[str, str, int]):
    expected_context, expected_dockerfile, _port = expected
    service = _load_compose()["services"][service_name]

    assert _build_context(service) == expected_context
    assert _dockerfile_name(service) == expected_dockerfile

    dockerfile = ROOT / expected_context.lstrip("./") / expected_dockerfile
    dockerfile_text = dockerfile.read_text().lower()
    assert "python:3.11-slim" in dockerfile_text
    assert "uvicorn" in dockerfile_text
    assert "go build" not in dockerfile_text
    assert "npm run" not in dockerfile_text


@pytest.mark.parametrize("service_name,expected", FASTAPI_SERVICES.items())
def test_unified_fastapi_services_have_healthchecks(service_name: str, expected: tuple[str, str, int]):
    _context, _dockerfile, port = expected
    service = _load_compose()["services"][service_name]
    healthcheck = service.get("healthcheck")

    assert healthcheck, f"{service_name} must define a compose healthcheck"
    command = " ".join(str(part) for part in healthcheck.get("test", []))
    assert f"http://localhost:{port}/health" in command
    assert healthcheck.get("retries", 0) >= 3


def test_unified_core_no_longer_uses_rust_configuration():
    core = _load_compose()["services"]["core"]
    env = core.get("environment", [])
    env_text = "\n".join(env) if isinstance(env, list) else "\n".join(f"{k}={v}" for k, v in env.items())

    assert "core-rust" not in _build_context(core)
    assert "RUST_LOG" not in env_text
    assert "LOG_LEVEL" in env_text
    assert "JWT_SECRET" in env_text


@pytest.mark.parametrize("path", (ROOT / "README.md", ROOT / "CLAUDE.md"))
def test_docs_describe_python_fastapi_stack(path: Path):
    text = path.read_text()
    stale = [snippet for snippet in STALE_RUNTIME_SNIPPETS if snippet in text]

    assert "Python + FastAPI" in text
    assert not stale, f"{path.name} still contains stale runtime descriptions: {stale}"
