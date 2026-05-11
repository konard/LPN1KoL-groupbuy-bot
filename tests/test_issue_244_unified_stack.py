"""Regression coverage for issue #244.

Two independent problems were filed under this issue:

1. ``groupbuy-core`` crashed at startup with::

       asyncpg.exceptions.DatatypeMismatchError: foreign key constraint
       "buyer_requests_user_id_fkey" cannot be implemented.
       DETAIL:  Key columns "user_id" and "id" are of incompatible types:
       uuid and integer.

   Root cause: both ``core/`` (Django ORM, INTEGER pk) and ``core-fastapi/``
   (raw SQL, UUID pk) defined a ``users`` table on the same ``groupbuy``
   database. Django ran first (start_period 120s), created ``users`` with an
   INTEGER ``id``, and the FastAPI ``CREATE TABLE IF NOT EXISTS users`` then
   no-op'd. When ``buyer_requests`` tried to declare ``user_id UUID
   REFERENCES users(id)`` the FK failed because Django's ``id`` was INTEGER.

   The fix: give Django its own database (``django_admin_db``) so the two
   schemas never collide. Mirrors the per-service DB pattern already used by
   auth/purchase/payment/chat/reputation.

2. The operator asked for log aggregation (Sentry or Grafana) so they can
   read logs without running ``docker exec`` on the host.

   The fix: a self-hosted Grafana + Loki + Promtail stack inside the same
   compose network. Promtail tails every container's logs via the Docker
   socket, Loki stores them, Grafana renders them at ``GRAFANA_PORT``.

These tests guard against re-introducing either side of the regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.unified.yml"
INIT_DB_SH = ROOT / "scripts" / "init-databases.sh"
ENV_EXAMPLE = ROOT / ".env.example"

MONITORING = ROOT / "monitoring"
LOKI_CFG = MONITORING / "loki" / "loki-config.yaml"
PROMTAIL_CFG = MONITORING / "loki" / "promtail-config.yaml"
GRAFANA_DS = MONITORING / "grafana" / "provisioning" / "datasources" / "loki.yaml"
GRAFANA_DASHBOARDS_PROVIDER = (
    MONITORING / "grafana" / "provisioning" / "dashboards" / "dashboards.yaml"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(_read(COMPOSE))


# ─── Part 1: UUID vs INTEGER FK collision on users.id ────────────────────────


def test_init_databases_provisions_django_admin_db():
    """Postgres init script must create django_admin_db on first start."""
    sh = _read(INIT_DB_SH)
    assert "django_admin_db" in sh, (
        "scripts/init-databases.sh must CREATE DATABASE django_admin_db so "
        "Django has somewhere isolated to live (issue #244)."
    )


def test_django_admin_service_uses_separate_database(compose):
    """django-admin must not connect to the shared groupbuy database."""
    env = compose["services"]["django-admin"]["environment"]
    db_url = next((e for e in env if e.startswith("DATABASE_URL=")), None)
    assert db_url is not None, "django-admin must declare DATABASE_URL"
    assert "django_admin_db" in db_url or "DJANGO_DB_NAME" in db_url, (
        f"django-admin DATABASE_URL must point at django_admin_db so its "
        f"INTEGER users.id never collides with core-fastapi's UUID users.id "
        f"(issue #244). Got: {db_url}"
    )
    # And it must NOT fall back to the shared groupbuy database.
    assert "${DB_NAME:-groupbuy}" not in db_url, (
        "django-admin must not default to ${DB_NAME:-groupbuy}; that is the "
        "core-fastapi database and re-introduces issue #244."
    )


def test_core_fastapi_still_uses_shared_groupbuy_db(compose):
    """core-fastapi keeps its existing DB; only Django moves."""
    env = compose["services"]["core"]["environment"]
    db_url = next((e for e in env if e.startswith("DATABASE_URL=")), None)
    assert db_url is not None
    assert "${DB_NAME:-groupbuy}" in db_url, (
        "core (FastAPI) should still target the canonical groupbuy DB; only "
        "django-admin was moved in the fix for issue #244."
    )


def test_env_example_documents_django_db_name():
    """Operators need DJANGO_DB_NAME in .env.example to override the default."""
    text = _read(ENV_EXAMPLE)
    assert "DJANGO_DB_NAME" in text, (
        ".env.example must mention DJANGO_DB_NAME so operators understand "
        "Django runs on its own database (issue #244)."
    )


# ─── Part 2: Grafana + Loki + Promtail log aggregation stack ─────────────────


@pytest.mark.parametrize("service", ["loki", "promtail", "grafana"])
def test_compose_defines_log_aggregation_services(compose, service):
    assert service in compose["services"], (
        f"docker-compose.unified.yml must define service '{service}' so "
        f"operators can read logs without docker exec (issue #244)."
    )


def test_grafana_port_is_exposed(compose):
    ports = compose["services"]["grafana"].get("ports", [])
    assert any("3000" in str(p) for p in ports), (
        "Grafana must expose its HTTP port (container 3000) so the operator "
        "can reach the UI from outside the compose network."
    )


def test_promtail_mounts_docker_socket(compose):
    volumes = compose["services"]["promtail"].get("volumes", [])
    sock_mounts = [v for v in volumes if "/var/run/docker.sock" in v]
    assert sock_mounts, (
        "Promtail must mount the Docker socket — it discovers containers "
        "via Docker SD."
    )
    log_mounts = [v for v in volumes if "/var/lib/docker/containers" in v]
    assert log_mounts, (
        "Promtail must mount /var/lib/docker/containers so it can read the "
        "containers' JSON log files."
    )
    # Read-only is important — Promtail never writes to either path.
    for mount in sock_mounts + log_mounts:
        assert mount.endswith(":ro"), (
            f"Promtail mount {mount!r} should be read-only; Promtail only "
            f"needs to read logs and inspect the docker socket."
        )


def test_loki_has_persistent_volume(compose):
    volumes = compose["services"]["loki"].get("volumes", [])
    assert any("loki_data:/loki" in v for v in volumes), (
        "Loki must persist /loki onto the loki_data named volume so logs "
        "survive container restarts."
    )
    # And the named volume must be declared at the top level.
    assert "loki_data" in compose.get("volumes", {}), (
        "Top-level 'volumes:' block must declare loki_data."
    )


def test_grafana_has_persistent_volume(compose):
    volumes = compose["services"]["grafana"].get("volumes", [])
    assert any("grafana_data:/var/lib/grafana" in v for v in volumes), (
        "Grafana must persist /var/lib/grafana so dashboards and users "
        "survive restarts."
    )
    assert "grafana_data" in compose.get("volumes", {})


def test_loki_config_file_exists_and_is_valid_yaml():
    assert LOKI_CFG.exists(), f"Missing Loki config: {LOKI_CFG}"
    cfg = yaml.safe_load(_read(LOKI_CFG))
    # http_listen_port must match the URL used by Promtail and Grafana
    assert cfg["server"]["http_listen_port"] == 3100


def test_promtail_config_targets_loki_service():
    assert PROMTAIL_CFG.exists(), f"Missing Promtail config: {PROMTAIL_CFG}"
    cfg = yaml.safe_load(_read(PROMTAIL_CFG))
    urls = [c["url"] for c in cfg["clients"]]
    assert any("loki:3100" in u for u in urls), (
        "Promtail must push to http://loki:3100 (the compose service name)."
    )
    # Docker SD discovers running containers.
    job_names = {j["job_name"] for j in cfg["scrape_configs"]}
    assert "docker" in job_names


def test_grafana_datasource_points_to_loki():
    assert GRAFANA_DS.exists(), f"Missing Grafana datasource: {GRAFANA_DS}"
    cfg = yaml.safe_load(_read(GRAFANA_DS))
    ds = cfg["datasources"][0]
    assert ds["type"] == "loki"
    assert ds["url"] == "http://loki:3100"


def test_grafana_dashboards_provider_exists():
    assert GRAFANA_DASHBOARDS_PROVIDER.exists()
    cfg = yaml.safe_load(_read(GRAFANA_DASHBOARDS_PROVIDER))
    assert cfg["apiVersion"] == 1
    assert cfg["providers"], "Provisioning must declare at least one provider"


def test_default_dashboard_json_is_valid():
    dashboard = (
        MONITORING / "grafana" / "provisioning" / "dashboards" / "container-logs.json"
    )
    assert dashboard.exists()
    # Must parse and reference the Loki datasource UID set in loki.yaml.
    data = json.loads(_read(dashboard))
    assert data["uid"] == "groupbuy-container-logs"
    panel_datasource_uids = {
        p.get("datasource", {}).get("uid")
        for p in data.get("panels", [])
        if isinstance(p.get("datasource"), dict)
    }
    assert "loki" in panel_datasource_uids


@pytest.mark.parametrize(
    "var",
    ["GRAFANA_PORT", "GRAFANA_ADMIN_USER", "GRAFANA_ADMIN_PASSWORD"],
)
def test_env_example_documents_grafana_vars(var):
    text = _read(ENV_EXAMPLE)
    assert var in text, (
        f".env.example must document {var} so operators know how to "
        f"customise the Grafana login (issue #244)."
    )


def test_grafana_depends_on_loki(compose):
    """Grafana would 500 if it started before Loki was ready."""
    deps = compose["services"]["grafana"].get("depends_on", {})
    if isinstance(deps, list):
        assert "loki" in deps
    else:
        assert "loki" in deps
        assert deps["loki"]["condition"] == "service_healthy"
