"""
Tests for issue #105 fixes (updated for issue #107).

Issue #107 requests that password validation be removed from the backend.
The byte-length validator added in #105 has been removed, so passwords of any
length are now accepted by RegisterRequest.

Remaining checks:
1. docker-compose.monolith.yml: gateway service is present and all service
   URLs point to backend-monolith.
2. nginx-monolith.conf: /admin-panel/ routes to user-frontend, and the
   user-frontend/pages/admin-panel/index.js page exists.
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
# 1.  Password validation removed (issue #107)
# ---------------------------------------------------------------------------

class TestPasswordValidationRemoved:
    """Passwords of any length must be accepted — validation removed per issue #107."""

    def _base(self, password: str) -> dict:
        return {
            "email": "user@example.com",
            "password": password,
            "role": "buyer",
        }

    def test_short_password_accepted(self):
        """Short passwords are now accepted."""
        req = RegisterRequest(**self._base("abc"))
        assert req.password == "abc"

    def test_37_cyrillic_chars_accepted(self):
        """37 Cyrillic chars (74 UTF-8 bytes) are now accepted."""
        password = "а" * 37
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_72_ascii_chars_accepted(self):
        """72 ASCII chars are accepted."""
        password = "x" * 72
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_73_ascii_chars_accepted(self):
        """73 ASCII chars are now accepted (no byte-length limit)."""
        password = "x" * 73
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_normal_password_accepted(self):
        """Normal passwords continue to work."""
        req = RegisterRequest(**self._base("securepassword123"))
        assert req.password == "securepassword123"


# ---------------------------------------------------------------------------
# 2.  docker-compose.monolith.yml gateway presence
# ---------------------------------------------------------------------------


class TestMonolithGatewayConfig:
    """Gateway service must be defined in docker-compose.monolith.yml."""

    @pytest.fixture(scope="class")
    def compose(self):
        path = ROOT / "docker-compose.monolith.yml"
        with open(path) as f:
            return yaml.safe_load(f)

    def test_gateway_service_present(self, compose):
        assert "gateway" in compose["services"], (
            "docker-compose.monolith.yml must contain a 'gateway' service"
        )

    def test_gateway_points_to_monolith(self, compose):
        env = compose["services"]["gateway"].get("environment", {})
        for key, val in env.items():
            if key.endswith("_SERVICE_URL") and "analytics" not in key.lower():
                assert "backend-monolith" in str(val), (
                    f"Gateway env var {key}={val} should point to backend-monolith "
                    "in the monolith deployment"
                )


# ---------------------------------------------------------------------------
# 3.  nginx-monolith.conf: /admin-panel/ routed to user-frontend
# ---------------------------------------------------------------------------


class TestNginxAdminPanelRouting:
    """nginx-monolith.conf must route /admin-panel/ to user-frontend."""

    @pytest.fixture(scope="class")
    def nginx_conf(self):
        path = ROOT / "infrastructure" / "nginx" / "nginx-monolith.conf"
        with open(path) as f:
            return f.read()

    def _admin_panel_blocks(self, conf: str):
        return re.findall(
            r"location\s+/admin-panel/\s*\{([^}]+)\}",
            conf,
            re.DOTALL,
        )

    def test_admin_panel_location_exists(self, nginx_conf):
        blocks = self._admin_panel_blocks(nginx_conf)
        assert len(blocks) >= 1, "nginx-monolith.conf must have a location /admin-panel/ block"

    def test_admin_panel_routes_to_user_frontend(self, nginx_conf):
        blocks = self._admin_panel_blocks(nginx_conf)
        for body in blocks:
            assert "user-frontend" in body, (
                "location /admin-panel/ must proxy to user-frontend.\n"
                f"Block body:\n{body}"
            )
            assert "admin_frontend" not in body, (
                "location /admin-panel/ must not proxy to admin_frontend upstream.\n"
                f"Block body:\n{body}"
            )

    def test_user_frontend_admin_panel_page_exists(self):
        page = ROOT / "user-frontend" / "pages" / "admin-panel" / "index.js"
        assert page.exists(), (
            "user-frontend/pages/admin-panel/index.js must exist so Next.js "
            "serves /admin-panel/ route"
        )
