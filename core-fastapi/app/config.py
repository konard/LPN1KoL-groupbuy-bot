"""Application configuration loaded from environment variables."""

import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/groupbuy",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    jwt_secret: str = os.getenv("JWT_SECRET", "your-secret-key")
    cors_origins: list = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()
