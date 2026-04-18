from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/monolith_db"
    )
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 15
    jwt_refresh_expires_days: int = 7
    bcrypt_rounds: int = 10
    kafka_brokers: str = "kafka:9092"
    kafka_client_id: str = "backend-monolith"
    notification_service_url: str = "http://notification-service:4005"
    port: int = 4000


settings = Settings()
