"""Application configuration loaded from environment variables.

Mirrors the docker-compose.yml contract for the `core` service:
    DATABASE_URL  PostgreSQL connection string
    REDIS_URL     Redis connection string
    PORT          uvicorn bind port (default 8000)
    LOG_LEVEL     Python logging level (default INFO)
"""

import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/groupbuy",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
