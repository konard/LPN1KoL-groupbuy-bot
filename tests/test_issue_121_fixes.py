"""
Tests for issue #121: docker-compose.monolith.yml fixes.

Bug #1: groupbuy-nginx-monolith fails to start with
        "exec /docker-entrypoint.sh: no such file or directory".

        Root cause: the nginx:alpine image ships its own /docker-entrypoint.sh.
        Mounting our custom script at the same path (/docker-entrypoint.sh)
        in read-only mode can prevent the bind mount from working correctly on
        some container runtimes, causing execve() to fail with ENOENT.

        Fix: mount the host script under a unique name
        /docker-entrypoint-custom.sh and set entrypoint to that path.
        This avoids the collision with the nginx default entrypoint and
        matches the fix applied in issue #109.

Bug #2: telegram-adapter and mattermost-adapter services must be removed
        from docker-compose.monolith.yml as requested by the issue author.
"""

import pathlib

import pytest
import yaml

REPO = pathlib.Path(__file__).parent.parent
COMPOSE_MONOLITH = REPO / "docker-compose.monolith.yml"
COMPOSE_UNIFIED = REPO / "docker-compose.unified.yml"


def _load(path: pathlib.Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Bug #1: nginx entrypoint path collision fix
# ---------------------------------------------------------------------------


class TestNginxEntrypointNaming:
    """The nginx service must use /docker-entrypoint-custom.sh to avoid
    colliding with the nginx:alpine image's built-in /docker-entrypoint.sh."""

    @pytest.mark.parametrize("compose_path", [COMPOSE_MONOLITH, COMPOSE_UNIFIED])
    def test_nginx_entrypoint_is_custom(self, compose_path):
        compose = _load(compose_path)
        nginx = compose["services"]["nginx"]
        entrypoint = nginx.get("entrypoint")
        assert entrypoint == ["/docker-entrypoint-custom.sh"], (
            f"{compose_path.name}: nginx entrypoint must be "
            "['/docker-entrypoint-custom.sh'] to avoid collision with the "
            "nginx:alpine built-in /docker-entrypoint.sh. Got: {entrypoint!r}"
        )

    @pytest.mark.parametrize("compose_path", [COMPOSE_MONOLITH, COMPOSE_UNIFIED])
    def test_nginx_volume_mounts_script_as_custom(self, compose_path):
        compose = _load(compose_path)
        nginx = compose["services"]["nginx"]
        volumes = nginx.get("volumes", [])
        assert any("/docker-entrypoint-custom.sh" in v for v in volumes), (
            f"{compose_path.name}: nginx must mount the host script at "
            f"/docker-entrypoint-custom.sh. Got volumes: {volumes}"
        )
        assert not any(
            v.endswith(":/docker-entrypoint.sh") or ":/docker-entrypoint.sh:" in v
            for v in volumes
        ), (
            f"{compose_path.name}: nginx must NOT mount anything at "
            "/docker-entrypoint.sh (reserved by nginx:alpine base image)."
        )


# ---------------------------------------------------------------------------
# Bug #2: telegram-adapter and mattermost-adapter removed from monolith
# ---------------------------------------------------------------------------


class TestAdaptersRemovedFromMonolith:
    """telegram-adapter and mattermost-adapter must not be present in
    docker-compose.monolith.yml per the issue request."""

    @pytest.fixture(scope="class")
    def compose(self):
        return _load(COMPOSE_MONOLITH)

    def test_telegram_adapter_not_in_monolith(self, compose):
        assert "telegram-adapter" not in compose.get("services", {}), (
            "telegram-adapter service must be removed from "
            "docker-compose.monolith.yml as requested in issue #121."
        )

    def test_mattermost_adapter_not_in_monolith(self, compose):
        assert "mattermost-adapter" not in compose.get("services", {}), (
            "mattermost-adapter service must be removed from "
            "docker-compose.monolith.yml as requested in issue #121."
        )
