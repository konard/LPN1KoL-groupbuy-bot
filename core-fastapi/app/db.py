"""Database (PostgreSQL via asyncpg) and Redis connection helpers."""

import logging

import asyncpg
import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger("core.db")

_pg_pool: asyncpg.Pool | None = None
_redis: aioredis.Redis | None = None


def _normalize_pg_dsn(url: str) -> str:
    # asyncpg uses postgresql:// (it does not accept the postgresql+asyncpg:// SQLAlchemy form)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def connect() -> None:
    """Open the asyncpg pool and Redis client. Verify both at startup."""
    global _pg_pool, _redis

    dsn = _normalize_pg_dsn(settings.database_url)
    _pg_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)
    async with _pg_pool.acquire() as conn:
        await conn.execute("SELECT 1")
    logger.info("PostgreSQL connection established")

    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()
    logger.info("Redis connection established")


async def disconnect() -> None:
    global _pg_pool, _redis
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_pool() -> asyncpg.Pool:
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL pool is not initialised")
    return _pg_pool


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis client is not initialised")
    return _redis


async def init_schema() -> None:
    """Create the demo `products` table if it does not exist yet."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id          BIGSERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price_cents BIGINT NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
