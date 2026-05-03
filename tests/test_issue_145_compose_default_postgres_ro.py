"""
Tests for issue #145: docker-compose.yml mounts init-databases.sh without :ro.

The same bug fixed for docker-compose.light.yml and docker-compose.unified.yml in
PR #144 was present in the default docker-compose.yml — the init script volume mount
was missing the :ro (read-only) flag, allowing the container to write to a config
file it should only read.

Fix: add :ro to the mount:
  ./infrastructure/postgres/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh:ro
"""

import pathlib

import yaml

REPO = pathlib.Path(__file__).parent.parent

COMPOSE_DEFAULT = REPO / "docker-compose.yml"

INIT_SCRIPT_HOST = "./infrastructure/postgres/init-databases.sh"
INIT_SCRIPT_CONTAINER = "/docker-entrypoint-initdb.d/init-databases.sh"


def _load(path: pathlib.Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _find_init_mount(compose: dict) -> str | None:
    volumes = compose["services"]["postgres"].get("volumes", [])
    for vol in volumes:
        if isinstance(vol, str) and INIT_SCRIPT_HOST in vol:
            return vol
    return None


class TestDefaultComposePostgresInitScriptReadOnly:
    """docker-compose.yml init-databases.sh must be mounted read-only."""

    def test_postgres_mounts_init_script(self):
        compose = _load(COMPOSE_DEFAULT)
        mount = _find_init_mount(compose)
        assert mount is not None, (
            f"docker-compose.yml postgres does not mount {INIT_SCRIPT_HOST} "
            f"into {INIT_SCRIPT_CONTAINER}"
        )

    def test_postgres_init_script_mounted_readonly(self):
        compose = _load(COMPOSE_DEFAULT)
        mount = _find_init_mount(compose)
        assert mount is not None, (
            f"docker-compose.yml postgres does not mount {INIT_SCRIPT_HOST}"
        )
        assert mount.endswith(":ro"), (
            f"docker-compose.yml should mount init-databases.sh with :ro to prevent "
            f"accidental writes from inside the container. Got: {mount!r}"
        )

    def test_postgres_has_start_period(self):
        hc = _load(COMPOSE_DEFAULT)["services"]["postgres"]["healthcheck"]
        assert "start_period" in hc, (
            "docker-compose.yml postgres healthcheck must include start_period."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = _load(COMPOSE_DEFAULT)["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        s = str(start_period).strip()
        if s.endswith("s"):
            seconds = float(s[:-1])
        elif s.endswith("m"):
            seconds = float(s[:-1]) * 60
        else:
            seconds = float(s)
        assert seconds >= 30, (
            f"docker-compose.yml postgres healthcheck.start_period must be at least "
            f"30s for first-boot init. Currently: {start_period!r}."
        )
