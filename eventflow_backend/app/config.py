from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EventFlow"
    database_url: str = (
        "postgresql+asyncpg://eventflow:eventflow@localhost:5432/eventflow"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"
    event_cache_ttl: int = 60
    ticket_output_dir: str = "tickets"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
