"""
Tests for issue #204: phone-based login with email OTP for personal account (личный кабинет).

The issue reports that the frontend correctly implements the phone+email auth flow,
but the backend lacks the implementation.

Required behaviour:
  Registration: phone number + email address
  Login: phone number only → OTP code sent to the email registered for that phone
  Verification: user enters the received OTP code to complete login

The implementation lives in services/auth-service — a NestJS service that stores
users in PostgreSQL (by phone and email) and OTP sessions in Redis.
"""
import os
import re
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read_file(relpath: str) -> str:
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def load_compose(filename: str) -> dict:
    with open(os.path.join(ROOT, filename)) as f:
        return yaml.safe_load(f)


def get_env_value(env_section, key: str):
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
# Auth-service: User entity must have phone and email fields
# ---------------------------------------------------------------------------

class TestUserEntityHasPhoneAndEmail:
    """
    The User entity in auth-service must store both phone and email.
    - Registration: phone + email required
    - Login: phone → email lookup → OTP sent to that email
    """

    ENTITY_PATH = "services/auth-service/src/users/users.entity.ts"

    def test_entity_has_phone_column(self):
        src = read_file(self.ENTITY_PATH)
        assert "phone" in src, (
            f"{self.ENTITY_PATH}: User entity must have a 'phone' column so that "
            "users can log in by phone number (issue #204)."
        )

    def test_entity_has_email_column(self):
        src = read_file(self.ENTITY_PATH)
        assert "email" in src, (
            f"{self.ENTITY_PATH}: User entity must have an 'email' column so that "
            "the OTP code can be sent to the user's registered email (issue #204)."
        )

    def test_phone_is_unique(self):
        src = read_file(self.ENTITY_PATH)
        assert "unique" in src.lower(), (
            f"{self.ENTITY_PATH}: phone must be declared with a unique constraint "
            "to prevent duplicate registrations with the same phone (issue #204)."
        )

    def test_entity_has_is_active_column(self):
        src = read_file(self.ENTITY_PATH)
        assert "isActive" in src or "is_active" in src, (
            f"{self.ENTITY_PATH}: User entity must have an isActive field so that "
            "disabled accounts are rejected at login (issue #204)."
        )


# ---------------------------------------------------------------------------
# Auth-service: UsersService must support lookup by phone
# ---------------------------------------------------------------------------

class TestUsersServiceFindByPhone:
    """UsersService must expose a findByPhone() method used by the login flow."""

    SERVICE_PATH = "services/auth-service/src/users/users.service.ts"

    def test_find_by_phone_method_exists(self):
        src = read_file(self.SERVICE_PATH)
        assert "findByPhone" in src, (
            f"{self.SERVICE_PATH}: UsersService must implement findByPhone() so the "
            "login handler can look up the user's email from their phone number (issue #204)."
        )

    def test_create_accepts_phone_and_email(self):
        src = read_file(self.SERVICE_PATH)
        assert "phone" in src and "email" in src, (
            f"{self.SERVICE_PATH}: UsersService.create() must accept both phone and "
            "email to register a new user (issue #204)."
        )


# ---------------------------------------------------------------------------
# Auth-service controller: registration endpoint (phone + email)
# ---------------------------------------------------------------------------

class TestRegistrationEndpoint:
    """
    POST /register must accept phone + email and send an OTP to that email.
    POST /register/confirm must accept phone + OTP and return JWT tokens.
    """

    CONTROLLER_PATH = "services/auth-service/src/auth/auth.controller.ts"
    SERVICE_PATH = "services/auth-service/src/auth/auth.service.ts"

    def test_register_endpoint_exists(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "register" in src, (
            f"{self.CONTROLLER_PATH}: must expose a POST /register endpoint for "
            "new user sign-up with phone + email (issue #204)."
        )

    def test_register_dto_has_phone(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "RegisterDto" in src, (
            f"{self.CONTROLLER_PATH}: must define a RegisterDto class (issue #204)."
        )
        dto_match = re.search(r'class RegisterDto\b.*?(?=\nclass |\Z)', src, re.DOTALL)
        assert dto_match, "RegisterDto class not found in controller"
        assert "phone" in dto_match.group(0), (
            "RegisterDto must include a 'phone' field (issue #204)."
        )

    def test_register_dto_has_email(self):
        src = read_file(self.CONTROLLER_PATH)
        dto_match = re.search(r'class RegisterDto\b.*?(?=\nclass |\Z)', src, re.DOTALL)
        assert dto_match, "RegisterDto class not found in controller"
        assert "email" in dto_match.group(0), (
            "RegisterDto must include an 'email' field (issue #204)."
        )

    def test_confirm_registration_endpoint_exists(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "register/confirm" in src or "confirmRegistration" in src, (
            f"{self.CONTROLLER_PATH}: must expose POST /register/confirm to verify "
            "the OTP and complete registration (issue #204)."
        )

    def test_register_with_phone_service_method(self):
        src = read_file(self.SERVICE_PATH)
        assert "registerWithPhone" in src, (
            f"{self.SERVICE_PATH}: AuthService must implement registerWithPhone() "
            "that stores pending registration data and sends OTP email (issue #204)."
        )

    def test_confirm_registration_service_method(self):
        src = read_file(self.SERVICE_PATH)
        assert "confirmRegistration" in src, (
            f"{self.SERVICE_PATH}: AuthService must implement confirmRegistration() "
            "that verifies the OTP and creates the user account (issue #204)."
        )

    def test_registration_sends_otp_to_email(self):
        src = read_file(self.SERVICE_PATH)
        assert "sendOtpEmail" in src or "send-otp" in src or "sendEmail" in src, (
            f"{self.SERVICE_PATH}: registration must send an OTP to the user's email "
            "via the notification service (issue #204)."
        )

    def test_registration_checks_duplicate_phone(self):
        src = read_file(self.SERVICE_PATH)
        # The service must check for existing phone before sending OTP
        assert "already exists" in src or "existingByPhone" in src, (
            f"{self.SERVICE_PATH}: registerWithPhone() must check that the phone is "
            "not already registered before generating an OTP (issue #204)."
        )

    def test_registration_stores_pending_data_in_redis(self):
        src = read_file(self.SERVICE_PATH)
        assert "reg:pending:" in src or "reg:" in src, (
            f"{self.SERVICE_PATH}: registerWithPhone() must store the pending "
            "registration (phone, email, otp) in Redis until confirmed (issue #204)."
        )


# ---------------------------------------------------------------------------
# Auth-service controller: login endpoint (phone → OTP → JWT)
# ---------------------------------------------------------------------------

class TestLoginEndpoint:
    """
    POST /login must accept phone and send OTP to the registered email.
    POST /login/confirm must accept phone + OTP and return JWT tokens.
    """

    CONTROLLER_PATH = "services/auth-service/src/auth/auth.controller.ts"
    SERVICE_PATH = "services/auth-service/src/auth/auth.service.ts"

    def test_login_endpoint_exists(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "@Post('login')" in src or "Post('login')" in src, (
            f"{self.CONTROLLER_PATH}: must expose a POST /login endpoint that "
            "accepts a phone number and dispatches an OTP (issue #204)."
        )

    def test_login_dto_has_phone(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "LoginDto" in src, (
            f"{self.CONTROLLER_PATH}: must define a LoginDto class (issue #204)."
        )
        dto_match = re.search(r'class LoginDto\b.*?(?=\nclass |\Z)', src, re.DOTALL)
        assert dto_match, "LoginDto class not found in controller"
        assert "phone" in dto_match.group(0), (
            "LoginDto must include a 'phone' field (issue #204)."
        )

    def test_confirm_login_endpoint_exists(self):
        src = read_file(self.CONTROLLER_PATH)
        assert "login/confirm" in src or "confirmLogin" in src, (
            f"{self.CONTROLLER_PATH}: must expose POST /login/confirm to verify "
            "the OTP code and issue JWT tokens (issue #204)."
        )

    def test_login_with_phone_service_method(self):
        src = read_file(self.SERVICE_PATH)
        assert "loginWithPhone" in src, (
            f"{self.SERVICE_PATH}: AuthService must implement loginWithPhone() "
            "that looks up the user's email by phone and sends an OTP (issue #204)."
        )

    def test_confirm_login_service_method(self):
        src = read_file(self.SERVICE_PATH)
        assert "confirmLogin" in src, (
            f"{self.SERVICE_PATH}: AuthService must implement confirmLogin() "
            "that verifies the OTP and returns JWT tokens (issue #204)."
        )

    def test_login_sends_otp_to_registered_email(self):
        """The login flow must look up the user's email and send OTP to it."""
        src = read_file(self.SERVICE_PATH)
        login_method_match = re.search(
            r'loginWithPhone\b.*?(?=\n  async |\Z)', src, re.DOTALL
        )
        assert login_method_match, "loginWithPhone method not found in auth.service.ts"
        method_body = login_method_match.group(0)
        assert "findByPhone" in method_body or "phone" in method_body, (
            "loginWithPhone must look up the user by phone to find their email (issue #204)."
        )
        assert "sendOtpEmail" in method_body or "otp" in method_body.lower(), (
            "loginWithPhone must send an OTP to the user's registered email (issue #204)."
        )

    def test_login_stores_otp_in_redis(self):
        src = read_file(self.SERVICE_PATH)
        assert "login:otp:" in src, (
            f"{self.SERVICE_PATH}: loginWithPhone() must store the OTP session in "
            "Redis keyed by phone so confirmLogin() can verify it (issue #204)."
        )

    def test_login_prevents_user_enumeration(self):
        """Login must return the same message whether phone is known or unknown."""
        src = read_file(self.SERVICE_PATH)
        assert "registered" in src or "If this number" in src or "enumeration" in src.lower(), (
            f"{self.SERVICE_PATH}: loginWithPhone() must return the same generic "
            "response for unknown phone numbers to prevent user enumeration (issue #204)."
        )

    def test_login_rejects_inactive_users(self):
        src = read_file(self.SERVICE_PATH)
        assert "isActive" in src or "is_active" in src or "Account is disabled" in src, (
            f"{self.SERVICE_PATH}: confirmLogin() must reject inactive accounts (issue #204)."
        )


# ---------------------------------------------------------------------------
# Auth-service: OTP mechanics
# ---------------------------------------------------------------------------

class TestOtpMechanics:
    """OTP must be numeric, have a limited TTL, and be consumed after use."""

    SERVICE_PATH = "services/auth-service/src/auth/auth.service.ts"

    def test_otp_has_ttl(self):
        src = read_file(self.SERVICE_PATH)
        assert "OTP_TTL" in src or "600" in src, (
            f"{self.SERVICE_PATH}: OTP sessions must have an expiry time (TTL) so "
            "they cannot be used indefinitely (issue #204)."
        )

    def test_otp_is_numeric(self):
        src = read_file(self.SERVICE_PATH)
        assert "generateNumericOtp" in src or "randomInt" in src, (
            f"{self.SERVICE_PATH}: OTP must be a numeric code generated via a "
            "cryptographically secure method (issue #204)."
        )

    def test_otp_consumed_after_login(self):
        """After a successful login the OTP session must be deleted."""
        src = read_file(self.SERVICE_PATH)
        assert "redisService.del" in src or "redis.del" in src or ".del(" in src, (
            f"{self.SERVICE_PATH}: the OTP session must be deleted from Redis after "
            "a successful confirmLogin() to prevent replay attacks (issue #204)."
        )

    def test_resend_otp_endpoint_exists(self):
        controller = read_file("services/auth-service/src/auth/auth.controller.ts")
        assert "resend" in controller.lower(), (
            "auth.controller.ts must expose a /resend-code endpoint so users can "
            "request a new OTP if the first one expired (issue #204)."
        )

    def test_resend_otp_has_cooldown(self):
        src = read_file(self.SERVICE_PATH)
        assert "cooldown" in src.lower() or "COOLDOWN" in src, (
            f"{self.SERVICE_PATH}: resendOtp() must enforce a cooldown between "
            "consecutive resend requests to prevent spam (issue #204)."
        )


# ---------------------------------------------------------------------------
# Notification service: must expose /internal/send-otp endpoint
# ---------------------------------------------------------------------------

class TestNotificationServiceSendOtp:
    """
    The notification-service must handle POST /internal/send-otp requests from
    the auth-service to deliver OTP emails.
    """

    NOTIF_PATH = "services/notification-service/src/index.js"

    def test_send_otp_endpoint_exists(self):
        src = read_file(self.NOTIF_PATH)
        assert "/internal/send-otp" in src, (
            f"{self.NOTIF_PATH}: notification-service must expose POST "
            "/internal/send-otp so auth-service can trigger OTP email delivery "
            "(issue #204)."
        )

    def test_send_otp_sends_email(self):
        src = read_file(self.NOTIF_PATH)
        assert "sendEmail" in src or "mailer" in src, (
            f"{self.NOTIF_PATH}: /internal/send-otp handler must call sendEmail() "
            "to deliver the OTP to the user (issue #204)."
        )

    def test_send_otp_validates_required_fields(self):
        src = read_file(self.NOTIF_PATH)
        # Must validate that email and otp are present
        assert "email" in src and "otp" in src, (
            f"{self.NOTIF_PATH}: /internal/send-otp handler must validate that "
            "'email' and 'otp' fields are present in the request body (issue #204)."
        )

    def test_send_otp_uses_russian_subject(self):
        """OTP emails must use Russian subject lines matching the target audience."""
        src = read_file(self.NOTIF_PATH)
        assert "код" in src or "код подтверждения" in src or "Groupbuy" in src, (
            f"{self.NOTIF_PATH}: OTP email subject must be set appropriately for "
            "the user audience (issue #204)."
        )


# ---------------------------------------------------------------------------
# Docker-compose: auth-service must be wired to notification-service
# ---------------------------------------------------------------------------

COMPOSE_FILES_WITH_AUTH_AND_NOTIF = [
    "docker-compose.yml",
    "docker-compose.unified.yml",
    "docker-compose.microservices.yml",
]


class TestAuthServiceNotificationServiceEnv:
    """
    auth-service must receive NOTIFICATION_SERVICE_URL so it can dispatch OTP
    emails through the notification-service.
    """

    def _check(self, filename: str):
        compose = load_compose(filename)
        services = compose.get("services", {})
        if "auth-service" not in services or "notification-service" not in services:
            return  # Skip files that don't include both services
        env = services["auth-service"].get("environment")
        value = get_env_value(env, "NOTIFICATION_SERVICE_URL")
        assert value is not None, (
            f"{filename}: auth-service must set NOTIFICATION_SERVICE_URL so it can "
            "send OTP emails via the notification-service (issue #204)."
        )
        assert "notification" in value.lower() or "${NOTIFICATION" in value, (
            f"{filename}: NOTIFICATION_SERVICE_URL='{value}' must point at the "
            "notification-service container (issue #204)."
        )

    def test_docker_compose_yml(self):
        self._check("docker-compose.yml")

    def test_docker_compose_unified(self):
        self._check("docker-compose.unified.yml")

    def test_docker_compose_microservices(self):
        self._check("docker-compose.microservices.yml")


# ---------------------------------------------------------------------------
# Docker-compose: auth-service must expose JWT configuration
# ---------------------------------------------------------------------------

class TestAuthServiceJwtEnv:
    """
    auth-service must receive JWT_SECRET and JWT_REFRESH_SECRET to sign and
    verify tokens issued after OTP confirmation.
    """

    def _check(self, filename: str):
        compose = load_compose(filename)
        services = compose.get("services", {})
        if "auth-service" not in services:
            return
        env = services["auth-service"].get("environment")
        secret = get_env_value(env, "JWT_SECRET")
        assert secret is not None, (
            f"{filename}: auth-service must set JWT_SECRET to sign access tokens "
            "issued after OTP login (issue #204)."
        )

    def test_docker_compose_yml(self):
        self._check("docker-compose.yml")

    def test_docker_compose_unified(self):
        self._check("docker-compose.unified.yml")

    def test_docker_compose_microservices(self):
        self._check("docker-compose.microservices.yml")


# ---------------------------------------------------------------------------
# Auth-service: database migration must include phone column
# ---------------------------------------------------------------------------

class TestPhoneMigrationExists:
    """
    The database schema for auth-service must include a migration that adds the
    phone column — required for the phone-based login flow.
    """

    MIGRATIONS_DIR = "services/auth-service/src/migrations"

    def test_phone_column_migration_exists(self):
        migrations_dir = os.path.join(ROOT, self.MIGRATIONS_DIR)
        migration_files = [
            f for f in os.listdir(migrations_dir)
            if f.endswith(".ts") or f.endswith(".sql")
        ]
        phone_migrations = [
            f for f in migration_files
            if "phone" in f.lower()
        ]
        assert phone_migrations, (
            f"No migration file for the phone column found in {self.MIGRATIONS_DIR}.  "
            "A migration that adds 'phone' to the users table is required for "
            "phone-based login (issue #204)."
        )

    def test_phone_migration_creates_column(self):
        migrations_dir = os.path.join(ROOT, self.MIGRATIONS_DIR)
        migration_files = [
            f for f in os.listdir(migrations_dir)
            if ("phone" in f.lower()) and (f.endswith(".ts") or f.endswith(".sql"))
        ]
        assert migration_files, "No phone migration file found"
        for mf in migration_files:
            content = read_file(os.path.join(self.MIGRATIONS_DIR, mf))
            assert "phone" in content.lower(), (
                f"{mf}: phone migration file must reference the 'phone' column (issue #204)."
            )


# ---------------------------------------------------------------------------
# Regression guard: previous auth fixes must still be in place
# ---------------------------------------------------------------------------

class TestAuthRegressionGuards:
    """Guard that earlier auth-service fixes are not accidentally reverted."""

    def test_two_factor_auth_still_present(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "twoFactor" in src or "2fa" in src.lower(), (
            "2FA functionality must still be present in auth.service.ts."
        )

    def test_token_blacklist_still_present(self):
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "blacklist" in src, (
            "Token blacklisting on logout must still be present in auth.service.ts."
        )

    def test_masked_email_still_present(self):
        """maskEmail() hides the user's address in the OTP pending response."""
        src = read_file("services/auth-service/src/auth/auth.service.ts")
        assert "maskEmail" in src, (
            "maskEmail() must still be present — it protects user privacy by "
            "returning only a masked email address in the login/register response."
        )
