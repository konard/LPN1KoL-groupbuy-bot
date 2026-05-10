"""Regression coverage for issue #234: unified frontend auth proxy still wrong.

Issues #228/#230 added a Vite proxy for ``/auth/*`` and issue #232 added the
same proxy to the legacy frontend.  The remaining failure mode is the one
called out in #232: ``frontend-react`` can be run as a dev server inside the
Docker network.  In that mode ``localhost:3001`` points back at the frontend
container, not at the host-published gateway port, so POST ``/auth/register``
can still be handled by Vite itself and return "Cannot POST /auth/register".

The fix must be container-configurable from ``docker-compose.unified.yml``:
Vite keeps host-local fallbacks for laptop development, while the unified
compose file injects Docker DNS targets such as ``http://gateway:3000``.
"""

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parent.parent
UNIFIED_COMPOSE = ROOT / "docker-compose.unified.yml"
VITE_CONFIG = ROOT / "frontend-react" / "vite.config.js"
FRONTEND_NGINX = ROOT / "frontend-react" / "nginx.conf"
EDGE_NGINX = ROOT / "infrastructure" / "nginx" / "nginx-api.conf"


def _load_unified() -> dict:
    with UNIFIED_COMPOSE.open() as f:
        return yaml.safe_load(f)


def _environment_map(service: dict) -> dict[str, str]:
    env = service.get("environment", {})
    if isinstance(env, dict):
        return env
    parsed = {}
    for item in env:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            parsed[key] = value
    return parsed


def _proxy_block(source: str, key: str) -> str:
    match = re.search(
        rf"['\"]{re.escape(key)}['\"]\s*:\s*\{{([^}}]+)\}}",
        source,
        re.DOTALL,
    )
    assert match is not None, f"frontend-react/vite.config.js has no {key!r} proxy block"
    return match.group(1)


def test_unified_frontend_injects_docker_auth_proxy_target():
    compose = _load_unified()
    frontend = compose["services"]["frontend-react"]
    env = _environment_map(frontend)

    assert env.get("VITE_AUTH_PROXY_TARGET") == "http://gateway:3000", (
        "docker-compose.unified.yml frontend-react must provide the Docker "
        "network gateway target for Vite dev-server auth proxying. "
        "localhost:3001 points back at the frontend container."
    )


def test_unified_frontend_injects_docker_core_and_ws_proxy_targets():
    compose = _load_unified()
    frontend = compose["services"]["frontend-react"]
    env = _environment_map(frontend)

    assert env.get("VITE_API_PROXY_TARGET") == "http://core:8000"
    assert env.get("VITE_WS_PROXY_TARGET") == "ws://websocket-server:8765"


def test_vite_auth_proxy_uses_configurable_gateway_target():
    source = VITE_CONFIG.read_text()
    block = _proxy_block(source, "/auth")

    assert "gatewayTarget" in block, (
        "The /auth Vite proxy must use a configurable gateway target. "
        "A literal localhost target fails when Vite runs inside Docker."
    )
    assert "target: 'http://localhost:3001'" not in block
    assert "target: \"http://localhost:3001\"" not in block


def test_vite_dev_server_listens_on_container_interface():
    source = VITE_CONFIG.read_text()

    assert re.search(r"host\s*:\s*['\"]0\.0\.0\.0['\"]", source) or re.search(
        r"host\s*:\s*true", source
    ), (
        "Vite must listen on the container interface when frontend-react is "
        "run in dev-server mode under Docker Compose."
    )


def test_production_nginx_chain_still_routes_auth_to_gateway():
    frontend_conf = FRONTEND_NGINX.read_text()
    edge_conf = EDGE_NGINX.read_text()

    assert "location /auth/" in frontend_conf
    assert "proxy_pass $gateway_upstream;" in frontend_conf
    assert edge_conf.count("location /auth/") >= 2
    assert "proxy_pass http://gateway;" in edge_conf
