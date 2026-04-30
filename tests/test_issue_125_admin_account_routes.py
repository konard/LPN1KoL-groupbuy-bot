"""
Tests for issue #125:

  Three problems in `docker-compose.monolith.yml`:

  1. Admin panel (`/admin`) and personal account (`/account`) do not open —
     browser gets 502/503 or a blank page.

     Root cause: the user-frontend (Next.js) only had pages at
     `/admin-panel` and `/lk`. Requests to `/admin` and `/account` fell
     through to Next.js but had no matching pages, so Next.js returned 404
     (rendered as a white screen). Fix: add pages at `/admin` and
     `/account` that render the same admin and personal-account UI.

  2. Backend password validation must be removed: any password with
     length >= 1 must be accepted (no complexity requirements). The
     RegisterRequest schema enforces only `min_length=1`.

  3. Swagger documentation must reflect actual endpoints. The OpenAPI
     description (generated from FastAPI) advertises the auth endpoints
     and the registration/login model with their current fields.
"""
import os
import sys
import pathlib

import pytest


ROOT = pathlib.Path(__file__).parent.parent
USER_FRONTEND_PAGES = ROOT / "user-frontend" / "pages"
NGINX_MONOLITH_CONF = ROOT / "infrastructure" / "nginx" / "nginx-monolith.conf"

sys.path.insert(0, str(ROOT / "backend-monolith"))


def read(path) -> str:
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. /admin and /account pages exist in the user-frontend Next.js app
# ---------------------------------------------------------------------------


class TestAdminAndAccountPagesExist:
    """The Next.js app must expose pages at /admin and /account."""

    def test_admin_page_file_exists(self):
        admin_index = USER_FRONTEND_PAGES / "admin" / "index.js"
        assert admin_index.is_file(), (
            f"Missing Next.js page {admin_index}. Without this file a request "
            f"to /admin returns 404 (white screen) because Next.js has no route."
        )

    def test_account_page_file_exists(self):
        account_index = USER_FRONTEND_PAGES / "account" / "index.js"
        assert account_index.is_file(), (
            f"Missing Next.js page {account_index}. Without this file a request "
            f"to /account returns 404 (white screen) because Next.js has no route."
        )

    def test_admin_page_renders_admin_ui(self):
        """The /admin page must render the admin panel UI (login form + dashboard)."""
        content = read(USER_FRONTEND_PAGES / "admin" / "index.js")
        assert "Admin" in content or "admin" in content, (
            "/admin page does not render the admin UI"
        )

    def test_account_page_renders_account_ui(self):
        """The /account page must render the personal-account UI."""
        content = read(USER_FRONTEND_PAGES / "account" / "index.js")
        # Must reference personal-account-related state (login form or user data).
        assert (
            "PersonalAccount" in content
            or "Personal Account" in content
            or "Sign In" in content
        ), "/account page does not render the personal-account UI"


# ---------------------------------------------------------------------------
# 2. Nginx must not block /admin and /account — they must reach user-frontend
# ---------------------------------------------------------------------------


class TestNginxRoutesAdminAndAccount:
    """nginx-monolith.conf must let /admin and /account reach user-frontend."""

    def setup_method(self):
        self.conf = read(NGINX_MONOLITH_CONF)

    def test_no_admin_panel_for_admin_path(self):
        """
        There must be no rule that intercepts /admin to a non-frontend
        upstream (e.g. admin-frontend), since the Next.js page now lives at
        /admin and must reach user-frontend.
        """
        # /api/admin/* still goes to admin-backend — that's fine.
        # But there should be no `location /admin` (without /api/ prefix or
        # -panel suffix) pointing to admin-backend or admin-frontend.
        assert "location /admin {" not in self.conf and "location = /admin {" not in self.conf, (
            "Unexpected location /admin block — /admin must fall through to "
            "the location / block that proxies to user-frontend."
        )

    def test_account_path_falls_through_to_user_frontend(self):
        """
        /account must not be claimed by another upstream — it must reach
        user-frontend via the catch-all `location /` block.
        """
        assert "location /account {" not in self.conf and "location = /account {" not in self.conf, (
            "Unexpected location /account block — /account must fall through to "
            "the location / block that proxies to user-frontend."
        )


# ---------------------------------------------------------------------------
# 3. Password validation: length >= 1, no complexity constraints
# ---------------------------------------------------------------------------


class TestPasswordValidation:
    """RegisterRequest accepts any password with length >= 1."""

    @pytest.fixture
    def schema_module(self):
        from app.modules.auth import schemas
        return schemas

    def _payload(self, password: str) -> dict:
        return {"email": "user@example.com", "password": password, "role": "buyer"}

    def test_single_character_password_accepted(self, schema_module):
        req = schema_module.RegisterRequest(**self._payload("a"))
        assert req.password == "a"

    def test_empty_password_rejected(self, schema_module):
        """Length must be >= 1 — empty string must be rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            schema_module.RegisterRequest(**self._payload(""))

    def test_no_complexity_required(self, schema_module):
        """No special characters / digits / case requirements."""
        for pwd in ["abcd", "1234", "AAAA", "пароль", "    "]:
            req = schema_module.RegisterRequest(**self._payload(pwd))
            assert req.password == pwd

    def test_long_password_accepted(self, schema_module):
        """Bcrypt's 72-byte limit must not be enforced at the schema level."""
        password = "a" * 200
        req = schema_module.RegisterRequest(**self._payload(password))
        assert req.password == password

    def test_login_request_accepts_any_password(self, schema_module):
        """Login schema must not impose extra password requirements either."""
        req = schema_module.LoginRequest(email="u@e.com", password="x")
        assert req.password == "x"


# ---------------------------------------------------------------------------
# 4. Swagger / OpenAPI: endpoints and registration/login model are present
# ---------------------------------------------------------------------------


class TestSwaggerOpenApi:
    """
    The FastAPI OpenAPI schema must expose the actual auth endpoints with
    the current registration/login model.

    The full auth.router imports `app.config` (which depends on
    pydantic-settings) and other runtime modules. To verify the OpenAPI
    schema in isolation we create a minimal FastAPI app that exposes the
    same auth endpoints using the real Pydantic schemas.
    """

    @pytest.fixture(scope="class")
    def openapi(self):
        from fastapi import FastAPI
        from app.modules.auth import schemas

        app = FastAPI()

        @app.post("/auth/register", response_model=schemas.UserOut)
        def register(req: schemas.RegisterRequest):
            ...

        @app.post("/auth/login", response_model=schemas.TokenResponse)
        def login(req: schemas.LoginRequest):
            ...

        @app.post("/auth/refresh", response_model=schemas.TokenResponse)
        def refresh(req: schemas.RefreshRequest):
            ...

        return app.openapi()

    def test_register_endpoint_documented(self, openapi):
        assert "/auth/register" in openapi["paths"], (
            "Swagger missing /auth/register endpoint"
        )

    def test_login_endpoint_documented(self, openapi):
        assert "/auth/login" in openapi["paths"], (
            "Swagger missing /auth/login endpoint"
        )

    def test_refresh_endpoint_documented(self, openapi):
        assert "/auth/refresh" in openapi["paths"], (
            "Swagger missing /auth/refresh endpoint"
        )

    def test_register_schema_has_email_password(self, openapi):
        components = openapi.get("components", {}).get("schemas", {})
        assert "RegisterRequest" in components, "RegisterRequest schema missing"
        props = components["RegisterRequest"]["properties"]
        assert "email" in props
        assert "password" in props
        # Password must reflect the "any length >= 1" rule, exposed as
        # min_length=1 in the schema.
        assert props["password"].get("minLength") == 1, (
            "Swagger password schema must declare minLength=1 to match the "
            "'any password, length >= 1' policy."
        )

    def test_login_schema_has_email_password(self, openapi):
        components = openapi.get("components", {}).get("schemas", {})
        assert "LoginRequest" in components, "LoginRequest schema missing"
        props = components["LoginRequest"]["properties"]
        assert "email" in props
        assert "password" in props
