"""
Tests for issue #350 fix:
  When a user registers via the auth service, their profile must be synced
  to the Rust core API so that GET /api/users/by_email/ returns the user and
  the frontend can resolve the integer coreId needed to create procurements.

  Root cause: auth-service only saved users in its own PostgreSQL database
  (auth_db) but never POSTed to the Rust core API.  When the frontend called
  GET /api/users/by_email/?email=..., the Rust core returned 404, which then
  caused "Не удалось определить организатора" when creating a procurement.

  Fix: after OTP-confirmed registration the auth-service's confirmRegistration
  handler calls syncUserToCoreApi(), which POSTs to POST /api/users/ in the
  Rust core.  CORE_API_URL is set in every docker-compose file.
"""
import os
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath: str) -> str:
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def load_compose(filename: str) -> dict:
    with open(os.path.join(ROOT, filename)) as f:
        return yaml.safe_load(f)


def get_env_value(env_section, key: str):
    """Return the value for *key* from an environment section.

    Handles both list-of-strings (``KEY=VALUE``) and dict-style mappings.
    """
    if env_section is None:
        return None
    if isinstance(env_section, list):
        for entry in env_section:
            if isinstance(entry, str) and entry.startswith(key + "="):
                return entry[len(key) + 1:]
    elif isinstance(env_section, dict):
        val = env_section.get(key)
        return str(val) if val is not None else None
    return None


# ---------------------------------------------------------------------------
# Auth-service source code checks
# ---------------------------------------------------------------------------

class TestAuthServiceCoreSync:
    """The auth service must sync newly registered users to the Rust core API."""

    def test_sync_method_exists(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "syncUserToCoreApi" in src, (
            "auth.service.ts must define a syncUserToCoreApi method that "
            "POSTs the new user to the Rust core API"
        )

    def test_sync_called_after_registration(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        # The sync call must appear inside confirmRegistration, after user creation
        confirm_idx = src.index("confirmRegistration")
        sync_idx = src.index("syncUserToCoreApi")
        assert sync_idx > confirm_idx, (
            "syncUserToCoreApi must be called inside confirmRegistration "
            "(after user creation)"
        )

    def test_sync_posts_to_core_api_users_endpoint(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "/api/users/" in src, (
            "syncUserToCoreApi must POST to the /api/users/ endpoint of the core API"
        )

    def test_sync_uses_core_api_url_env(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "CORE_API_URL" in src, (
            "syncUserToCoreApi must read CORE_API_URL from config so the URL "
            "can be configured per environment"
        )

    def test_sync_is_non_fatal(self):
        """A failure to sync must not block the registration response."""
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        # The method should call resolve() on error (fire-and-forget pattern)
        assert "resolve()" in src, (
            "syncUserToCoreApi must resolve() on error so that core API "
            "unavailability does not break registration"
        )


# ---------------------------------------------------------------------------
# docker-compose files must pass CORE_API_URL to the auth-service
# ---------------------------------------------------------------------------

COMPOSE_FILES_WITH_AUTH = [
    "docker-compose.yml",
    "docker-compose.unified.yml",
    "docker-compose.light.yml",
    "docker-compose.microservices.yml",
]


class TestCoreApiUrlInCompose:
    """Every docker-compose file that runs the auth-service must set CORE_API_URL."""

    def _check_compose(self, filename: str):
        compose = load_compose(filename)
        services = compose.get("services", {})
        assert "auth-service" in services, f"{filename}: auth-service service not found"
        env = services["auth-service"].get("environment")
        value = get_env_value(env, "CORE_API_URL")
        assert value is not None, (
            f"{filename}: auth-service must have CORE_API_URL set so it can "
            "sync newly registered users to the Rust core API"
        )
        assert "core" in value.lower() or "${CORE_API_URL" in value, (
            f"{filename}: CORE_API_URL='{value}' should point to the core service"
        )

    def test_docker_compose_yml(self):
        self._check_compose("docker-compose.yml")

    def test_docker_compose_unified(self):
        self._check_compose("docker-compose.unified.yml")

    def test_docker_compose_light(self):
        self._check_compose("docker-compose.light.yml")

    def test_docker_compose_microservices(self):
        self._check_compose("docker-compose.microservices.yml")


# ---------------------------------------------------------------------------
# docker-compose.yml: auth-service must depend on core being healthy
# ---------------------------------------------------------------------------

class TestAuthServiceDependsOnCore:
    """
    In docker-compose.yml (and unified) auth-service should wait for the core
    to be healthy before starting so the first sync attempt doesn't fail
    because the core hasn't started yet.
    """

    def _check_depends_on_core(self, filename: str):
        compose = load_compose(filename)
        services = compose.get("services", {})
        if "auth-service" not in services or "core" not in services:
            # Can only check when both services are in the same file
            return
        auth = services["auth-service"]
        depends_on = auth.get("depends_on", {})
        if isinstance(depends_on, list):
            assert "core" in depends_on, (
                f"{filename}: auth-service depends_on must include 'core'"
            )
        elif isinstance(depends_on, dict):
            assert "core" in depends_on, (
                f"{filename}: auth-service depends_on must include 'core'"
            )

    def test_docker_compose_yml(self):
        self._check_depends_on_core("docker-compose.yml")

    def test_docker_compose_unified(self):
        self._check_depends_on_core("docker-compose.unified.yml")
