"""
Tests for issue #143: init-databases.sh fails with CRLF on docker-compose.python.yml.

Root causes:
1. docker-compose.light.yml postgres healthcheck lacks start_period — on first boot
   (initdb + creating five extra databases) postgres routinely takes more than 10 s;
   without start_period the orchestrator marks the container unhealthy before it is
   ready, cascading to every service that depends on it.

2. docker-compose.unified.yml postgres start_period is only 10 s — also too short
   for first-boot initialization.  docker-compose.python.yml correctly uses 30 s;
   unified and light should match.

3. scripts/init-databases.sh is mounted without :ro in both docker-compose.light.yml
   and docker-compose.unified.yml — config files should be read-only to prevent
   accidental writes from within the container (docker-compose.python.yml already
   uses :ro after PR #141).
"""

import pathlib

import yaml

REPO = pathlib.Path(__file__).parent.parent

COMPOSE_LIGHT = REPO / "docker-compose.light.yml"
COMPOSE_UNIFIED = REPO / "docker-compose.unified.yml"
COMPOSE_PYTHON = REPO / "docker-compose.python.yml"

INIT_SCRIPT_HOST = "./scripts/init-databases.sh"
INIT_SCRIPT_CONTAINER = "/docker-entrypoint-initdb.d/init-databases.sh"


def _parse_duration(value) -> float:
    """Parse a docker-compose duration string (e.g. '30s', '1m') to seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000.0
    if s.endswith("s"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) * 60
    if s.endswith("h"):
        return float(s[:-1]) * 3600
    return float(s)


def _load(path: pathlib.Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


class TestLightComposePostgresHealthcheck:
    """docker-compose.light.yml postgres healthcheck must survive first-boot init."""

    def test_postgres_has_healthcheck(self):
        compose = _load(COMPOSE_LIGHT)
        assert "healthcheck" in compose["services"]["postgres"], (
            "docker-compose.light.yml postgres must define a healthcheck."
        )

    def test_postgres_has_start_period(self):
        hc = _load(COMPOSE_LIGHT)["services"]["postgres"]["healthcheck"]
        assert "start_period" in hc, (
            "docker-compose.light.yml postgres healthcheck must include start_period. "
            "On first boot (initdb + creating five extra databases) postgres takes "
            "> 10 s to become ready; without start_period the orchestrator marks it "
            "unhealthy immediately and every dependent service fails."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = _load(COMPOSE_LIGHT)["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"docker-compose.light.yml postgres healthcheck.start_period must be "
            f"at least 30s to cover first-boot init. Currently: {start_period!r}."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        hc = _load(COMPOSE_LIGHT)["services"]["postgres"]["healthcheck"]
        test_cmd = hc["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"docker-compose.light.yml postgres healthcheck must use pg_isready; "
            f"got: {cmd_str}"
        )


class TestUnifiedComposePostgresHealthcheck:
    """docker-compose.unified.yml postgres healthcheck must survive first-boot init."""

    def test_postgres_has_healthcheck(self):
        compose = _load(COMPOSE_UNIFIED)
        assert "healthcheck" in compose["services"]["postgres"], (
            "docker-compose.unified.yml postgres must define a healthcheck."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = _load(COMPOSE_UNIFIED)["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"docker-compose.unified.yml postgres healthcheck.start_period must be "
            f"at least 30s to cover first-boot init. Currently: {start_period!r}. "
            f"docker-compose.python.yml already uses 30s — unified should match."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        hc = _load(COMPOSE_UNIFIED)["services"]["postgres"]["healthcheck"]
        test_cmd = hc["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"docker-compose.unified.yml postgres healthcheck must use pg_isready; "
            f"got: {cmd_str}"
        )


class TestInitScriptMountedReadOnly:
    """scripts/init-databases.sh should be mounted read-only in all compose files
    that use it — config files should not be writable from within the container."""

    def _find_init_mount(self, compose: dict) -> str | None:
        volumes = compose["services"]["postgres"].get("volumes", [])
        for vol in volumes:
            if isinstance(vol, str) and INIT_SCRIPT_HOST in vol:
                return vol
        return None

    def test_python_compose_mounts_init_script_readonly(self):
        compose = _load(COMPOSE_PYTHON)
        mount = self._find_init_mount(compose)
        assert mount is not None, (
            f"docker-compose.python.yml postgres does not mount {INIT_SCRIPT_HOST}"
        )
        assert mount.endswith(":ro"), (
            f"docker-compose.python.yml should mount init-databases.sh with :ro. "
            f"Got: {mount!r}"
        )

    def test_light_compose_mounts_init_script_readonly(self):
        compose = _load(COMPOSE_LIGHT)
        mount = self._find_init_mount(compose)
        assert mount is not None, (
            f"docker-compose.light.yml postgres does not mount {INIT_SCRIPT_HOST}"
        )
        assert mount.endswith(":ro"), (
            f"docker-compose.light.yml should mount init-databases.sh with :ro. "
            f"Got: {mount!r}"
        )

    def test_unified_compose_mounts_init_script_readonly(self):
        compose = _load(COMPOSE_UNIFIED)
        mount = self._find_init_mount(compose)
        assert mount is not None, (
            f"docker-compose.unified.yml postgres does not mount {INIT_SCRIPT_HOST}"
        )
        assert mount.endswith(":ro"), (
            f"docker-compose.unified.yml should mount init-databases.sh with :ro. "
            f"Got: {mount!r}"
        )
