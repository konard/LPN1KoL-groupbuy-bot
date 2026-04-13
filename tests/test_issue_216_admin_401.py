"""
Tests for issue #216 fix:
  Admin panel returns 401 when logging in with credentials from .env.

Root cause:
  docker-compose.prod.yml was missing the CSRF_TRUSTED_ORIGINS environment
  variable for the django-admin service.  Django's CSRF middleware rejects
  POST requests (including the admin login POST) whose Origin/Referer header
  is not listed in CSRF_TRUSTED_ORIGINS, returning 403 Forbidden.  This
  prevents the admin from logging in even with valid credentials.

Fix:
  Added CSRF_TRUSTED_ORIGINS to docker-compose.prod.yml django-admin
  environment, using the same pattern as docker-compose.unified.yml:
    CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS:-http://localhost,http://<SERVER_IP>,...}
"""
import os

import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_prod_compose():
    """Load docker-compose.prod.yml as a dict."""
    path = os.path.join(ROOT, "docker-compose.prod.yml")
    with open(path) as f:
        return yaml.safe_load(f)


def get_django_admin_env(compose):
    """Return the environment list for the django-admin service."""
    return compose["services"]["django-admin"].get("environment", [])


def parse_env_var(env_list, key):
    """Return the value string for KEY=VALUE in env_list, or None."""
    for entry in env_list:
        if isinstance(entry, str) and entry.startswith(key + "="):
            return entry[len(key) + 1:]
        if isinstance(entry, dict) and key in entry:
            return str(entry[key])
    return None


class TestProdComposeCsrfTrustedOrigins:
    """
    docker-compose.prod.yml must set CSRF_TRUSTED_ORIGINS for the
    django-admin service so that browsers can POST to /api/admin/auth/
    without hitting Django's CSRF protection.

    Without this variable the admin panel shows a 403 error on login,
    which the user experiences as credentials being rejected (401-like).
    """

    def test_csrf_trusted_origins_env_var_present(self):
        """CSRF_TRUSTED_ORIGINS must be defined in django-admin environment."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        assert value is not None, (
            "django-admin service in docker-compose.prod.yml must set "
            "CSRF_TRUSTED_ORIGINS.  Without it, Django's CSRF middleware "
            "rejects POST login requests from the browser with 403 Forbidden, "
            "preventing admin login even with valid credentials from .env.\n\n"
            "Fix: add the following to the django-admin environment section:\n"
            "  - CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS:-"
            "http://localhost,http://${EXTERNAL_IP:-}}"
        )

    def test_csrf_trusted_origins_includes_localhost(self):
        """CSRF_TRUSTED_ORIGINS default must include at least one localhost origin."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        if value is None:
            import pytest
            pytest.skip("CSRF_TRUSTED_ORIGINS not set; covered by previous test")
        assert "localhost" in value, (
            f"CSRF_TRUSTED_ORIGINS='{value}' should include a localhost "
            f"origin (e.g. http://localhost) so the admin panel works on "
            f"a fresh deployment before a domain is configured."
        )

    def test_csrf_trusted_origins_includes_external_ip_placeholder(self):
        """CSRF_TRUSTED_ORIGINS must support per-deployment IP override via EXTERNAL_IP."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        if value is None:
            import pytest
            pytest.skip("CSRF_TRUSTED_ORIGINS not set; covered by previous test")
        # Value must reference EXTERNAL_IP or DOMAIN so operators can configure
        # their server's IP/domain without editing the compose file.
        assert "EXTERNAL_IP" in value or "DOMAIN" in value, (
            f"CSRF_TRUSTED_ORIGINS='{value}' should reference ${{EXTERNAL_IP}} "
            f"or ${{DOMAIN}} so operators can configure the correct origin for "
            f"their deployment via the .env file."
        )


class TestProdComposeAdminLoginFlow:
    """
    Verify the overall admin authentication configuration in docker-compose.prod.yml
    is complete — credentials in .env should be sufficient to log in.
    """

    def test_superuser_password_env_var_present(self):
        """DJANGO_SUPERUSER_PASSWORD must be configurable via environment."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "DJANGO_SUPERUSER_PASSWORD")
        assert value is not None, (
            "django-admin service must expose DJANGO_SUPERUSER_PASSWORD "
            "so that a superuser can be auto-created from .env credentials."
        )

    def test_superuser_username_env_var_present(self):
        """DJANGO_SUPERUSER_USERNAME must be configurable via environment."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "DJANGO_SUPERUSER_USERNAME")
        assert value is not None, (
            "django-admin service must expose DJANGO_SUPERUSER_USERNAME "
            "so that the admin username is configurable from .env."
        )

    def test_cors_allowed_origins_present(self):
        """CORS_ALLOWED_ORIGINS must be present so the admin panel JS can reach the API."""
        compose = load_prod_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CORS_ALLOWED_ORIGINS")
        assert value is not None, (
            "django-admin service must set CORS_ALLOWED_ORIGINS "
            "so that the React admin panel can make cross-origin API requests."
        )


class TestEntrypointSuperuserCreation:
    """
    Verify that entrypoint.sh creates the superuser using Django's built-in
    auth (django.contrib.auth.models.User) which is what the admin login
    endpoint authenticates against.
    """

    def _read_entrypoint(self):
        path = os.path.join(ROOT, "core", "entrypoint.sh")
        with open(path) as f:
            return f.read()

    def test_entrypoint_uses_django_auth_user(self):
        """entrypoint.sh must create superuser via django.contrib.auth.models.User."""
        content = self._read_entrypoint()
        assert "django.contrib.auth.models" in content or "create_superuser" in content, (
            "entrypoint.sh must create the superuser using Django's built-in "
            "auth model so that session-based admin login works correctly."
        )

    def test_entrypoint_checks_existing_user(self):
        """entrypoint.sh must be idempotent — skip creation if user already exists."""
        content = self._read_entrypoint()
        assert "exists" in content, (
            "entrypoint.sh superuser creation must be idempotent: check "
            "if the user already exists before attempting to create it."
        )
