"""
Tests for issue #212 — POST /api/v1/auth/login returns 422.

Root cause: `services/auth-service/Dockerfile` builds Python (`uvicorn app:app`),
but the previous `services/auth-service/app.py` exposed an email+password login
endpoint while the gateway and frontend now POST `{phone}` only.  FastAPI
therefore answered 422 (validation error) for the new request shape.

Fix: rewrite `app.py` to mirror the NestJS phone+OTP controller used elsewhere
in this repo (`services/auth-service/src/auth/auth.controller.ts`), so the
deployed Python service exposes the same endpoints the gateway proxies and the
frontend invokes.

These tests are static (file-text) checks only, matching the style of the
sibling test_issue_204/208/209 suites — they do not boot the service.
"""
from __future__ import annotations

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
APP_PATH = "services/auth-service/app.py"
REQS_PATH = "services/auth-service/requirements.txt"


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Dockerfile actually deploys Python `app.py` — guard against drift
# ---------------------------------------------------------------------------

class TestDockerfileBuildsPythonApp:
    def test_dockerfile_uses_python_base_image(self):
        df = read("services/auth-service/Dockerfile")
        assert "python" in df.lower(), (
            "auth-service Dockerfile must use a python base image so app.py is "
            "the runtime entrypoint that fixes the /api/v1/auth/login 422 error."
        )

    def test_dockerfile_runs_uvicorn_app_app(self):
        df = read("services/auth-service/Dockerfile")
        assert "uvicorn" in df and "app:app" in df, (
            "auth-service Dockerfile must run `uvicorn app:app` — this is the "
            "module the gateway forwards POST /api/v1/auth/login to."
        )


# ---------------------------------------------------------------------------
# requirements.txt — runtime deps the new app.py imports
# ---------------------------------------------------------------------------

class TestRequirements:
    def test_requirements_include_redis(self):
        reqs = read(REQS_PATH)
        assert re.search(r"^redis", reqs, re.MULTILINE), (
            "services/auth-service/requirements.txt must include the 'redis' "
            "package — app.py imports redis.asyncio for OTP session storage."
        )

    def test_requirements_include_asyncpg(self):
        reqs = read(REQS_PATH)
        assert "asyncpg" in reqs, (
            "requirements.txt must include asyncpg — app.py uses it for the "
            "users table where phone numbers and refresh-token hashes live."
        )

    def test_requirements_include_jose(self):
        reqs = read(REQS_PATH)
        assert "python-jose" in reqs or "jose" in reqs, (
            "requirements.txt must include python-jose for JWT signing."
        )

    def test_requirements_include_httpx(self):
        reqs = read(REQS_PATH)
        assert "httpx" in reqs, (
            "requirements.txt must include httpx — app.py uses it to call the "
            "notification-service /internal/send-otp endpoint."
        )


# ---------------------------------------------------------------------------
# app.py exposes the phone+OTP endpoints the gateway proxies
# ---------------------------------------------------------------------------

class TestAppHasPhoneOtpEndpoints:
    """
    The gateway forwards /api/v1/auth/<x> → http://auth-service:4001/auth/<x>.
    Each of these routes must exist in app.py (FastAPI strips the /auth prefix
    only if the request hits the gateway, so the Python service mounts each
    route at its bare path under /).
    """

    REQUIRED_ROUTES = [
        ("post", "/login"),
        ("post", "/login/confirm"),
        ("post", "/register"),
        ("post", "/register/confirm"),
        ("post", "/resend-code"),
        ("post", "/refresh"),
        ("post", "/logout"),
        ("get", "/validate"),
        ("get", "/me"),
        ("get", "/health"),
    ]

    def test_all_required_routes_are_registered(self):
        src = read(APP_PATH)
        missing = []
        for method, path in self.REQUIRED_ROUTES:
            decorator = f'@app.{method}("{path}"'
            if decorator not in src:
                missing.append(f"{method.upper()} {path}")
        assert not missing, (
            f"app.py must register these FastAPI routes (matching the gateway "
            f"PUBLIC_PATHS / proxy targets): {missing}"
        )


# ---------------------------------------------------------------------------
# /login accepts {phone} only — the original 422 cause
# ---------------------------------------------------------------------------

class TestLoginAcceptsPhoneOnly:
    def test_login_request_model_has_phone(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+LoginRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match, "app.py must declare a LoginRequest pydantic model"
        body = match.group(0)
        assert "phone" in body, (
            "LoginRequest must include a 'phone' field — the frontend POSTs "
            "{phone} to /api/v1/auth/login and any other shape returns 422."
        )

    def test_login_request_model_does_not_require_password(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+LoginRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match
        body = match.group(0)
        assert "password" not in body, (
            "LoginRequest must NOT require a 'password' field — issue #212 was "
            "the auth-service rejecting {phone}-only logins with 422 because "
            "the previous schema demanded email+password."
        )

    def test_login_request_model_does_not_require_email(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+LoginRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match
        body = match.group(0)
        assert "email" not in body, (
            "LoginRequest must NOT include an 'email' field — login is by "
            "phone, the OTP is delivered to the phone's registered email."
        )


# ---------------------------------------------------------------------------
# OTP confirm endpoint shape — frontend POSTs {phone, otp}
# ---------------------------------------------------------------------------

class TestConfirmLoginSchema:
    def test_confirm_login_model_has_phone_and_otp(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+ConfirmLoginRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match, "app.py must declare a ConfirmLoginRequest model"
        body = match.group(0)
        assert "phone" in body, "ConfirmLoginRequest must accept 'phone'"
        assert "otp" in body, "ConfirmLoginRequest must accept 'otp'"


# ---------------------------------------------------------------------------
# Register schema — phone + email
# ---------------------------------------------------------------------------

class TestRegisterSchema:
    def test_register_model_has_phone_and_email(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+RegisterRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match, "app.py must declare a RegisterRequest model"
        body = match.group(0)
        assert "phone" in body, "RegisterRequest must accept 'phone'"
        assert "email" in body, "RegisterRequest must accept 'email'"

    def test_register_model_does_not_require_password(self):
        src = read(APP_PATH)
        match = re.search(
            r"class\s+RegisterRequest\b.*?(?=\nclass\s+|\Z)", src, re.DOTALL
        )
        assert match
        body = match.group(0)
        assert "password" not in body, (
            "RegisterRequest must NOT require 'password' — registration is "
            "phone+email; identity is proven via the OTP sent to the email."
        )


# ---------------------------------------------------------------------------
# Phone validation
# ---------------------------------------------------------------------------

class TestPhoneValidation:
    def test_phone_regex_present(self):
        src = read(APP_PATH)
        assert "PHONE_RE" in src or r"\+?[1-9]" in src, (
            "app.py must validate phone numbers against an E.164-style regex."
        )


# ---------------------------------------------------------------------------
# OTP delivery + lifecycle
# ---------------------------------------------------------------------------

class TestOtpDelivery:
    def test_uses_notification_service_send_otp(self):
        src = read(APP_PATH)
        assert "/internal/send-otp" in src, (
            "app.py must POST to notification-service /internal/send-otp to "
            "deliver the OTP email."
        )

    def test_otp_ttl_is_set(self):
        src = read(APP_PATH)
        assert "OTP_TTL" in src or "600" in src, (
            "OTP sessions must have a TTL (default 600s = 10 minutes)."
        )

    def test_resend_cooldown_is_set(self):
        src = read(APP_PATH)
        assert "OTP_RESEND_COOLDOWN" in src or "cooldown" in src.lower(), (
            "Resend must enforce a cooldown to mitigate abuse."
        )

    def test_otp_generated_via_secrets_module(self):
        """OTP must be cryptographically random."""
        src = read(APP_PATH)
        assert "secrets" in src, (
            "OTP must be generated with the 'secrets' module (not random.random)."
        )


# ---------------------------------------------------------------------------
# Anti-enumeration on login
# ---------------------------------------------------------------------------

class TestLoginAntiEnumeration:
    def test_login_returns_generic_message_for_unknown_phone(self):
        src = read(APP_PATH)
        assert "If this number is registered" in src, (
            "Login must return a generic message for unknown phones to prevent "
            "user enumeration (matches NestJS auth.service.ts behaviour)."
        )


# ---------------------------------------------------------------------------
# Response envelope — frontend expects {success, data}
# ---------------------------------------------------------------------------

class TestResponseEnvelope:
    def test_success_envelope_used(self):
        src = read(APP_PATH)
        assert '"success": True' in src, (
            "All responses must use the {success: true, data: ...} envelope so "
            "the React/Next frontend can read response.data uniformly."
        )

    def test_login_returns_masked_email(self):
        src = read(APP_PATH)
        assert "maskedEmail" in src and "_mask_email" in src, (
            "Login response must include a maskedEmail field so the frontend "
            "can show the user a hint without leaking the full address."
        )


# ---------------------------------------------------------------------------
# Token issuance — JWT access + refresh
# ---------------------------------------------------------------------------

class TestTokenIssuance:
    def test_uses_jwt_library(self):
        src = read(APP_PATH)
        assert "jose" in src or "jwt.encode" in src, (
            "app.py must sign JWTs (python-jose) for access + refresh tokens."
        )

    def test_response_uses_camelcase_token_keys(self):
        src = read(APP_PATH)
        assert "accessToken" in src and "refreshToken" in src, (
            "Token response must use camelCase keys (accessToken, refreshToken) "
            "to match what the frontend stores in localStorage."
        )

    def test_refresh_token_stored_hashed(self):
        src = read(APP_PATH)
        assert "refresh_token_hash" in src and "pwd_ctx.hash" in src, (
            "The refresh token must be stored as a bcrypt hash, never in plain "
            "text — pwd_ctx.hash() is used for that."
        )


# ---------------------------------------------------------------------------
# Database schema — users table with phone column
# ---------------------------------------------------------------------------

class TestUsersTableHasPhone:
    def test_migrations_create_users_with_phone(self):
        src = read(APP_PATH)
        assert "CREATE TABLE IF NOT EXISTS users" in src, (
            "app.py must run an idempotent users table migration on startup."
        )
        match = re.search(
            r"CREATE TABLE IF NOT EXISTS users.*?\);", src, re.DOTALL
        )
        assert match, "users table DDL not found"
        ddl = match.group(0)
        assert "phone" in ddl, "users table must have a phone column (issue #212)."
        assert "email" in ddl, "users table must have an email column."

    def test_phone_column_has_unique_constraint(self):
        src = read(APP_PATH)
        match = re.search(
            r"CREATE TABLE IF NOT EXISTS users.*?\);", src, re.DOTALL
        )
        assert match
        ddl = match.group(0)
        # phone must be unique to prevent duplicate registrations
        phone_line = next(
            (line for line in ddl.split("\n") if line.strip().startswith("phone")),
            "",
        )
        assert "UNIQUE" in phone_line.upper(), (
            "users.phone must be UNIQUE to prevent duplicate registrations."
        )
