"""
Tests validating the docker-compose.monolith.yml and nginx-monolith.conf
configuration correctness for issue #71.

Checks:
- /socket.io/ nginx location exists and targets backend-monolith (Bug #1 fix)
- centrifugo service is removed from compose (Bug #2 fix)
- postgres-chat service is removed from compose (Bug #3 fix)
- postgres_chat_data volume is removed from compose
- nginx /api/admin/ correctly routes to admin-backend
- nginx / and /lk/ correctly route to user-frontend
- all services are on correct networks
- backend-monolith healthcheck path is /health
"""

import re
import yaml
import pathlib

REPO = pathlib.Path(__file__).parent.parent
COMPOSE = REPO / "docker-compose.monolith.yml"
NGINX_CONF = REPO / "infrastructure/nginx/nginx-monolith.conf"


def load_compose():
    with open(COMPOSE) as f:
        return yaml.safe_load(f)


def load_nginx():
    return NGINX_CONF.read_text()


class TestNginxMonolithConf:
    """Verify nginx-monolith.conf routing for the monolith architecture."""

    def test_socket_io_location_exists(self):
        """BUG #1: /socket.io/ location must exist for Socket.IO WebSocket connections."""
        nginx = load_nginx()
        assert "location /socket.io/" in nginx, (
            "nginx-monolith.conf is missing location /socket.io/ block. "
            "Socket.IO clients connect to /socket.io/ by default. "
            "Without this, socket connections fall through to / → user-frontend (wrong)."
        )

    def test_socket_io_proxies_to_backend_monolith(self):
        """Socket.IO location must proxy to backend-monolith:4000."""
        nginx = load_nginx()
        # Find the /socket.io/ location blocks
        # Check that backend-monolith:4000 appears in association with /socket.io/
        socket_io_section = re.findall(
            r"location /socket\.io/ \{([^}]*)\}", nginx, re.DOTALL
        )
        assert socket_io_section, "No /socket.io/ location block found"
        for block in socket_io_section:
            assert "backend-monolith:4000" in block, (
                f"/socket.io/ block does not proxy to backend-monolith:4000: {block}"
            )

    def test_socket_io_has_websocket_upgrade_headers(self):
        """Socket.IO location must include WebSocket upgrade headers."""
        nginx = load_nginx()
        socket_io_sections = re.findall(
            r"location /socket\.io/ \{([^}]*)\}", nginx, re.DOTALL
        )
        assert socket_io_sections, "No /socket.io/ location block found"
        for block in socket_io_sections:
            assert "Upgrade" in block, (
                "/socket.io/ block missing Upgrade header for WebSocket"
            )
            assert "Connection" in block and "upgrade" in block.lower(), (
                "/socket.io/ block missing Connection upgrade header"
            )

    def test_api_admin_proxies_to_admin_backend(self):
        """Admin API must route to admin-backend:4010."""
        nginx = load_nginx()
        assert "admin_backend" in nginx or "admin-backend" in nginx, (
            "nginx-monolith.conf has no reference to admin-backend"
        )

    def test_root_location_proxies_to_user_frontend(self):
        """/ location must proxy to user-frontend:3000."""
        nginx = load_nginx()
        assert "user-frontend:3000" in nginx, (
            "nginx-monolith.conf does not reference user-frontend:3000"
        )

    def test_both_http_and_https_servers_have_socket_io(self):
        """Both port 80 and 443 server blocks must have /socket.io/ location."""
        nginx = load_nginx()
        count = nginx.count("location /socket.io/")
        assert count >= 2, (
            f"Expected /socket.io/ location in both HTTP and HTTPS server blocks, "
            f"found {count} occurrence(s)"
        )


class TestDockerComposeMonolith:
    """Verify docker-compose.monolith.yml service configuration."""

    def test_centrifugo_removed(self):
        """BUG #2: centrifugo service must be removed — it is replaced by Socket.IO."""
        compose = load_compose()
        services = compose.get("services", {})
        assert "centrifugo" not in services, (
            "centrifugo service is still present in docker-compose.monolith.yml. "
            "Real-time chat in the monolith uses Socket.IO (python-socketio) inside "
            "backend-monolith; centrifugo is a leftover from the microservices layout."
        )

    def test_postgres_chat_removed(self):
        """BUG #3: postgres-chat must be removed — chat schema lives in postgres-monolith."""
        compose = load_compose()
        services = compose.get("services", {})
        assert "postgres-chat" not in services, (
            "postgres-chat service is still present in docker-compose.monolith.yml. "
            "The chat schema is created by Alembic migration 0002 inside monolith_db "
            "(postgres-monolith). postgres-chat is unused and redundant."
        )

    def test_postgres_chat_volume_removed(self):
        """postgres_chat_data volume must be removed along with postgres-chat service."""
        compose = load_compose()
        volumes = compose.get("volumes", {})
        assert "postgres_chat_data" not in volumes, (
            "postgres_chat_data volume remains but postgres-chat service was removed"
        )

    def test_backend_monolith_on_both_networks(self):
        """backend-monolith must be on both backend-network and frontend-network."""
        compose = load_compose()
        svc = compose["services"]["backend-monolith"]
        networks = svc.get("networks", [])
        assert "backend-network" in networks, (
            "backend-monolith must be on backend-network to reach postgres, redis, kafka"
        )
        assert "frontend-network" in networks, (
            "backend-monolith must be on frontend-network so nginx and user-frontend can reach it"
        )

    def test_nginx_on_both_networks(self):
        """nginx must be on both networks to route traffic to all upstream services."""
        compose = load_compose()
        svc = compose["services"]["nginx"]
        networks = svc.get("networks", [])
        assert "backend-network" in networks, (
            "nginx must be on backend-network to proxy /api/* to backend-monolith"
        )
        assert "frontend-network" in networks, (
            "nginx must be on frontend-network to proxy / to user-frontend and /api/admin/ to admin-backend"
        )

    def test_backend_monolith_healthcheck_path(self):
        """backend-monolith healthcheck must target /health endpoint."""
        compose = load_compose()
        svc = compose["services"]["backend-monolith"]
        hc = svc.get("healthcheck", {})
        test_cmd = " ".join(hc.get("test", []))
        assert "/health" in test_cmd, (
            f"backend-monolith healthcheck must target /health, got: {test_cmd}"
        )

    def test_bot_uses_backend_monolith_api(self):
        """bot must point CORE_API_URL to backend-monolith, not the old core service."""
        compose = load_compose()
        svc = compose["services"]["bot"]
        env = svc.get("environment", [])
        # environment can be list or dict
        if isinstance(env, list):
            env_str = "\n".join(env)
        else:
            env_str = "\n".join(f"{k}={v}" for k, v in env.items())
        assert "backend-monolith" in env_str, (
            "bot CORE_API_URL must point to backend-monolith:4000, not old core service"
        )

    def test_postgres_monolith_is_healthy_dependency(self):
        """backend-monolith must wait for postgres-monolith to be healthy."""
        compose = load_compose()
        svc = compose["services"]["backend-monolith"]
        deps = svc.get("depends_on", {})
        assert "postgres-monolith" in deps, (
            "backend-monolith must depend on postgres-monolith"
        )
        cond = deps["postgres-monolith"].get("condition") if isinstance(deps["postgres-monolith"], dict) else None
        assert cond == "service_healthy", (
            "backend-monolith must wait for postgres-monolith to be healthy before starting"
        )

    def test_admin_backend_on_both_networks(self):
        """admin-backend must be on both networks for nginx and admin-frontend to reach it."""
        compose = load_compose()
        svc = compose["services"]["admin-backend"]
        networks = svc.get("networks", [])
        assert "backend-network" in networks, (
            "admin-backend must be on backend-network to reach postgres-monolith"
        )
        assert "frontend-network" in networks, (
            "admin-backend must be on frontend-network so admin-frontend and nginx can reach it"
        )
