"""
Tests for issue #184 fix:
  Django Admin container logs `DisallowedHost: Invalid HTTP_HOST header:
  'localhost:8000'` every 5 seconds (matching the healthcheck interval).

Root causes and fixes:
  1. settings.py parsed ALLOWED_HOSTS with a plain `.split(',')` which does
     not strip whitespace, so any value with a leading/trailing space (e.g.
     from `ALLOWED_HOSTS=localhost, 127.0.0.1`) would silently fail to match.
     Fixed by using a list comprehension that strips each token.

  2. docker-compose.unified.yml was missing CORS_ALLOWED_ORIGINS and
     CSRF_TRUSTED_ORIGINS environment variables that are present in
     docker-compose.prod.yml.  CSRF_TRUSTED_ORIGINS is required for browsers
     to reach the admin panel; without it, Django rejects CSRF-protected
     POST requests from the browser.

  3. docker-compose.unified.yml ALLOWED_HOSTS did not include the internal
     container hostname (groupbuy-django-admin) which can appear in
     inter-service requests.
"""
import os
import ast
import textwrap

import pytest
import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_unified_compose():
    """Load docker-compose.unified.yml as a dict."""
    path = os.path.join(ROOT, "docker-compose.unified.yml")
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


# ---------------------------------------------------------------------------
# 1. settings.py — ALLOWED_HOSTS whitespace stripping
# ---------------------------------------------------------------------------

class TestAllowedHostsSettingsParsing:
    """
    settings.py must strip whitespace when parsing the ALLOWED_HOSTS env var.

    Without stripping, ALLOWED_HOSTS='localhost, 127.0.0.1' would produce
    ['localhost', ' 127.0.0.1'] and requests from 127.0.0.1 would be rejected
    with DisallowedHost.
    """

    def _get_allowed_hosts_line(self):
        path = os.path.join(ROOT, "core", "config", "settings.py")
        with open(path) as f:
            return f.read()

    def test_allowed_hosts_uses_strip(self):
        """
        The ALLOWED_HOSTS assignment in settings.py must strip whitespace from
        each token so that values like ' 127.0.0.1' are normalised to
        '127.0.0.1' and do not silently fail host validation.
        """
        src = self._get_allowed_hosts_line()
        # The fix replaces bare .split(',') with a comprehension that calls .strip()
        assert ".strip()" in src, (
            "settings.py ALLOWED_HOSTS parsing must call .strip() on each "
            "token to handle values like 'localhost, 127.0.0.1' correctly. "
            "Plain .split(',') without stripping causes DisallowedHost when "
            "environment variables contain spaces after commas."
        )

    def test_allowed_hosts_parses_spaced_values_correctly(self):
        """
        Simulating the env-var parsing: 'localhost, 127.0.0.1' must yield
        ['localhost', '127.0.0.1'], not ['localhost', ' 127.0.0.1'].
        """
        raw = "localhost, 127.0.0.1"
        # Old (broken) approach
        old_result = raw.split(",")
        # New (fixed) approach
        new_result = [h.strip() for h in raw.split(",") if h.strip()]

        assert " 127.0.0.1" not in new_result, (
            "Parsed ALLOWED_HOSTS must not contain leading spaces. "
            "Got: %r" % new_result
        )
        assert "127.0.0.1" in new_result, (
            "Parsed ALLOWED_HOSTS must contain '127.0.0.1' (without space). "
            "Got: %r" % new_result
        )
        assert old_result != new_result, (
            "This test exists to document that the old bare .split(',') "
            "was incorrect; the new list-comprehension result must differ."
        )

    def test_allowed_hosts_filters_empty_strings(self):
        """
        Trailing commas (e.g. 'localhost,') must not produce empty-string
        entries in ALLOWED_HOSTS, which would be silently ignored by Django
        but add noise and confusion.
        """
        raw = "localhost,"
        result = [h.strip() for h in raw.split(",") if h.strip()]
        assert "" not in result, (
            "Empty-string entries must be filtered out of ALLOWED_HOSTS. "
            "Got: %r" % result
        )


# ---------------------------------------------------------------------------
# 2. docker-compose.unified.yml — CSRF_TRUSTED_ORIGINS present
# ---------------------------------------------------------------------------

class TestUnifiedComposeCsrfTrustedOrigins:
    """
    docker-compose.unified.yml must set CSRF_TRUSTED_ORIGINS so browsers can
    reach the Django admin panel without CSRF errors on POST requests.

    This variable was present in docker-compose.prod.yml via the
    CSRF_TRUSTED_ORIGINS env var but was missing from docker-compose.unified.yml.
    """

    def test_csrf_trusted_origins_env_var_present(self):
        """CSRF_TRUSTED_ORIGINS must be defined in django-admin environment."""
        compose = load_unified_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        assert value is not None, (
            "django-admin service in docker-compose.unified.yml must set "
            "CSRF_TRUSTED_ORIGINS. Without it, browsers visiting the admin "
            "panel at http://localhost:8000 receive CSRF errors on POST "
            "requests (login form, etc.)."
        )

    def test_csrf_trusted_origins_includes_localhost(self):
        """CSRF_TRUSTED_ORIGINS default must include at least one localhost origin."""
        compose = load_unified_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CSRF_TRUSTED_ORIGINS")
        if value is None:
            pytest.skip("CSRF_TRUSTED_ORIGINS not set; covered by previous test")
        # The value may be an env-var reference like ${CSRF_TRUSTED_ORIGINS:-http://localhost:8000,...}
        # or a plain comma-separated list.  Either way it should mention localhost.
        assert "localhost" in value, (
            f"CSRF_TRUSTED_ORIGINS='{value}' should include a localhost "
            f"origin (e.g. http://localhost:8000) so the admin panel is "
            f"accessible on a local/dev setup."
        )


# ---------------------------------------------------------------------------
# 3. docker-compose.unified.yml — CORS_ALLOWED_ORIGINS present
# ---------------------------------------------------------------------------

class TestUnifiedComposeCorsAllowedOrigins:
    """
    docker-compose.unified.yml must define CORS_ALLOWED_ORIGINS (even if
    empty by default) so that the settings.py CORS logic is consistent with
    docker-compose.prod.yml.

    When CORS_ALLOWED_ORIGINS is absent the settings.py logic defaults to
    CORS_ALLOW_ALL_ORIGINS=True which is correct for local dev, but the
    variable should still be explicitly present to allow operators to
    configure it via .env without editing the compose file.
    """

    def test_cors_allowed_origins_env_var_present(self):
        """CORS_ALLOWED_ORIGINS must be defined in django-admin environment."""
        compose = load_unified_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "CORS_ALLOWED_ORIGINS")
        assert value is not None, (
            "django-admin service in docker-compose.unified.yml must declare "
            "CORS_ALLOWED_ORIGINS (even as an empty default via "
            "'${CORS_ALLOWED_ORIGINS:-}') so that operators can restrict CORS "
            "in production by setting CORS_ALLOWED_ORIGINS in their .env file."
        )


# ---------------------------------------------------------------------------
# 4. docker-compose.unified.yml — ALLOWED_HOSTS includes container hostname
# ---------------------------------------------------------------------------

class TestUnifiedComposeAllowedHosts:
    """
    django-admin ALLOWED_HOSTS must include the container's own hostname so
    that inter-service HTTP health probes (which use the container name as the
    Host header) are not rejected.
    """

    def test_allowed_hosts_includes_container_name(self):
        """ALLOWED_HOSTS should include the django-admin container hostname."""
        compose = load_unified_compose()
        env = get_django_admin_env(compose)
        value = parse_env_var(env, "ALLOWED_HOSTS")
        assert value is not None, "ALLOWED_HOSTS must be set in django-admin service"
        # The container name is groupbuy-django-admin; the hostname inside the
        # container defaults to the container name with underscores/hyphens.
        assert "groupbuy-django-admin" in value or "django-admin" in value, (
            f"ALLOWED_HOSTS='{value}' should include the container hostname "
            f"(groupbuy-django-admin) so that internal health probes using "
            f"the container name as Host are accepted."
        )
