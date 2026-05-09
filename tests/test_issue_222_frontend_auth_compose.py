"""Regression coverage for issue #222.

The frontend-react container proxies legacy `/auth/*` requests to the FastAPI
gateway.  In compose stacks where `frontend-react`, `gateway`, and
`auth-service` run together, startup readiness must keep that proxy chain
available before the frontend is considered usable.  Otherwise browser POSTs to
`/auth/register` can fall through to a static frontend process or hit an
unready upstream.

The issue also asks that compose descriptions and service builds reflect the
current Python/FastAPI implementations under `services/`.
"""

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent

COMPOSE_WITH_AUTH_GATEWAY = (
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.light.yml",
    ROOT / "docker-compose.microservices.yml",
    ROOT / "docker-compose.unified.yml",
)

COMPOSE_WITH_FRONTEND_GATEWAY = (
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.unified.yml",
)

PYTHON_FASTAPI_SERVICE_CONTEXTS = {
    "./services/gateway",
    "./services/auth-service",
    "./services/purchase-service",
    "./services/payment-service",
    "./services/chat-service",
    "./services/notification-service",
    "./services/analytics-service",
    "./services/search-service",
    "./services/reputation-service",
}

STALE_SERVICE_DESCRIPTIONS = (
    "gateway           — Go",
    "gateway (Go",
    "auth-service (NestJS",
    "purchase-service (NestJS",
    "payment-service (Go",
    "chat-service (Go",
    "notification-service (Node.js",
    "search-service (Go",
    "reputation-service (NestJS",
    "to be migrated to Rust",
)


def _load_compose(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def _depends_on_condition(service: dict, dependency: str) -> str | None:
    depends_on = service.get("depends_on", {})
    if isinstance(depends_on, list):
        return "service_started" if dependency in depends_on else None
    if isinstance(depends_on, dict):
        value = depends_on.get(dependency)
        if isinstance(value, dict):
            return value.get("condition", "service_started")
        if value is not None:
            return "service_started"
    return None


def _build_context(service: dict) -> str:
    build = service.get("build")
    if isinstance(build, str):
        return build
    if isinstance(build, dict):
        return build.get("context", "")
    return ""


def _dockerfile_path(service: dict) -> Path:
    build = service.get("build")
    if isinstance(build, dict):
        dockerfile = build.get("dockerfile", "Dockerfile")
    else:
        dockerfile = "Dockerfile"
    return ROOT / _build_context(service).lstrip("./") / dockerfile


@pytest.mark.parametrize("compose_path", COMPOSE_WITH_AUTH_GATEWAY, ids=lambda p: p.name)
def test_auth_service_has_healthcheck_for_gateway_dependency(compose_path: Path):
    compose = _load_compose(compose_path)
    auth_service = compose["services"]["auth-service"]
    healthcheck = auth_service.get("healthcheck")

    assert healthcheck, f"{compose_path.name}: auth-service must expose a healthcheck"
    command = " ".join(str(part) for part in healthcheck.get("test", []))
    assert "localhost:4001/health" in command


@pytest.mark.parametrize("compose_path", COMPOSE_WITH_AUTH_GATEWAY, ids=lambda p: p.name)
def test_gateway_waits_for_auth_service_health(compose_path: Path):
    compose = _load_compose(compose_path)
    gateway = compose["services"]["gateway"]

    assert _depends_on_condition(gateway, "auth-service") == "service_healthy", (
        f"{compose_path.name}: gateway must wait for auth-service health before "
        "serving /auth/register proxy traffic"
    )


@pytest.mark.parametrize("compose_path", COMPOSE_WITH_FRONTEND_GATEWAY, ids=lambda p: p.name)
def test_frontend_react_waits_for_gateway_health(compose_path: Path):
    compose = _load_compose(compose_path)
    frontend = compose["services"]["frontend-react"]

    assert _depends_on_condition(frontend, "gateway") == "service_healthy", (
        f"{compose_path.name}: frontend-react proxies /auth/* to gateway and "
        "must not become ready before the gateway is healthy"
    )


def test_unified_public_nginx_waits_for_gateway_health():
    compose = _load_compose(ROOT / "docker-compose.unified.yml")
    nginx = compose["services"]["nginx"]

    assert _depends_on_condition(nginx, "gateway") == "service_healthy"


@pytest.mark.parametrize("compose_path", sorted(ROOT.glob("docker-compose*.yml")), ids=lambda p: p.name)
def test_services_directory_builds_use_python_fastapi_dockerfiles(compose_path: Path):
    compose = _load_compose(compose_path)

    for service_name, service in compose.get("services", {}).items():
        context = _build_context(service)
        if context not in PYTHON_FASTAPI_SERVICE_CONTEXTS:
            continue

        dockerfile = _dockerfile_path(service)
        text = dockerfile.read_text().lower()

        assert "python:" in text, f"{compose_path.name}:{service_name} must build from Python"
        assert "uvicorn" in text, f"{compose_path.name}:{service_name} must run ASGI/FastAPI"
        assert "go build" not in text, f"{compose_path.name}:{service_name} must not build Go"
        assert "npm run" not in text, f"{compose_path.name}:{service_name} must not run Node"


@pytest.mark.parametrize("compose_path", sorted(ROOT.glob("docker-compose*.yml")), ids=lambda p: p.name)
def test_compose_descriptions_do_not_claim_services_are_legacy_runtimes(compose_path: Path):
    text = compose_path.read_text()
    stale = [snippet for snippet in STALE_SERVICE_DESCRIPTIONS if snippet in text]

    assert not stale, (
        f"{compose_path.name} has stale service runtime descriptions: "
        + ", ".join(stale)
    )
