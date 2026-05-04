"""
Конфигурация приложения через pydantic-settings.
Все переменные окружения читаются из .env или среды Docker.
"""
import os
from typing import List


# ─── База данных ──────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./dev.db",
)

# ─── Redis ────────────────────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─── JWT / безопасность ───────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS: List[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:80",
).split(",")

# ─── Порт и логирование ───────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ─── Kafka ────────────────────────────────────────────────────────────────────
KAFKA_BROKERS: str = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_CLIENT_ID: str = os.getenv("KAFKA_CLIENT_ID", "groupbuy-core")

# ─── Centrifugo (вебсокеты для чата) ─────────────────────────────────────────
CENTRIFUGO_URL: str = os.getenv("CENTRIFUGO_URL", "http://centrifugo:8000")
CENTRIFUGO_API_KEY: str = os.getenv("CENTRIFUGO_API_KEY", "centrifugo_api_key")

# ─── Elasticsearch (поиск) ────────────────────────────────────────────────────
ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "")

# ─── S3 / MinIO (аналитика, отчёты) ──────────────────────────────────────────
S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET: str = os.getenv("S3_BUCKET", "groupbuy-reports")

# ─── SMTP (email-уведомления) ─────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "Groupbuy <notifications@example.com>")

# ─── Telegram Bot (уведомления) ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ─── Администратор по умолчанию ───────────────────────────────────────────────
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@localhost")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")
