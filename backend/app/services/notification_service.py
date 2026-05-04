"""
Бизнес-логика уведомлений: отправка email, Telegram, Centrifugo in-app.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> bool:
    """
    Отправляет email через SMTP.
    Возвращает True при успехе, False при ошибке.
    """
    from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER
    if not SMTP_HOST or not SMTP_USER:
        logger.debug("SMTP не настроен, письмо не отправлено")
        return False
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to], msg.as_string())
        return True
    except Exception as exc:
        logger.error("Ошибка отправки email на %s: %s", to, exc)
        return False


async def send_telegram(chat_id: str, text: str) -> bool:
    """
    Отправляет сообщение через Telegram Bot API.
    Возвращает True при успехе.
    """
    from app.config import TELEGRAM_BOT_TOKEN
    if not TELEGRAM_BOT_TOKEN:
        logger.debug("TELEGRAM_BOT_TOKEN не задан, уведомление пропущено")
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Ошибка Telegram-уведомления для %s: %s", chat_id, exc)
        return False


async def send_in_app(user_id: int, message: str) -> bool:
    """
    Отправляет in-app уведомление через Centrifugo.
    Канал: notifications:{user_id}
    """
    from app.clients.centrifugo_client import publish_to_channel
    return await publish_to_channel(
        f"notifications:{user_id}",
        {"message": message},
    )


async def notify(user_id: int, notify_type: str, subject: Optional[str],
                 message: str, extra: Optional[dict] = None) -> None:
    """
    Универсальный диспетчер уведомлений.
    Типы: email | telegram | push | in_app
    """
    extra = extra or {}
    if notify_type == "email":
        email = extra.get("email", "")
        if email:
            await send_email(email, subject or "Уведомление", message)
    elif notify_type == "telegram":
        chat_id = extra.get("telegram_id", "")
        if chat_id:
            await send_telegram(chat_id, message)
    elif notify_type in ("push", "in_app"):
        await send_in_app(user_id, message)
    else:
        logger.warning("Неизвестный тип уведомления: %s", notify_type)
