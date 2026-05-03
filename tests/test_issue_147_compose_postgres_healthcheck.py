"""
Tests for issue #147: postgres healthcheck start_period too short in
docker-compose.prod.yml and docker-compose.two-server.yml.

Root causes:

1. docker-compose.prod.yml postgres healthcheck has start_period: 10s — too short
   for first-boot initialization (initdb can take > 10s on a fresh volume).
   On first boot postgres must (a) run initdb, (b) start the server, and (c) restart
   on the public listener; without adequate grace the orchestrator marks it unhealthy
   before it is ready, causing every dependent service to fail.

2. docker-compose.two-server.yml postgres healthcheck lacks start_period entirely —
   the orchestrator starts probing immediately on first boot, which can mark postgres
   unhealthy during initdb, cascading to core, bot, and all dependent services.

Fix: set start_period: 30s and retries: 10 in both files, matching
docker-compose.python.yml, docker-compose.light.yml, docker-compose.unified.yml,
and docker-compose.yml (all fixed in previous PRs).
"""

import pathlib

import yaml

REPO = pathlib.Path(__file__).parent.parent

COMPOSE_PROD = REPO / "docker-compose.prod.yml"
COMPOSE_TWO_SERVER = REPO / "docker-compose.two-server.yml"


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


class TestProdComposePostgresHealthcheck:
    """docker-compose.prod.yml postgres healthcheck must survive first-boot init."""

    def test_postgres_has_healthcheck(self):
        compose = _load(COMPOSE_PROD)
        assert "healthcheck" in compose["services"]["postgres"], (
            "docker-compose.prod.yml postgres must define a healthcheck."
        )

    def test_postgres_has_start_period(self):
        hc = _load(COMPOSE_PROD)["services"]["postgres"]["healthcheck"]
        assert "start_period" in hc, (
            "docker-compose.prod.yml postgres healthcheck must include start_period. "
            "On first boot postgres must run initdb before accepting connections; "
            "without start_period the orchestrator marks it unhealthy immediately."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = _load(COMPOSE_PROD)["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"docker-compose.prod.yml postgres healthcheck.start_period must be "
            f"at least 30s to cover first-boot initdb. Currently: {start_period!r}."
        )

    def test_postgres_retries_grants_at_least_100s_after_start_period(self):
        hc = _load(COMPOSE_PROD)["services"]["postgres"]["healthcheck"]
        retries = int(hc.get("retries", 1))
        interval_s = _parse_duration(hc.get("interval", "30s"))
        window = retries * interval_s
        assert window >= 100, (
            f"docker-compose.prod.yml postgres healthcheck retries * interval = "
            f"{window}s; must be ≥ 100s to absorb transient slowness. "
            f"Currently retries={retries}, interval={hc.get('interval')}."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        hc = _load(COMPOSE_PROD)["services"]["postgres"]["healthcheck"]
        test_cmd = hc["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"docker-compose.prod.yml postgres healthcheck must use pg_isready; "
            f"got: {cmd_str}"
        )


class TestTwoServerComposePostgresHealthcheck:
    """docker-compose.two-server.yml postgres healthcheck must survive first-boot init."""

    def test_postgres_has_healthcheck(self):
        compose = _load(COMPOSE_TWO_SERVER)
        assert "healthcheck" in compose["services"]["postgres"], (
            "docker-compose.two-server.yml postgres must define a healthcheck."
        )

    def test_postgres_has_start_period(self):
        hc = _load(COMPOSE_TWO_SERVER)["services"]["postgres"]["healthcheck"]
        assert "start_period" in hc, (
            "docker-compose.two-server.yml postgres healthcheck must include "
            "start_period. On first boot postgres must complete initdb before "
            "accepting connections; without start_period the orchestrator marks "
            "it unhealthy immediately, cascading failures to core and bot."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        hc = _load(COMPOSE_TWO_SERVER)["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"docker-compose.two-server.yml postgres healthcheck.start_period must "
            f"be at least 30s to cover first-boot initdb. "
            f"Currently: {start_period!r}."
        )

    def test_postgres_retries_grants_at_least_100s_after_start_period(self):
        hc = _load(COMPOSE_TWO_SERVER)["services"]["postgres"]["healthcheck"]
        retries = int(hc.get("retries", 1))
        interval_s = _parse_duration(hc.get("interval", "30s"))
        window = retries * interval_s
        assert window >= 100, (
            f"docker-compose.two-server.yml postgres healthcheck retries * interval "
            f"= {window}s; must be ≥ 100s. "
            f"Currently retries={retries}, interval={hc.get('interval')}."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        hc = _load(COMPOSE_TWO_SERVER)["services"]["postgres"]["healthcheck"]
        test_cmd = hc["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"docker-compose.two-server.yml postgres healthcheck must use pg_isready; "
            f"got: {cmd_str}"
        )
