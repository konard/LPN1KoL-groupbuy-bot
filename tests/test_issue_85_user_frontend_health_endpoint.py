"""
Tests for issue #85: user-frontend container is unhealthy when running
docker-compose.monolith.yml up --build -d.

Root cause: The healthcheck targets the root path (/) which triggers a full
Next.js SSR render. Any server-side rendering issue causes wget to receive
a non-200 response, making the healthcheck fail even when the server is up.
Additionally, the Dockerfile lacked HOSTNAME=0.0.0.0, so the ENV was only
set in docker-compose — missing when the container is run directly.

Fix:
1. Add pages/api/health.js — a lightweight endpoint that always returns 200 OK.
2. Update the docker-compose healthcheck to target /api/health instead of /.
3. Add HOSTNAME=0.0.0.0 to the Dockerfile ENV so the server always binds on
   all interfaces, regardless of how the container is launched.
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
    """docker-compose.monolith.yml healthcheck must target /api/health."""

    def test_healthcheck_targets_api_health(self):
        """Healthcheck must use /api/health, not root /."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(str(t) for t in hc.get("test", []))
        assert "/api/health" in test_cmd, (
            f"user-frontend healthcheck should target /api/health, got: {test_cmd}. "
            "The root path / triggers a full SSR render which may fail; "
            "/api/health is a lightweight endpoint that always returns 200."
        )

    def test_healthcheck_start_period_sufficient(self):
        """start_period must be at least 20s for Next.js to initialize."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        start_period = hc.get("start_period", "0s")
        seconds = int(str(start_period).rstrip("s"))
        assert seconds >= 20, (
            f"user-frontend healthcheck start_period is {start_period}, "
            "should be at least 20s for Next.js standalone to initialize."
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
