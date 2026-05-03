"""
Tests for issue #137: docker-compose.python.yml has bugs causing
"container groupbuy-postgres is unhealthy" failures on `docker compose up`.

Root causes identified and fixed:

1. scripts/init-databases.sh lacked the executable bit. The official postgres
   image's docker-entrypoint sources non-executable .sh files in
   /docker-entrypoint-initdb.d/ instead of executing them. Sourcing inherits
   `set -e`, and any psql failure during sourcing aborts the entire
   docker-entrypoint, which makes postgres exit before the healthcheck can
   ever pass — so dependent services see `groupbuy-postgres is unhealthy`.

2. The postgres healthcheck used start_period: 10s, which is too short for the
   first container start: postgres has to (a) initdb the cluster, (b) start the
   server, (c) execute every script in /docker-entrypoint-initdb.d/ (creating
   five extra databases), and (d) restart on the public listener. On a fresh
   volume this routinely takes more than 10 seconds, so the orchestrator marks
   postgres unhealthy before it has finished initializing.

3. retries: 5 with interval: 10s gives only 50s of grace after start_period.
   Bump retries to 10 so transient slowness during cold-start init does not
   trip the unhealthy state for dependent services.
"""
import os
import pathlib
import stat

import yaml


REPO = pathlib.Path(__file__).parent.parent
COMPOSE = REPO / "docker-compose.python.yml"
INIT_SCRIPT = REPO / "scripts" / "init-databases.sh"


def load_compose():
    with open(COMPOSE) as f:
        return yaml.safe_load(f)


class TestInitDatabasesScriptExecutable:
    """The init-databases.sh script must be executable so the postgres
    docker-entrypoint runs it instead of sourcing it."""

    def test_init_script_exists(self):
        assert INIT_SCRIPT.exists(), (
            f"{INIT_SCRIPT} is referenced by docker-compose.python.yml "
            f"but does not exist on disk."
        )

    def test_init_script_is_executable(self):
        """
        Postgres's docker-entrypoint executes *.sh files only when the file
        has the executable bit; otherwise it sources them (which inherits
        `set -e` and can abort the entrypoint on any psql error).
        """
        mode = INIT_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, (
            f"{INIT_SCRIPT.name} must have the user-executable bit set so the "
            f"postgres docker-entrypoint runs it (instead of sourcing it). "
            f"Current mode: {oct(mode & 0o777)}."
        )
        # Also assert the world-execute bit so the file works under any UID
        # the postgres image runs the entrypoint as.
        assert mode & stat.S_IXOTH, (
            f"{INIT_SCRIPT.name} should be world-executable so it runs "
            f"regardless of the postgres image's runtime UID. "
            f"Current mode: {oct(mode & 0o777)}."
        )


class TestPostgresHealthcheckStartPeriod:
    """The postgres healthcheck must give enough grace for first-run init."""

    def test_postgres_service_exists(self):
        compose = load_compose()
        assert "postgres" in compose["services"], (
            "docker-compose.python.yml must define a `postgres` service."
        )

    def test_postgres_has_healthcheck(self):
        compose = load_compose()
        postgres = compose["services"]["postgres"]
        assert "healthcheck" in postgres, (
            "postgres service must define a healthcheck so dependent services "
            "can wait via condition: service_healthy."
        )

    def test_postgres_start_period_is_at_least_30s(self):
        """
        With init-databases.sh creating five additional databases on first
        boot (auth_db, purchase_db, payment_db, chat_db, reputation_db),
        cold-start typically takes 15–30 seconds. start_period must be long
        enough to cover this so postgres is not marked unhealthy mid-init.
        """
        compose = load_compose()
        hc = compose["services"]["postgres"]["healthcheck"]
        start_period = hc.get("start_period", "0s")
        # parse "30s" / "1m" etc. -> seconds
        seconds = _parse_duration(start_period)
        assert seconds >= 30, (
            f"postgres healthcheck.start_period must be at least 30s to cover "
            f"cold-start init (initdb + creating 5 extra databases). "
            f"Currently: {start_period} ({seconds}s)."
        )

    def test_postgres_retries_grants_at_least_100s_after_start_period(self):
        """
        After start_period elapses, the orchestrator gives retries × interval
        before declaring the container unhealthy. That window must be at
        least 100 seconds to absorb transient slowness on small hosts.
        """
        compose = load_compose()
        hc = compose["services"]["postgres"]["healthcheck"]
        retries = int(hc.get("retries", 1))
        interval_s = _parse_duration(hc.get("interval", "30s"))
        window = retries * interval_s
        assert window >= 100, (
            f"postgres healthcheck retries * interval = {window}s; "
            f"must be ≥ 100s to absorb transient slowness on cold start."
        )

    def test_postgres_healthcheck_uses_pg_isready(self):
        """The healthcheck should invoke pg_isready, not a custom command."""
        compose = load_compose()
        test_cmd = compose["services"]["postgres"]["healthcheck"]["test"]
        cmd_str = " ".join(test_cmd) if isinstance(test_cmd, list) else str(test_cmd)
        assert "pg_isready" in cmd_str, (
            f"postgres healthcheck must use pg_isready; got: {cmd_str}"
        )


class TestPostgresInitScriptMount:
    """The init script must be mounted into the container's init dir."""

    def test_init_script_mounted_to_initdb_dir(self):
        compose = load_compose()
        postgres = compose["services"]["postgres"]
        volumes = postgres.get("volumes", [])
        mounts = [v for v in volumes if "init-databases.sh" in v]
        assert mounts, (
            "postgres service must mount scripts/init-databases.sh into "
            "/docker-entrypoint-initdb.d/ so all required databases are "
            "created on first boot."
        )
        target = mounts[0].split(":")[1]
        assert "/docker-entrypoint-initdb.d/" in target, (
            f"init-databases.sh must be mounted under "
            f"/docker-entrypoint-initdb.d/, got: {target}"
        )


class TestComposeDependencyChain:
    """Services that depend on postgres must wait for it to be healthy."""

    def test_core_waits_for_postgres_healthy(self):
        compose = load_compose()
        core = compose["services"]["core"]
        deps = core.get("depends_on", {})
        assert "postgres" in deps, "core must depend on postgres"
        assert deps["postgres"].get("condition") == "service_healthy", (
            "core must wait for postgres to be healthy, not just started"
        )

    def test_backend_waits_for_postgres_healthy(self):
        compose = load_compose()
        backend = compose["services"]["backend"]
        deps = backend.get("depends_on", {})
        assert "postgres" in deps, "backend must depend on postgres"
        assert deps["postgres"].get("condition") == "service_healthy", (
            "backend must wait for postgres to be healthy"
        )

    def test_django_admin_waits_for_postgres_healthy(self):
        compose = load_compose()
        admin = compose["services"]["django-admin"]
        deps = admin.get("depends_on", {})
        assert "postgres" in deps, "django-admin must depend on postgres"
        assert deps["postgres"].get("condition") == "service_healthy", (
            "django-admin must wait for postgres to be healthy"
        )


class TestComposeYamlValid:
    """The compose file must parse and contain the documented services."""

    def test_compose_file_is_valid_yaml(self):
        compose = load_compose()
        assert isinstance(compose, dict)
        assert "services" in compose

    def test_required_services_present(self):
        compose = load_compose()
        services = compose["services"]
        for required in (
            "postgres",
            "redis",
            "kafka",
            "centrifugo",
            "core",
            "django-admin",
            "backend",
            "bot",
            "websocket-server",
            "frontend-react",
            "nginx",
        ):
            assert required in services, (
                f"docker-compose.python.yml is missing required service "
                f"`{required}`."
            )

    def test_gateway_service_absent(self):
        """Issue #163: gateway container must be removed from docker-compose.python.yml.
        All services in services/ are merged into the single 'backend' container."""
        compose = load_compose()
        assert "gateway" not in compose["services"], (
            "docker-compose.python.yml must NOT contain a `gateway` service — "
            "issue #163 requires all services/ microservices to be unified into "
            "the single `backend` container."
        )


def _parse_duration(value):
    """Parse a docker-compose duration string (e.g. '30s', '1m', '90') to seconds."""
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
