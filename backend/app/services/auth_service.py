"""
Бизнес-логика аутентификации: регистрация, вход, refresh, TOTP.
Также экспортирует current_user / admin_user для обратной совместимости
с app.api.* роутерами.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.models import UserModel
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token

# ─── Зависимости для старых роутеров (app.api.*) ──────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    """Возвращает текущего пользователя. Используется в legacy api-роутерах."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user_id: int = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def admin_user(user: UserModel = Depends(current_user)) -> UserModel:
    """Проверяет права администратора. Используется в legacy api-роутерах."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user

logger = logging.getLogger(__name__)


def register_user(db: Session, username: str, email: str, password: str, phone: str | None = None) -> UserModel:
    """Регистрирует нового пользователя. Бросает 409 если email/username заняты."""
    existing = db.query(UserModel).filter(
        (UserModel.username == username) | (UserModel.email == email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Имя пользователя или email уже заняты",
        )
    user = UserModel(
        username=username,
        email=email,
        phone=phone,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Зарегистрирован новый пользователь: %s", username)
    return user


def authenticate_user(
    db: Session,
    username: str,
    password: str,
    totp_code: str | None = None,
) -> tuple[str, str]:
    """
    Проверяет учётные данные и возвращает (access_token, refresh_token).
    Поддерживает опциональную TOTP 2FA.
    """
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")

    if user.totp_enabled:
        if not totp_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется TOTP-код")
        try:
            import pyotp
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный TOTP-код")
        except ImportError:
            logger.warning("pyotp не установлен, TOTP пропущен")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return access_token, refresh_token


def seed_admin(db: Session, username: str, email: str, password: str) -> None:
    """Создаёт администратора по умолчанию при первом запуске, если нет ни одного admin."""
    if not db.query(UserModel).filter(UserModel.is_admin == True).first():  # noqa: E712
        db.add(UserModel(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_admin=True,
            is_active=True,
            is_verified=True,
        ))
        db.commit()
        logger.info("Создан администратор по умолчанию: %s", username)
