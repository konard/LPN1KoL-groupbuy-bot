"""Regression coverage for issue #216: unified compose auth routing."""

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.unified.yml"
NGINX_API_CONF = ROOT / "infrastructure" / "nginx" / "nginx-api.conf"

GATEWAY_SERVICES = (
    "gateway",
    "auth-service",
    "purchase-service",
    "payment-service",
    "chat-service",
    "notification-service",
    "analytics-service",
    "search-service",
    "reputation-service",
)


def load_unified_compose() -> dict:
    with COMPOSE.open() as f:
        return yaml.safe_load(f)


def read_nginx_api_conf() -> str:
    return NGINX_API_CONF.read_text()


def _service_build_context(service: dict) -> str:
    build = service.get("build")
    if isinstance(build, str):
        return build
    if isinstance(build, dict):
        return build.get("context", "")
    return ""


def _service_dockerfile(service: dict) -> str:
    build = service.get("build")
    if isinstance(build, dict):
        return build.get("dockerfile", "Dockerfile")
    return "Dockerfile"


class TestUnifiedNginxGatewayAuthRouting:
    """The deployed unified edge must expose gateway /api/v1/auth routes."""

    def test_unified_compose_mounts_nginx_api_conf(self):
        compose = load_unified_compose()
        volumes = compose["services"]["nginx"].get("volumes", [])

        assert any(
            "infrastructure/nginx/nginx-api.conf:/etc/nginx/nginx.conf" in v
            for v in volumes
        )

    def test_api_v1_routes_to_gateway_not_missing_backend_service(self):
        compose = load_unified_compose()
        services = compose["services"]
        conf = read_nginx_api_conf()

        assert "gateway" in services
        assert "server gateway:3000;" in conf
        assert "proxy_pass http://gateway;" in conf
        assert "backend:4000" not in conf
        assert "proxy_pass http://backend_monolith;" not in conf

    @pytest.mark.parametrize("path", ("/api/v1/auth/login", "/api/v1/auth/register"))
    def test_gateway_defines_issue_auth_routes(self, path):
        gateway_main = (ROOT / "services" / "gateway" / "main.py").read_text()

        assert f'"{path}"' in gateway_main


class TestUnifiedGatewayServicesAreFastApi:
    """Gateway-facing services in unified compose must run Python/FastAPI images."""

    @pytest.mark.parametrize("service_name", GATEWAY_SERVICES)
    def test_compose_builds_python_fastapi_service(self, service_name):
        compose = load_unified_compose()
        service = compose["services"][service_name]
        context = _service_build_context(service)
        dockerfile = ROOT / context.lstrip("./") / _service_dockerfile(service)

        assert dockerfile.exists(), f"{service_name} Dockerfile is missing: {dockerfile}"
        dockerfile_text = dockerfile.read_text().lower()
        assert "python:" in dockerfile_text, f"{service_name} must build from a Python image"
        assert "uvicorn" in dockerfile_text, f"{service_name} must run a FastAPI/ASGI app"
        assert "go build" not in dockerfile_text, f"{service_name} must not build Go code"
        assert "npm run" not in dockerfile_text, f"{service_name} must not run a Node service"
