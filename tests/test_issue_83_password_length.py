"""
Tests for issue #83: password longer than 72 bytes must be rejected with a validation
error before reaching bcrypt, instead of leaking an INTERNAL_ERROR (500).

bcrypt silently truncates or raises on passwords > 72 bytes depending on the
implementation. The fix adds max_length=72 to RegisterRequest.password so Pydantic
rejects the request early with a clear validation error.
"""

import pytest
from pydantic import ValidationError

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend-monolith"))

from app.modules.auth.schemas import RegisterRequest


class TestRegisterRequestPasswordValidation:
    """Validate RegisterRequest password length constraints."""

    def _base_payload(self, password: str) -> dict:
        return {
            "email": "user@example.com",
            "password": password,
            "first_name": "Иван",
            "last_name": "Иванов",
            "role": "buyer",
        }

    def test_valid_password_accepted(self):
        """A normal password within limits must be accepted without error."""
        req = RegisterRequest(**self._base_payload("securepassword123"))
        assert req.password == "securepassword123"

    def test_password_too_short_rejected(self):
        """Password shorter than 6 characters must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base_payload("abc"))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_password_exactly_72_bytes_accepted(self):
        """Password of exactly 72 ASCII characters (72 bytes) must be accepted."""
        password = "a" * 72
        req = RegisterRequest(**self._base_payload(password))
        assert len(req.password) == 72

    def test_password_73_bytes_rejected(self):
        """Password of 73 ASCII characters (73 bytes) must be rejected with a validation error,
        not an INTERNAL_ERROR from bcrypt."""
        password = "a" * 73
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base_payload(password))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors), (
            "Expected validation error on 'password' field for length > 72"
        )

    def test_password_100_bytes_rejected(self):
        """Password well above the 72-byte bcrypt limit must be rejected."""
        password = "x" * 100
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**self._base_payload(password))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_password_too_long_error_is_not_internal(self):
        """Submitting a password > 72 bytes must NOT raise an unhandled exception
        (which would become INTERNAL_ERROR), only a Pydantic ValidationError."""
        password = "p" * 73
        try:
            RegisterRequest(**self._base_payload(password))
            pytest.fail("Expected ValidationError was not raised")
        except ValidationError:
            pass  # correct — Pydantic rejected it before bcrypt was called
        except Exception as exc:
            pytest.fail(
                f"Expected ValidationError but got {type(exc).__name__}: {exc} — "
                "this would surface as INTERNAL_ERROR to API callers"
            )
