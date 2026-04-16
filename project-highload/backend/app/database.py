import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://groupbuy:groupbuy@pgbouncer:6432/groupbuy",
)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class Base(DeclarativeBase):
    pass


connect_args = {}
if DATABASE_URL.startswith("postgresql+asyncpg"):
    # Required for PgBouncer transaction pooling because prepared statements
    # are bound to a server connection, while transactions may hop servers.
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    DATABASE_URL,
    pool_size=_int_env("DATABASE_POOL_SIZE", 20),
    max_overflow=_int_env("DATABASE_MAX_OVERFLOW", 40),
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ping_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    await engine.dispose()
