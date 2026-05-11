from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = Field(default=8000, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379", alias="REDIS_URL")

    kafka_brokers: str = Field(default="kafka:9092", alias="KAFKA_BROKERS")
    kafka_client_id: str = Field(default="groupbuy-service", alias="KAFKA_CLIENT_ID")
    kafka_group_id: str = Field(default="groupbuy-group", alias="KAFKA_GROUP_ID")

    jwt_secret: str = Field(default="change_me_in_production", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expires_in: int = 900  # 15 minutes in seconds

    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
