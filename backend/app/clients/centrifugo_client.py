"""
Centrifugo HTTP API клиент для публикации сообщений в каналы (реалтайм чат).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import CENTRIFUGO_API_KEY, CENTRIFUGO_URL, SECRET_KEY

logger = logging.getLogger(__name__)


async def publish_to_channel(channel: str, data: Dict[str, Any]) -> bool:
    """
    Публикует данные в канал Centrifugo через HTTP API.
    Возвращает True при успехе.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{CENTRIFUGO_URL}/api/publish",
                json={"channel": channel, "data": data},
                headers={"X-API-Key": CENTRIFUGO_API_KEY},
            )
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("Centrifugo недоступен: %s", exc)
        return False


def generate_centrifugo_token(user_id: str, channel: Optional[str] = None) -> str:
    """
    Генерирует JWT-токен для подключения клиента к Centrifugo WebSocket.
    Использует тот же SECRET_KEY, что и основной JWT (упрощение для монолита).
    """
    import jwt
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    if channel:
        payload["channel"] = channel
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
