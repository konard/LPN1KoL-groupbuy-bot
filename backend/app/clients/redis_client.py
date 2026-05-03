"""
Redis клиент (из shared-lib).
Используется для кэширования, поиска, истории и ограничения запросов.
"""
import logging
from typing import Optional

from app.config import REDIS_URL

logger = logging.getLogger(__name__)

# Глобальный Redis клиент
_redis = None


def get_redis():
    """Возвращает глобальный экземпляр Redis клиента."""
    return _redis


async def init_redis() -> None:
    """Инициализирует Redis клиент при старте приложения."""
    global _redis
    try:
        import redis.asyncio as aioredis
        _redis = await aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        await _redis.ping()
        logger.info("Redis подключён: %s", REDIS_URL)
    except Exception as exc:
        logger.warning("Redis недоступен при старте: %s", exc)
        _redis = None


async def close_redis() -> None:
    """Закрывает соединение с Redis."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis отключён")
