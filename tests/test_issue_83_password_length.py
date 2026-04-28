"""
Tests for issue #83 (updated for issue #107).

Issue #107 requests that password validation be removed from the backend,
so RegisterRequest must accept passwords of any length (including those that
were previously rejected by the byte-length validator added in issue #83).

The backend no longer enforces min_length or bcrypt byte limits on the password
field — any non-empty string is accepted by Pydantic.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend-monolith"))

from app.modules.auth.schemas import RegisterRequest


class TestRegisterRequestPasswordValidation:
    """Verify that RegisterRequest accepts passwords without length restrictions."""

    def _base_payload(self, password: str) -> dict:
        return {
            "email": "user@example.com",
            "password": password,
            "first_name": "Иван",
            "last_name": "Иванов",
            "role": "buyer",
        }

    def test_valid_password_accepted(self):
        """A normal password must be accepted."""
        req = RegisterRequest(**self._base_payload("securepassword123"))
        assert req.password == "securepassword123"

    def test_short_password_accepted(self):
        """A short password (e.g. 3 chars) is accepted — validation removed per issue #107."""
        req = RegisterRequest(**self._base_payload("abc"))
        assert req.password == "abc"

    def test_password_exactly_72_bytes_accepted(self):
        """Password of exactly 72 ASCII characters must be accepted."""
        password = "a" * 72
        req = RegisterRequest(**self._base_payload(password))
        assert len(req.password) == 72

    def test_password_73_bytes_accepted(self):
        """Password of 73 bytes must now be accepted (no byte-length validation)."""
        password = "a" * 73
        req = RegisterRequest(**self._base_payload(password))
        assert req.password == password

    def test_password_100_bytes_accepted(self):
        """Long password must be accepted — no length limit enforced."""
        password = "x" * 100
        req = RegisterRequest(**self._base_payload(password))
        assert req.password == password

    def test_cyrillic_password_over_72_bytes_accepted(self):
        """37 Cyrillic chars (74 UTF-8 bytes) must now be accepted."""
        password = "а" * 37
        req = RegisterRequest(**self._base_payload(password))
        assert req.password == password
