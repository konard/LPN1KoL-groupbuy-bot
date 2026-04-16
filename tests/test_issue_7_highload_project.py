"""
Structural checks for issue #7.

The issue asks for a launchable `project-highload` stack that separates the
frontend, async REST API, horizontally scalable WebSocket service, Django admin,
PostgreSQL, PgBouncer, Redis, and nginx load balancer.
"""
import os
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project-highload"


def read_file(relpath):
    return (PROJECT / relpath).read_text()


def load_compose():
    with (PROJECT / "docker-compose.yml").open() as f:
        return yaml.safe_load(f)


def service_env(service):
    env = service.get("environment", {})
    if isinstance(env, list):
        result = {}
        for entry in env:
            if isinstance(entry, str) and "=" in entry:
                key, value = entry.split("=", 1)
                result[key] = value
            elif isinstance(entry, dict):
                result.update(entry)
        return result
    return env


class TestProjectHighloadLayout:
    def test_required_files_exist(self):
        required = [
            "docker-compose.yml",
            ".env.example",
            "README.md",
            "nginx/nginx.conf",
            "postgres/postgresql.conf",
            "backend/Dockerfile",
            "backend/requirements.txt",
            "backend/app/main.py",
            "backend/app/models.py",
            "backend/app/database.py",
            "backend/app/redis_client.py",
            "websocket/Dockerfile",
            "websocket/requirements.txt",
            "websocket/server.py",
            "admin/Dockerfile",
            "admin/requirements.txt",
            "admin/manage.py",
            "admin/django_app/settings.py",
            "admin/django_app/urls.py",
            "admin/django_app/models.py",
            "admin/django_app/admin.py",
            "admin/entrypoint.sh",
            "frontend/Dockerfile",
            "frontend/package.json",
            "frontend/index.html",
            "frontend/src/App.js",
        ]

        missing = [path for path in required if not (PROJECT / path).exists()]
        assert not missing, f"Missing project-highload files: {missing}"


class TestHighloadCompose:
    def test_compose_defines_required_services(self):
        compose = load_compose()
        services = compose["services"]
        for name in [
            "frontend",
            "backend",
            "websocket",
            "admin",
            "db",
            "pgbouncer",
            "redis",
            "nginx",
        ]:
            assert name in services, f"{name} service must be defined"

    def test_backend_and_websocket_are_scale_safe(self):
        services = load_compose()["services"]
        for name in ["backend", "websocket"]:
            service = services[name]
            assert "container_name" not in service, (
                f"{name} must not set container_name because it must support "
                "docker compose --scale"
            )
            assert "ports" not in service, (
                f"{name} should be reached through nginx so replicas do not "
                "fight over host ports"
            )

    def test_all_runtime_services_have_healthchecks_and_limits(self):
        services = load_compose()["services"]
        for name in ["frontend", "backend", "websocket", "admin", "db", "pgbouncer", "redis", "nginx"]:
            service = services[name]
            assert "healthcheck" in service, f"{name} must expose a local healthcheck"
            limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
            assert limits.get("memory"), f"{name} must declare a memory limit"

    def test_backend_uses_pgbouncer_and_redis_pubsub(self):
        backend = load_compose()["services"]["backend"]
        env = service_env(backend)
        assert "pgbouncer:6432" in env["DATABASE_URL"]
        assert env["REDIS_URL"].startswith("redis://redis:6379")
        assert env["REDIS_CHANNEL"] == "items:new"

    def test_db_uses_postgresql_15_and_pgbouncer_fronts_it(self):
        services = load_compose()["services"]
        assert str(services["db"]["image"]).startswith("postgres:15")
        assert "pgbouncer" in services
        pgbouncer_env = service_env(services["pgbouncer"])
        assert pgbouncer_env["DB_HOST"] == "db"
        assert pgbouncer_env["POOL_MODE"] == "transaction"


class TestBackendImplementation:
    def test_backend_is_async_fastapi_with_pooled_asyncpg(self):
        main = read_file("backend/app/main.py")
        database = read_file("backend/app/database.py")
        requirements = read_file("backend/requirements.txt")
        assert "FastAPI" in main
        assert "async def list_items" in main
        assert "async def create_item" in main
        assert "create_async_engine" in database
        assert "postgresql+asyncpg" in database
        assert "pool_size" in database
        assert "asyncpg" in requirements
        assert "SQLAlchemy" in requirements

    def test_backend_publishes_items_new_events(self):
        main = read_file("backend/app/main.py")
        redis_client = read_file("backend/app/redis_client.py")
        assert "publish_item_created" in main
        assert "items:new" in redis_client
        assert ".publish(" in redis_client

    def test_backend_exposes_health_readiness_and_metrics(self):
        main = read_file("backend/app/main.py")
        assert '"/healthz"' in main
        assert '"/readyz"' in main
        assert '"/metrics"' in main


class TestWebSocketImplementation:
    def test_websocket_subscribes_to_redis_and_broadcasts_locally(self):
        server = read_file("websocket/server.py")
        assert "aiohttp" in server
        assert "self.connections" in server
        assert "pubsub.subscribe" in server
        assert "items:new" in server
        assert "broadcast" in server

    def test_websocket_handles_shutdown_and_metrics(self):
        server = read_file("websocket/server.py")
        assert "on_shutdown" in server
        assert "GOING_AWAY" in server
        assert '"/healthz"' in server
        assert '"/readyz"' in server
        assert '"/metrics"' in server


class TestNginxStickySessions:
    def test_nginx_load_balances_api_and_sticks_websockets_by_cookie(self):
        nginx = read_file("nginx/nginx.conf")
        assert "worker_connections" in nginx
        assert "backend_upstream" in nginx
        assert "websocket_upstream" in nginx
        assert "hash $sticky_key consistent" in nginx
        assert "SERVER_ID" in nginx
        assert "proxy_set_header Upgrade" in nginx
        assert "/ws/" in nginx


class TestFrontendAndDocs:
    def test_frontend_uses_runtime_urls_from_vite_env(self):
        app = read_file("frontend/src/App.js")
        assert "VITE_API_URL" in app
        assert "VITE_WS_URL" in app
        assert "new WebSocket" in app

    def test_readme_documents_scaling_load_tests_failures_and_next_steps(self):
        readme = read_file("README.md")
        expected_fragments = [
            "docker compose up --build --scale websocket=3",
            "wrk",
            "k6",
            "Kubernetes",
            "Kafka",
            "Redis Pub/Sub",
            "graceful shutdown",
            "Architecture",
            "PgBouncer",
            "health",
        ]
        missing = [fragment for fragment in expected_fragments if fragment not in readme]
        assert not missing, f"README misses required documentation: {missing}"

    def test_postgres_config_contains_highload_basics(self):
        config = read_file("postgres/postgresql.conf")
        for setting in ["max_connections", "shared_buffers", "effective_cache_size"]:
            assert setting in config, f"{setting} must be configured"
