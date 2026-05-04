"""
Утилиты для работы с JWT-токенами (из shared-lib).
Поддерживает access и refresh токены.
"""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    """Создаёт подписанный JWT access-токен."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        **(extra or {}),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Создаёт долгоживущий refresh-токен."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Декодирует и валидирует JWT. Бросает исключение при ошибке."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
