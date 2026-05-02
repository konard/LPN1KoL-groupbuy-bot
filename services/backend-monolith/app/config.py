from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/monolith_db"
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 15
    jwt_refresh_expires_days: int = 7
    bcrypt_rounds: int = 10
    kafka_brokers: str = "kafka:9092"
    kafka_client_id: str = "backend-monolith"
    port: int = 4000

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Centrifugo
    centrifugo_url: str = "http://centrifugo:8000"
    centrifugo_api_key: str = "centrifugo_api_key"

    # SMTP
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "Groupbuy <notifications@example.com>"

    # Telegram bot (for notifications)
    telegram_bot_token: str = ""

    # Elasticsearch (optional)
    elasticsearch_url: str = ""


settings = Settings()
