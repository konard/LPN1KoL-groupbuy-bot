"""
Tests for issue #107:

1. Backend password validation removed: RegisterRequest must accept passwords
   of any length, including those previously rejected by the bcrypt byte-limit
   validator (e.g. 37 Cyrillic chars = 74 UTF-8 bytes).

2. docker-compose.monolith.yml: admin-frontend service removed — the admin
   panel is now served by user-frontend at /admin-panel/, matching the
   docker-compose.unified.yml approach.  nginx depends_on must not include
   admin-frontend.

3. nginx-monolith.conf: admin_frontend upstream removed since admin-frontend
   service no longer exists in the monolith deployment.
"""

import sys
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend-monolith"))

from app.modules.auth.schemas import RegisterRequest  # noqa: E402


# ---------------------------------------------------------------------------
# 1.  Password validation removed
# ---------------------------------------------------------------------------

class TestPasswordValidationRemoved:
    """Issue #107: password validation must be removed from RegisterRequest."""

    def _base(self, password: str) -> dict:
        return {"email": "test@example.com", "password": password, "role": "buyer"}

    def test_any_length_password_accepted(self):
        """Passwords of any length must be accepted."""
        for pwd in ["a", "ab", "abc", "x" * 100, "а" * 37]:
            req = RegisterRequest(**self._base(pwd))
            assert req.password == pwd

    def test_no_min_length_constraint(self):
        """Single-character passwords are accepted (no min_length)."""
        req = RegisterRequest(**self._base("x"))
        assert req.password == "x"

    def test_no_bcrypt_byte_limit(self):
        """Passwords exceeding 72 UTF-8 bytes are accepted."""
        password = "а" * 37  # 37 chars, 74 bytes
        assert len(password.encode("utf-8")) > 72
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_long_ascii_password_accepted(self):
        """Passwords longer than 72 ASCII chars are accepted."""
        password = "p" * 200
        req = RegisterRequest(**self._base(password))
        assert req.password == password


# ---------------------------------------------------------------------------
# 2.  admin-frontend removed from docker-compose.monolith.yml
# ---------------------------------------------------------------------------

class TestMonolithComposeAdminFrontend:
    """admin-frontend service must be absent from docker-compose.monolith.yml."""

    @pytest.fixture(scope="class")
    def compose(self):
        with open(ROOT / "docker-compose.monolith.yml") as f:
            return yaml.safe_load(f)

    def test_admin_frontend_service_absent(self, compose):
        assert "admin-frontend" not in compose["services"], (
            "admin-frontend service must be removed from docker-compose.monolith.yml; "
            "the admin panel is served by user-frontend at /admin-panel/"
        )

    def test_nginx_does_not_depend_on_admin_frontend(self, compose):
        nginx_deps = compose["services"]["nginx"].get("depends_on", {})
        assert "admin-frontend" not in nginx_deps, (
            "nginx depends_on must not include admin-frontend"
        )

    def test_user_frontend_service_present(self, compose):
        assert "user-frontend" in compose["services"], (
            "user-frontend must remain in docker-compose.monolith.yml"
        )


# ---------------------------------------------------------------------------
# 3.  admin_frontend upstream removed from nginx-monolith.conf
# ---------------------------------------------------------------------------

class TestNginxAdminFrontendUpstreamAbsent:
    """admin_frontend upstream must be removed from nginx-monolith.conf."""

    @pytest.fixture(scope="class")
    def nginx_conf(self):
        return (ROOT / "infrastructure" / "nginx" / "nginx-monolith.conf").read_text()

    def test_admin_frontend_upstream_absent(self, nginx_conf):
        assert "upstream admin_frontend" not in nginx_conf, (
            "nginx-monolith.conf must not define an admin_frontend upstream "
            "since admin-frontend service is removed"
        )

    def test_admin_panel_still_routes_to_user_frontend(self, nginx_conf):
        blocks = re.findall(
            r"location\s+/admin-panel/\s*\{([^}]+)\}", nginx_conf, re.DOTALL
        )
        assert blocks, "location /admin-panel/ block must exist"
        for body in blocks:
            assert "user-frontend" in body, (
                "/admin-panel/ must still proxy to user-frontend"
            )
