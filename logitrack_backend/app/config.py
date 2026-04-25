from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "LogiTrack"
    database_url: str = (
        "postgresql+asyncpg://logitrack:logitrack@localhost:5432/logitrack"
    )
    redis_url: str = "redis://localhost:6379/0"
    api_token: str = "change-me"
    rate_limit_max_requests: int = 30
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


settings = get_settings()
