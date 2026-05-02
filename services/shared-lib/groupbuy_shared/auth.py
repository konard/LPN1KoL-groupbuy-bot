from datetime import datetime, timezone, timedelta
from typing import Any

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=True)


def create_access_token(
    subject: str,
    secret: str,
    algorithm: str = "HS256",
    expires_seconds: int = 900,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str = "HS256") -> dict[str, Any]:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def make_jwt_dependency(secret: str, algorithm: str = "HS256"):
    def _verify(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict[str, Any]:
        return decode_token(credentials.credentials, secret, algorithm)
    return _verify
