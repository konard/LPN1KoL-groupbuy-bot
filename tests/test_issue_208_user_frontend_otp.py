"""
Tests for issue #208: user-frontend must implement phone+OTP login flow.

The issue says "Not implemented" pointing at PR #210, which added OTP auth
endpoints to the gateway and notification service.  The user-frontend pages
still used an email+password form that never worked with the new backend.

Required changes:
  1. user-frontend/pages/index.js and user-frontend/pages/lk/index.js must
     implement a two-step OTP login: phone input → OTP code input.
  2. POST /api/v1/auth/login must be called with {phone} (step 1).
  3. POST /api/v1/auth/login/confirm must be called with {phone, otp} (step 2).
  4. user-frontend/next.config.js must proxy /api/v1/* to the gateway
     so auth endpoints are reachable from the frontend.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
PAGES = [
    ROOT / "user-frontend" / "pages" / "index.js",
    ROOT / "user-frontend" / "pages" / "lk" / "index.js",
]
NEXT_CONFIG = ROOT / "user-frontend" / "next.config.js"


def read(path):
    return path.read_text()


# ---------------------------------------------------------------------------
# next.config.js: /api/v1/* must be proxied to the gateway
# ---------------------------------------------------------------------------

class TestNextConfigGatewayProxy:
    """The Next.js config must proxy /api/v1/* to the microservices gateway."""

    def test_gateway_url_env_referenced(self):
        src = read(NEXT_CONFIG)
        assert "GATEWAY_URL" in src, (
            "user-frontend/next.config.js must reference GATEWAY_URL env var so "
            "/api/v1/* requests are forwarded to the gateway (issue #208)."
        )

    def test_api_v1_rewrite_rule_exists(self):
        src = read(NEXT_CONFIG)
        assert "/api/v1/" in src or "api/v1" in src, (
            "user-frontend/next.config.js must have a rewrite rule for /api/v1/* "
            "so OTP login endpoints are reachable from the frontend (issue #208)."
        )

    def test_gateway_default_url_is_gateway_service(self):
        src = read(NEXT_CONFIG)
        assert "gateway:3000" in src, (
            "user-frontend/next.config.js must default GATEWAY_URL to "
            "'http://gateway:3000' so it works inside the Docker network (issue #208)."
        )


# ---------------------------------------------------------------------------
# Frontend pages: must NOT use email+password login
# ---------------------------------------------------------------------------

class TestNoEmailPasswordLogin:
    """OTP pages must not use email+password login (replaced by phone+OTP)."""

    def test_index_no_password_field(self):
        src = read(PAGES[0])
        assert 'type="password"' not in src and "type='password'" not in src, (
            "user-frontend/pages/index.js must not render a password input — "
            "login uses phone+OTP, not email+password (issue #208)."
        )

    def test_lk_no_password_field(self):
        src = read(PAGES[1])
        assert 'type="password"' not in src and "type='password'" not in src, (
            "user-frontend/pages/lk/index.js must not render a password input — "
            "login uses phone+OTP, not email+password (issue #208)."
        )

    def test_index_no_email_login_state(self):
        src = read(PAGES[0])
        assert "{ email: ''," not in src and "{ email: \"\"," not in src, (
            "user-frontend/pages/index.js must not track email login state — "
            "the login form was replaced with a phone+OTP form (issue #208)."
        )

    def test_lk_no_email_login_state(self):
        src = read(PAGES[1])
        assert "{ email: ''," not in src and "{ email: \"\"," not in src, (
            "user-frontend/pages/lk/index.js must not track email login state — "
            "the login form was replaced with a phone+OTP form (issue #208)."
        )


# ---------------------------------------------------------------------------
# Frontend pages: step 1 — phone input form
# ---------------------------------------------------------------------------

class TestPhoneInputStep:
    """First step of OTP flow: user enters phone number."""

    def _check(self, path):
        src = read(path)
        return src

    def test_index_phone_state(self):
        src = self._check(PAGES[0])
        assert "phone" in src, (
            f"{PAGES[0].name}: must manage a 'phone' state variable for the OTP "
            "login flow (issue #208)."
        )

    def test_lk_phone_state(self):
        src = self._check(PAGES[1])
        assert "phone" in src, (
            f"{PAGES[1].name}: must manage a 'phone' state variable for the OTP "
            "login flow (issue #208)."
        )

    def test_index_phone_input_type_tel(self):
        src = self._check(PAGES[0])
        assert 'type="tel"' in src or "type='tel'" in src, (
            f"{PAGES[0].name}: phone input must use type='tel' for correct mobile "
            "keyboard display (issue #208)."
        )

    def test_lk_phone_input_type_tel(self):
        src = self._check(PAGES[1])
        assert 'type="tel"' in src or "type='tel'" in src, (
            f"{PAGES[1].name}: phone input must use type='tel' for correct mobile "
            "keyboard display (issue #208)."
        )

    def test_index_posts_to_auth_login_v1(self):
        src = self._check(PAGES[0])
        assert "/api/v1/auth/login" in src, (
            f"{PAGES[0].name}: must POST to /api/v1/auth/login with {{phone}} as "
            "step 1 of the OTP login flow (issue #208)."
        )

    def test_lk_posts_to_auth_login_v1(self):
        src = self._check(PAGES[1])
        assert "/api/v1/auth/login" in src, (
            f"{PAGES[1].name}: must POST to /api/v1/auth/login with {{phone}} as "
            "step 1 of the OTP login flow (issue #208)."
        )


# ---------------------------------------------------------------------------
# Frontend pages: step 2 — OTP code entry
# ---------------------------------------------------------------------------

class TestOtpCodeStep:
    """Second step of OTP flow: user enters the code received by email."""

    def test_index_otp_state(self):
        src = read(PAGES[0])
        assert "otp" in src, (
            f"{PAGES[0].name}: must manage an 'otp' state variable for the code "
            "entry step of the OTP flow (issue #208)."
        )

    def test_lk_otp_state(self):
        src = read(PAGES[1])
        assert "otp" in src, (
            f"{PAGES[1].name}: must manage an 'otp' state variable for the code "
            "entry step of the OTP flow (issue #208)."
        )

    def test_index_posts_to_login_confirm(self):
        src = read(PAGES[0])
        assert "/api/v1/auth/login/confirm" in src, (
            f"{PAGES[0].name}: must POST to /api/v1/auth/login/confirm with "
            "{{phone, otp}} as step 2 of the OTP login flow (issue #208)."
        )

    def test_lk_posts_to_login_confirm(self):
        src = read(PAGES[1])
        assert "/api/v1/auth/login/confirm" in src, (
            f"{PAGES[1].name}: must POST to /api/v1/auth/login/confirm with "
            "{{phone, otp}} as step 2 of the OTP login flow (issue #208)."
        )

    def test_index_two_step_flow(self):
        src = read(PAGES[0])
        assert "step" in src, (
            f"{PAGES[0].name}: must implement a two-step login flow with a 'step' "
            "state variable ('phone' → 'otp') (issue #208)."
        )

    def test_lk_two_step_flow(self):
        src = read(PAGES[1])
        assert "step" in src, (
            f"{PAGES[1].name}: must implement a two-step login flow with a 'step' "
            "state variable ('phone' → 'otp') (issue #208)."
        )

    def test_index_confirms_login_sends_both_phone_and_otp(self):
        src = read(PAGES[0])
        confirm_match = re.search(
            r"login/confirm.*?JSON\.stringify\(.*?\)", src, re.DOTALL
        )
        assert confirm_match, (
            f"{PAGES[0].name}: the login/confirm request body must include both "
            "phone and otp fields (issue #208)."
        )
        body = confirm_match.group(0)
        assert "phone" in body and "otp" in body, (
            f"{PAGES[0].name}: JSON.stringify() for login/confirm must include both "
            "'phone' and 'otp' keys (issue #208)."
        )

    def test_lk_confirms_login_sends_both_phone_and_otp(self):
        src = read(PAGES[1])
        confirm_match = re.search(
            r"login/confirm.*?JSON\.stringify\(.*?\)", src, re.DOTALL
        )
        assert confirm_match, (
            f"{PAGES[1].name}: the login/confirm request body must include both "
            "phone and otp fields (issue #208)."
        )
        body = confirm_match.group(0)
        assert "phone" in body and "otp" in body, (
            f"{PAGES[1].name}: JSON.stringify() for login/confirm must include both "
            "'phone' and 'otp' keys (issue #208)."
        )


# ---------------------------------------------------------------------------
# Frontend pages: resend-code support
# ---------------------------------------------------------------------------

class TestResendCode:
    """Users must be able to request a new OTP code."""

    def test_index_resend_code_endpoint(self):
        src = read(PAGES[0])
        assert "resend-code" in src, (
            f"{PAGES[0].name}: must call /api/v1/auth/resend-code so users can "
            "request a new OTP if the first one expires (issue #208)."
        )

    def test_lk_resend_code_endpoint(self):
        src = read(PAGES[1])
        assert "resend-code" in src, (
            f"{PAGES[1].name}: must call /api/v1/auth/resend-code so users can "
            "request a new OTP if the first one expires (issue #208)."
        )

    def test_index_resend_context_login(self):
        src = read(PAGES[0])
        assert "'login'" in src or '"login"' in src, (
            f"{PAGES[0].name}: resend-code request must include context: 'login' "
            "so the backend sends the correct email subject (issue #208)."
        )

    def test_lk_resend_context_login(self):
        src = read(PAGES[1])
        assert "'login'" in src or '"login"' in src, (
            f"{PAGES[1].name}: resend-code request must include context: 'login' "
            "so the backend sends the correct email subject (issue #208)."
        )


# ---------------------------------------------------------------------------
# Frontend pages: token extraction and storage
# ---------------------------------------------------------------------------

class TestTokenHandling:
    """After successful OTP confirmation the access token must be stored."""

    def test_index_stores_token_in_localstorage(self):
        src = read(PAGES[0])
        assert "localStorage.setItem('token'" in src or 'localStorage.setItem("token"' in src, (
            f"{PAGES[0].name}: must persist the access token to localStorage after "
            "successful OTP confirmation (issue #208)."
        )

    def test_lk_stores_token_in_localstorage(self):
        src = read(PAGES[1])
        assert "localStorage.setItem('token'" in src or 'localStorage.setItem("token"' in src, (
            f"{PAGES[1].name}: must persist the access token to localStorage after "
            "successful OTP confirmation (issue #208)."
        )

    def test_index_uses_v1_auth_validate(self):
        src = read(PAGES[0])
        assert "/api/v1/auth/validate" in src, (
            f"{PAGES[0].name}: must call /api/v1/auth/validate to fetch the current "
            "user profile after login (issue #208)."
        )

    def test_lk_uses_v1_auth_validate(self):
        src = read(PAGES[1])
        assert "/api/v1/auth/validate" in src, (
            f"{PAGES[1].name}: must call /api/v1/auth/validate to fetch the current "
            "user profile after login (issue #208)."
        )
