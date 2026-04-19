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

    # CORS
    cors_origins: str = "*"

    # Elasticsearch (Search module)
    elasticsearch_url: str = "http://elasticsearch:9200"
    elasticsearch_index: str = "purchases"

    # Redis (Socket.IO in production, optional)
    redis_url: str = ""

    # Notification channels (all optional)
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "Groupbuy <notifications@example.com>"

    sendgrid_api_key: str = ""
    firebase_server_key: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    telegram_bot_token: str = ""
    telegram_api_url: str = "https://api.telegram.org"

    # Analytics Kafka topic
    analytics_topic: str = "analytics-raw"


settings = Settings()
