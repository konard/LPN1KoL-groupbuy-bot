"""
Regression tests for issue #131.

The monolith deployment must:

1. accept registration passwords without schema-level validation;
2. start nginx without relying on a bind-mounted custom entrypoint script;
3. run the same production React frontend used by docker-compose.unified.yml
   for both the personal account (/lk) and admin panel (/admin-panel).
"""

import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).parent.parent
COMPOSE_MONOLITH = ROOT / "docker-compose.monolith.yml"
NGINX_MONOLITH_CONF = ROOT / "infrastructure" / "nginx" / "nginx-monolith.conf"

sys.path.insert(0, str(ROOT / "backend-monolith"))


def _load_compose() -> dict:
    with open(COMPOSE_MONOLITH) as f:
        return yaml.safe_load(f)


def _env_dict(service: dict) -> dict[str, str]:
    env = service.get("environment", {})
    if isinstance(env, list):
        result = {}
        for item in env:
            if "=" in item:
                key, value = item.split("=", 1)
                result[key] = value
        return result
    return {str(key): str(value) for key, value in env.items()}


class TestRegistrationPasswordValidationRemoved:
    """RegisterRequest must not reject passwords based on length."""

    def _payload(self, password: str) -> dict:
        return {"email": "user@example.com", "password": password, "role": "buyer"}

    def test_empty_password_is_accepted_by_registration_schema(self):
        from app.modules.auth.schemas import RegisterRequest

        req = RegisterRequest(**self._payload(""))
        assert req.password == ""

    def test_register_openapi_has_no_password_min_length(self):
        from fastapi import FastAPI
        from app.modules.auth import schemas

        app = FastAPI()

        @app.post("/auth/register", response_model=schemas.UserOut)
        def register(req: schemas.RegisterRequest):
            ...

        props = app.openapi()["components"]["schemas"]["RegisterRequest"]["properties"]
        assert "minLength" not in props["password"]

    def test_login_schema_also_allows_empty_password_for_registered_users(self):
        from app.modules.auth.schemas import LoginRequest

        req = LoginRequest(email="user@example.com", password="")
        assert req.password == ""


class TestMonolithNginxEntrypoint:
    """Nginx must not fail because /docker-entrypoint-custom.sh is absent."""

    @pytest.fixture(scope="class")
    def nginx_service(self):
        return _load_compose()["services"]["nginx"]

    def test_nginx_uses_inline_shell_entrypoint(self, nginx_service):
        assert nginx_service.get("entrypoint") == ["/bin/sh", "-c"]

    def test_nginx_command_generates_ssl_and_starts_nginx(self, nginx_service):
        command = nginx_service.get("command", "")
        assert "openssl req -x509" in command
        assert "exec nginx -g" in command

    def test_nginx_does_not_mount_custom_entrypoint_script(self, nginx_service):
        volumes = nginx_service.get("volumes", [])
        assert not any("/docker-entrypoint-custom.sh" in volume for volume in volumes)


class TestMonolithReactFrontend:
    """Monolith frontend should mirror docker-compose.unified.yml's React app."""

    @pytest.fixture(scope="class")
    def compose(self):
        return _load_compose()

    def test_user_frontend_builds_from_frontend_react(self, compose):
        service = compose["services"]["user-frontend"]
        assert service.get("build", {}).get("context") == "./frontend-react"

    def test_user_frontend_uses_frontend_image_tag(self, compose):
        service = compose["services"]["user-frontend"]
        assert "/frontend:" in service.get("image", "")

    def test_user_frontend_healthcheck_targets_nginx_port_80(self, compose):
        service = compose["services"]["user-frontend"]
        command = " ".join(str(item) for item in service["healthcheck"]["test"])
        assert "localhost:80" in command

    def test_user_frontend_no_longer_uses_nextjs_runtime_env(self, compose):
        env = _env_dict(compose["services"]["user-frontend"])
        assert "HOSTNAME" not in env
        assert "BACKEND_MONOLITH_URL" not in env

    def test_nginx_routes_frontend_to_port_80(self):
        nginx = NGINX_MONOLITH_CONF.read_text()
        assert "user-frontend:80" in nginx
        assert "user-frontend:3000" not in nginx
