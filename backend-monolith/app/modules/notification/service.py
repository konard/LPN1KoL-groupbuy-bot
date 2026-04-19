"""
Notification service: replaces the Node.js notification-service.
Uses httpx for async external API calls (SendGrid / Firebase).
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.sendgrid_api_key:
        logger.warning("SendGrid API key not configured, skipping email to %s", to)
        return

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to}]}],
                    "from": {"email": settings.smtp_from},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info("Email sent to %s via SendGrid", to)
        except Exception:
            logger.exception("Failed to send email to %s", to)


async def send_push(token: str, title: str, body: str, data: dict | None = None) -> None:
    if not settings.firebase_server_key:
        logger.warning("Firebase server key not configured, skipping push")
        return

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={settings.firebase_server_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": token,
                    "notification": {"title": title, "body": body},
                    "data": data or {},
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info("Push notification sent to token %s", token[:20])
        except Exception:
            logger.exception("Failed to send push notification")


async def dispatch(user_id: str, notification_type: str, payload: dict) -> None:
    subject = payload.get("subject", "Notification")
    message = payload.get("message", "")
    email = payload.get("email")
    device_token = payload.get("device_token")

    if notification_type == "email" and email:
        await send_email(email, subject, message)
    elif notification_type == "push" and device_token:
        await send_push(device_token, subject, message, payload.get("data"))
    else:
        logger.info(
            "Notification type '%s' for user %s — no handler or missing target",
            notification_type,
            user_id,
        )
