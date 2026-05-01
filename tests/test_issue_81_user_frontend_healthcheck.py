"""
Tests for the monolith frontend healthcheck.

Issue #81 originally fixed a Next.js standalone healthcheck by setting
HOSTNAME=0.0.0.0. Issue #131 moved docker-compose.monolith.yml to the same
React/nginx frontend pattern used by docker-compose.unified.yml, so the
monolith healthcheck now targets nginx on localhost:80 and no longer needs
Next.js HOSTNAME runtime variables.
"""

import subprocess
import pathlib
import yaml
import pytest

REPO = pathlib.Path(__file__).parent.parent
COMPOSE = REPO / "docker-compose.monolith.yml"
NEXT_SERVER_JS = REPO / "user-frontend" / ".next" / "standalone" / "server.js"


def load_compose():
    with open(COMPOSE) as f:
        return yaml.safe_load(f)


class TestUserFrontendHostnameEnv:
    """The monolith frontend service no longer relies on Next.js HOSTNAME."""

    def test_monolith_frontend_uses_react_nginx_image(self):
        """user-frontend in monolith must build from frontend-react."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        assert svc.get("build", {}).get("context") == "./frontend-react"
        assert "/frontend:" in svc.get("image", "")
        assert "HOSTNAME" not in svc.get("environment", {})

    def test_hostname_env_allows_localhost_healthcheck(self):
        """With HOSTNAME=0.0.0.0, Next.js server must respond on 127.0.0.1."""
        if not NEXT_SERVER_JS.exists():
            pytest.skip("Next.js standalone build not present; run npm run build first")

        import socket
        import time
        import urllib.request
        import urllib.error

        port = 13000  # use non-standard port to avoid conflicts
        env = {"HOSTNAME": "0.0.0.0", "PORT": str(port), "NODE_ENV": "production"}
        import os

        full_env = {**os.environ, **env}
        proc = subprocess.Popen(
            ["node", str(NEXT_SERVER_JS)],
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Wait for server to start (up to 15 seconds)
            deadline = time.time() + 15
            started = False
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
                    started = True
                    break
                except (urllib.error.URLError, ConnectionRefusedError):
                    time.sleep(0.5)

            assert started, (
                "Next.js server with HOSTNAME=0.0.0.0 did not respond on "
                f"127.0.0.1:{port} within 15 seconds"
            )
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_without_hostname_override_server_does_not_bind_localhost(self):
        """Without HOSTNAME=0.0.0.0, server binds only to container IP, not localhost."""
        if not NEXT_SERVER_JS.exists():
            pytest.skip("Next.js standalone build not present; run npm run build first")

        import os
        import socket
        import time
        import urllib.request
        import urllib.error

        # Simulate Docker container environment: HOSTNAME = container ID (not loopback)
        container_hostname = "abc123def456"
        port = 13001
        env = {"HOSTNAME": container_hostname, "PORT": str(port), "NODE_ENV": "production"}
        full_env = {k: v for k, v in os.environ.items() if k != "HOSTNAME"}
        full_env.update(env)

        proc = subprocess.Popen(
            ["node", str(NEXT_SERVER_JS)],
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Give server time to start
            time.sleep(3)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
                accessible = True
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                accessible = False

            assert not accessible, (
                "Next.js server bound to a non-loopback HOSTNAME should NOT be "
                f"accessible via 127.0.0.1:{port}, but it was. "
                "This test verifies the root cause of issue #81."
            )
        finally:
            proc.terminate()
            proc.wait(timeout=5)


class TestUserFrontendHealthcheck:
    """Healthcheck configuration must be robust enough to pass."""

    def test_healthcheck_targets_localhost(self):
        """Healthcheck must target localhost (loopback) not a hostname."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(str(t) for t in hc.get("test", []))
        assert "localhost" in test_cmd or "127.0.0.1" in test_cmd, (
            f"user-frontend healthcheck must target localhost or 127.0.0.1, got: {test_cmd}"
        )

    def test_healthcheck_targets_port_80(self):
        """Healthcheck must target port 80 where the frontend nginx listens."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(str(t) for t in hc.get("test", []))
        assert "80" in test_cmd, (
            f"user-frontend healthcheck must target port 80, got: {test_cmd}"
        )

    def test_healthcheck_start_period_sufficient(self):
        """start_period must allow the frontend nginx to start."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        start_period = hc.get("start_period", "0s")
        # Parse seconds value (e.g. "30s" -> 30)
        seconds = int(str(start_period).rstrip("s").rstrip("m"))
        if str(start_period).endswith("m"):
            seconds *= 60
        assert seconds >= 10, (
            f"user-frontend healthcheck start_period is {start_period}, "
            "should be at least 10s for the frontend nginx container to initialize"
        )

    def test_nginx_waits_for_user_frontend_healthy(self):
        """nginx must depend on user-frontend with condition: service_healthy."""
        compose = load_compose()
        svc = compose["services"]["nginx"]
        deps = svc.get("depends_on", {})
        assert "user-frontend" in deps, (
            "nginx must depend on user-frontend"
        )
        cond = (
            deps["user-frontend"].get("condition")
            if isinstance(deps["user-frontend"], dict)
            else None
        )
        assert cond == "service_healthy", (
            "nginx must wait for user-frontend to be healthy (condition: service_healthy)"
        )
