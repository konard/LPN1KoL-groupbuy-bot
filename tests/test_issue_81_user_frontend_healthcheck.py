"""
Tests for issue #81: user-frontend container fails healthcheck and prevents
docker compose -f docker-compose.monolith.yml up -d from completing.

Root cause: Docker sets the container's $HOSTNAME to the container ID. The
Next.js standalone server (server.js) reads $HOSTNAME to determine the bind
address. Without an explicit override, Next.js binds to the container's
primary IP only — making localhost:3000 unreachable for the wget healthcheck.

Fix: HOSTNAME=0.0.0.0 in the user-frontend environment forces Next.js to
bind on all interfaces, including loopback (127.0.0.1), so the healthcheck
succeeds.
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
    """HOSTNAME=0.0.0.0 must be set so Next.js binds on all interfaces."""

    def test_hostname_env_is_set(self):
        """user-frontend environment must define HOSTNAME=0.0.0.0."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        env = svc.get("environment", {})
        # environment can be a dict or list of KEY=VALUE strings
        if isinstance(env, list):
            env_dict = {}
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_dict[k.strip()] = v.strip()
                else:
                    env_dict[item.strip()] = ""
        else:
            env_dict = {str(k): str(v) for k, v in env.items()}

        assert "HOSTNAME" in env_dict, (
            "user-frontend environment is missing HOSTNAME. "
            "Docker sets $HOSTNAME to the container ID; Next.js standalone "
            "uses $HOSTNAME as the bind address and will only listen on the "
            "container's primary IP — making localhost:3000 unreachable for "
            "the wget healthcheck. Set HOSTNAME=0.0.0.0 to bind on all interfaces."
        )
        assert env_dict["HOSTNAME"] == "0.0.0.0", (
            f"user-frontend HOSTNAME must be '0.0.0.0', got '{env_dict['HOSTNAME']}'. "
            "Only 0.0.0.0 guarantees the server listens on all interfaces including loopback."
        )

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

    def test_healthcheck_targets_port_3000(self):
        """Healthcheck must target port 3000 where Next.js listens."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(str(t) for t in hc.get("test", []))
        assert "3000" in test_cmd, (
            f"user-frontend healthcheck must target port 3000, got: {test_cmd}"
        )

    def test_healthcheck_start_period_sufficient(self):
        """start_period must be at least 20s to allow Next.js time to start."""
        compose = load_compose()
        svc = compose["services"]["user-frontend"]
        hc = svc.get("healthcheck", {})
        start_period = hc.get("start_period", "0s")
        # Parse seconds value (e.g. "30s" -> 30)
        seconds = int(str(start_period).rstrip("s").rstrip("m"))
        if str(start_period).endswith("m"):
            seconds *= 60
        assert seconds >= 20, (
            f"user-frontend healthcheck start_period is {start_period}, "
            "should be at least 20s for Next.js standalone server to initialize"
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
