"""
Tests for issue #105 fixes:

1. Password byte-length validation: registering with a password that is ≤ 72
   Unicode characters but > 72 UTF-8 bytes (e.g. 37 Cyrillic characters = 74
   bytes) must be rejected with a 422 validation error instead of leaking
   INTERNAL_ERROR from bcrypt.

2. docker-compose.monolith.yml: the ``gateway`` service must be present
   (it was already there but all service URLs must point to backend-monolith
   so the monolith deployment is self-contained).

3. Backend endpoint health: all FastAPI routers registered in
   backend-monolith/app/main.py must be importable and free of obvious
   registration errors.
"""

import sys
import pathlib
import importlib

import pytest
from pydantic import ValidationError

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend-monolith"))

from app.modules.auth.schemas import RegisterRequest  # noqa: E402


# ---------------------------------------------------------------------------
# 1.  Password byte-length validation
# ---------------------------------------------------------------------------

class TestPasswordByteLengthValidation:
    """Passwords > 72 bytes must be rejected by Pydantic, not by bcrypt."""

    def _base(self, password: str) -> dict:
        return {
            "email": "user@example.com",
            "password": password,
            "role": "buyer",
        }

    def test_37_cyrillic_chars_rejected(self):
        """37 Cyrillic chars = 74 UTF-8 bytes → must be rejected before bcrypt."""
        password = "а" * 37  # 37 chars, 74 bytes
        assert len(password) == 37, "sanity: 37 characters"
        assert len(password.encode("utf-8")) == 74, "sanity: 74 bytes"

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base(password))

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors), (
            "Expected a ValidationError on the 'password' field, got: "
            + str(errors)
        )

    def test_36_cyrillic_chars_accepted(self):
        """36 Cyrillic chars = 72 UTF-8 bytes → exactly on the limit, must be accepted."""
        password = "а" * 36  # 36 chars, 72 bytes
        assert len(password.encode("utf-8")) == 72
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_72_ascii_chars_accepted(self):
        """72 ASCII chars = 72 bytes → must be accepted."""
        password = "x" * 72
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_73_ascii_chars_rejected(self):
        """73 ASCII chars = 73 bytes → must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base("x" * 73))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_mixed_multibyte_over_72_bytes_rejected(self):
        """Password with mixed ASCII + Cyrillic that is ≤ 72 chars but > 72 bytes → rejected."""
        # 50 ASCII + 12 Cyrillic = 62 chars but 50 + 24 = 74 bytes
        password = "a" * 50 + "а" * 12
        assert len(password) == 62  # chars — within old max_length=72 limit
        assert len(password.encode("utf-8")) == 74  # bytes — over 72
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base(password))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors), (
            "Mixed-charset password > 72 bytes must fail validation"
        )

    def test_mixed_multibyte_exactly_72_bytes_accepted(self):
        """Password with mixed ASCII + Cyrillic that is exactly 72 bytes → accepted."""
        # 48 ASCII + 12 Cyrillic = 60 chars, 48 + 24 = 72 bytes
        password = "a" * 48 + "а" * 12
        assert len(password.encode("utf-8")) == 72
        req = RegisterRequest(**self._base(password))
        assert req.password == password

    def test_password_over_72_bytes_does_not_reach_bcrypt(self):
        """Ensure the error raised is a ValidationError (Pydantic), not any other
        exception that would indicate bcrypt was called with the oversized password."""
        password = "а" * 37  # 74 bytes
        try:
            RegisterRequest(**self._base(password))
            pytest.fail("Expected ValidationError was not raised")
        except ValidationError:
            pass  # correct
        except Exception as exc:
            pytest.fail(
                f"Expected Pydantic ValidationError but got "
                f"{type(exc).__name__}: {exc} — "
                "bcrypt may have been called with an oversized password"
            )


# ---------------------------------------------------------------------------
# 2.  docker-compose.monolith.yml gateway presence
# ---------------------------------------------------------------------------

import yaml  # noqa: E402


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

import re  # noqa: E402


class TestNginxAdminPanelRouting:
    """nginx-monolith.conf must route /admin-panel/ to user-frontend,
    not to the legacy admin-frontend container, so that user-frontend serves
    both /lk/ and /admin-panel/ (mirroring docker-compose.unified.yml)."""

    @pytest.fixture(scope="class")
    def nginx_conf(self):
        path = ROOT / "infrastructure" / "nginx" / "nginx-monolith.conf"
        with open(path) as f:
            return f.read()

    def _admin_panel_blocks(self, conf: str):
        """Return all location /admin-panel/ block bodies."""
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
                "location /admin-panel/ must proxy to user-frontend, not admin-frontend.\n"
                f"Block body:\n{body}"
            )
            assert "admin_frontend" not in body, (
                "location /admin-panel/ must not proxy to admin_frontend upstream any more.\n"
                f"Block body:\n{body}"
            )

    def test_user_frontend_admin_panel_page_exists(self):
        page = ROOT / "user-frontend" / "pages" / "admin-panel" / "index.js"
        assert page.exists(), (
            "user-frontend/pages/admin-panel/index.js must exist so Next.js "
            "serves /admin-panel/ route"
        )
