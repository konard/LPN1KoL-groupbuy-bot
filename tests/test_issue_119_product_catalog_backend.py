"""
Tests for issue #119: product-catalog-backend startup crash due to
passlib[bcrypt]==1.7.4 incompatibility with bcrypt>=4.0.0.

The fix pins bcrypt==4.0.1 in requirements.txt, which ships with a
workaround for the 72-byte password detection routine that caused:

    ValueError: password cannot be longer than 72 bytes,
    truncate manually if necessary (e.g. my_password[:72])

Also verifies that all HTTP error messages in the product-catalog backend
use Russian text as requested in the issue.
"""

import importlib
import pathlib
import re
import subprocess
import sys


REQUIREMENTS_PATH = pathlib.Path(__file__).parent.parent / "product-catalog" / "backend" / "requirements.txt"
MAIN_PATH = pathlib.Path(__file__).parent.parent / "product-catalog" / "backend" / "main.py"


class TestBcryptVersionPinned:
    """requirements.txt must pin bcrypt to a version compatible with passlib 1.7.4."""

    def test_bcrypt_pinned_in_requirements(self):
        """bcrypt must be explicitly pinned to avoid the passlib startup crash."""
        text = REQUIREMENTS_PATH.read_text()
        assert "bcrypt==" in text, (
            "bcrypt must be explicitly pinned in requirements.txt. "
            "passlib==1.7.4 crashes at startup with bcrypt>=4.0.0 unless "
            "bcrypt is pinned to a compatible version (e.g. bcrypt==4.0.1)."
        )

    def test_bcrypt_version_is_compatible(self):
        """The pinned bcrypt version must be 4.0.1 (has the passlib workaround)."""
        text = REQUIREMENTS_PATH.read_text()
        match = re.search(r"bcrypt==(\S+)", text)
        assert match, "bcrypt version pin not found in requirements.txt"
        version = match.group(1)
        assert version == "4.0.1", (
            f"bcrypt must be pinned to 4.0.1 (got {version}). "
            "bcrypt==4.0.1 ships with a workaround that prevents passlib 1.7.4 "
            "from crashing during its backend detection at startup."
        )


class TestPasswordHashingWorks:
    """Verify that passlib CryptContext with bcrypt works without ValueError."""

    def test_hash_and_verify_password_no_error(self):
        """hash_password and verify_password must not raise any exception."""
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = ctx.hash("admin123")
        assert ctx.verify("admin123", hashed)

    def test_short_password_hashes_correctly(self):
        """Short passwords (well under 72 bytes) must hash and verify without error."""
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        for pwd in ("a", "abc", "user123", "admin123"):
            hashed = ctx.hash(pwd)
            assert ctx.verify(pwd, hashed), f"verify failed for {pwd!r}"

    def test_password_at_72_bytes_hashes_correctly(self):
        """Passwords of exactly 72 bytes must hash without error."""
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        pwd = "x" * 72
        hashed = ctx.hash(pwd)
        assert ctx.verify(pwd, hashed)


class TestErrorMessagesInRussian:
    """All HTTP error detail messages in main.py must be in Russian."""

    def _load_source(self) -> str:
        return MAIN_PATH.read_text(encoding="utf-8")

    def _extract_detail_strings(self, source: str) -> list[str]:
        return re.findall(r'detail="([^"]+)"', source)

    def test_no_english_detail_messages(self):
        """detail= strings in main.py must not contain English-only words."""
        source = self._load_source()
        details = self._extract_detail_strings(source)
        english_pattern = re.compile(r"^[A-Za-z]")
        english_details = [d for d in details if english_pattern.match(d)]
        assert not english_details, (
            "The following detail messages are still in English and should be "
            f"translated to Russian: {english_details}"
        )

    def test_login_error_is_russian(self):
        source = self._load_source()
        assert "Неверные учётные данные" in source, (
            "Login error detail must say 'Неверные учётные данные' in Russian"
        )

    def test_blocked_account_error_is_russian(self):
        source = self._load_source()
        assert "Аккаунт заблокирован" in source, (
            "Blocked account error must say 'Аккаунт заблокирован' in Russian"
        )

    def test_invalid_token_error_is_russian(self):
        source = self._load_source()
        assert "Недействительный токен" in source, (
            "Invalid token error must say 'Недействительный токен' in Russian"
        )

    def test_insufficient_permissions_error_is_russian(self):
        source = self._load_source()
        assert "Недостаточно прав" in source, (
            "Permissions error must say 'Недостаточно прав' in Russian"
        )

    def test_category_not_found_error_is_russian(self):
        source = self._load_source()
        assert "Категория не найдена" in source, (
            "Category not found error must say 'Категория не найдена' in Russian"
        )

    def test_product_not_found_error_is_russian(self):
        source = self._load_source()
        assert "Продукт не найден" in source, (
            "Product not found error must say 'Продукт не найден' in Russian"
        )

    def test_user_not_found_error_is_russian(self):
        source = self._load_source()
        assert "Пользователь не найден" in source, (
            "User not found error must say 'Пользователь не найден' in Russian"
        )
