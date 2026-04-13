"""
Bot configuration
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Bot configuration settings"""

    # Telegram
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")

    # VK
    vk_token: str = os.getenv("VK_TOKEN", "")

    # Core API
    core_api_url: str = os.getenv("CORE_API_URL", "http://localhost:8000/api")
    core_api_timeout: int = 30

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")

    # YooKassa (legacy)
    yookassa_shop_id: str = os.getenv("YOOKASSA_SHOP_ID", "")
    yookassa_secret_key: str = os.getenv("YOOKASSA_SECRET_KEY", "")

    # JWT and WebSocket
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-jwt-secret")
    websocket_url: str = os.getenv("WEBSOCKET_URL", "ws://localhost:8765")
    web_app_url: str = os.getenv("WEB_APP_URL", "http://localhost:3000")

    # Bot mode
    bot_mode: str = os.getenv("BOT_MODE", "polling")  # polling or webhook
    webhook_host: str = os.getenv("WEBHOOK_HOST", "")
    webhook_path: str = os.getenv("WEBHOOK_PATH", "/bot/webhook")

    # Bot settings
    polling_interval: float = 0.5
    max_workers: int = 10

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: Optional[str] = os.getenv("LOG_FILE")


config = BotConfig()
