"""
Tests for issue #85 and the later issue #131 frontend healthcheck changes.

Issue #85 added a lightweight Next.js health endpoint for the historical
user-frontend image. Issue #131 changed docker-compose.monolith.yml to run the
React/nginx frontend used by docker-compose.unified.yml, so the compose
healthcheck now targets nginx at / on localhost:80.
"""

import pathlib
import re

import yaml
import pytest

REPO = pathlib.Path(__file__).parent.parent
COMPOSE = REPO / "docker-compose.monolith.yml"
HEALTH_ENDPOINT = REPO / "user-frontend" / "pages" / "api" / "health.js"
DOCKERFILE = REPO / "user-frontend" / "Dockerfile"


def load_compose():
    with open(COMPOSE) as f:
        return yaml.safe_load(f)


class TestHealthEndpoint:
    """pages/api/health.js must exist and return 200 OK."""

    def test_health_file_exists(self):
        """pages/api/health.js must be present."""
        assert HEALTH_ENDPOINT.exists(), (
            "user-frontend/pages/api/health.js does not exist. "
            "A dedicated health endpoint is required so the Docker healthcheck "
            "can verify liveness without triggering a full SSR render."
        )

    def test_health_returns_200(self):
        """health.js must call res.status(200)."""
        content = HEALTH_ENDPOINT.read_text()
        assert "200" in content, (
            "user-frontend/pages/api/health.js must explicitly return HTTP 200. "
            "Without it, the healthcheck wget call may receive a non-200 response."
        )

    def test_health_sends_json_or_text_response(self):
        """health.js must send a response body (json or send/end)."""
        content = HEALTH_ENDPOINT.read_text()
        has_response = any(kw in content for kw in (".json(", ".send(", ".end("))
        assert has_response, (
            "user-frontend/pages/api/health.js must send a response body "
            "via res.json(), res.send(), or res.end()."
        )


class TestHealthcheckConfig:
    """docker-compose.monolith.yml healthcheck must target the React nginx."""

    def test_healthcheck_targets_frontend_nginx_root(self):
        """Healthcheck must use the frontend nginx root on port 80."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(str(t) for t in hc.get("test", []))
        assert "localhost:80/" in test_cmd, (
            f"user-frontend healthcheck should target localhost:80/, got: {test_cmd}. "
            "The monolith now uses the React/nginx frontend, mirroring "
            "docker-compose.unified.yml."
        )

    def test_healthcheck_start_period_sufficient(self):
        """start_period must be at least 10s for nginx to initialize."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        start_period = hc.get("start_period", "0s")
        seconds = int(str(start_period).rstrip("s"))
        assert seconds >= 10, (
            f"user-frontend healthcheck start_period is {start_period}, "
            "should be at least 10s for the frontend nginx container to initialize."
        )


class TestDockerfileHostname:
    """Dockerfile must set HOSTNAME=0.0.0.0 in ENV."""

    def test_hostname_in_dockerfile_env(self):
        """HOSTNAME=0.0.0.0 must appear in Dockerfile ENV."""
        content = DOCKERFILE.read_text()
        assert "HOSTNAME" in content and "0.0.0.0" in content, (
            "user-frontend/Dockerfile must set ENV HOSTNAME=0.0.0.0. "
            "Docker sets $HOSTNAME to the container ID; Next.js standalone "
            "uses $HOSTNAME as the bind address. Without this override, "
            "Next.js only listens on the container's primary IP — making "
            "localhost:3000 unreachable for the healthcheck."
        )

    def test_hostname_value_is_all_interfaces(self):
        """HOSTNAME in Dockerfile must be 0.0.0.0."""
        content = DOCKERFILE.read_text()
        match = re.search(r"ENV\s+HOSTNAME[=\s]+(\S+)", content)
        assert match is not None, (
            "Could not find ENV HOSTNAME line in user-frontend/Dockerfile."
        )
        assert match.group(1) == "0.0.0.0", (
            f"Dockerfile HOSTNAME must be '0.0.0.0', got '{match.group(1)}'."
        )
