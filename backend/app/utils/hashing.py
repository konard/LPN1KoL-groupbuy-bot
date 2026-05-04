"""
Утилиты для хеширования паролей (из shared-lib).
Использует hashlib.sha256 с солью.
"""
import hashlib
import secrets


def hash_password(password: str) -> str:
    """Хеширует пароль с случайной солью. Формат: <salt>$<hash>."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, hashed: str) -> bool:
    """Проверяет пароль против сохранённого хеша."""
    salt, stored_hash = hashed.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == stored_hash
