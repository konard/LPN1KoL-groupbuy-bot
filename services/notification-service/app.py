import asyncio
import json
import logging
import os
import smtplib
import ssl
from contextlib import asynccontextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("notification-service")

PORT = int(os.getenv("PORT", "4005"))
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "notification-group")
CENTRIFUGO_URL = os.getenv("CENTRIFUGO_URL", "http://centrifugo:8000")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "centrifugo_api_key")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Groupbuy <notifications@example.com>")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL", "https://api.telegram.org")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

TOPICS = [
    "purchase.created", "purchase.voting.started", "purchase.voting.closed",
    "purchase.voting.tie", "purchase.vote.cast", "purchase.cancelled",
    "payment.topup.completed", "payment.hold.created", "payment.committed", "payment.released",
    "commission.held", "commission.committed", "commission.released",
    "escrow.created", "escrow.deposited", "escrow.confirmed", "escrow.released", "escrow.disputed",
    "review.created", "complaint.filed", "complaint.resolved", "user.auto_blocked",
    "search.query", "auth.registered", "auth.password_reset",
]

_consumer_task: asyncio.Task | None = None


# ─── Notification channels ────────────────────────────────────────────────────

async def _centrifugo_publish(channel: str, data: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{CENTRIFUGO_URL}/api/publish",
                headers={"X-API-Key": CENTRIFUGO_API_KEY},
                json={"channel": channel, "data": data},
            )
    except Exception as exc:
        logger.warning("Centrifugo publish failed: %s", exc)


async def _send_email(to: str, subject: str, body_html: str, body_text: str = "") -> None:
    if not SMTP_USER:
        logger.debug("SMTP not configured, skipping email to %s", to)
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        def _smtp_send():
            if SMTP_PORT == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_FROM, to, msg.as_string())
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_FROM, to, msg.as_string())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send)
        logger.info("Email sent to %s: %s", to, subject)
    except Exception as exc:
        logger.error("Email failed to %s: %s", to, exc)


async def _send_telegram(chat_id: str, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)


async def _send_whatsapp(phone: str, text: str) -> None:
    if not WHATSAPP_API_URL or not WHATSAPP_ACCESS_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
                json={"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}},
            )
    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)


# ─── Event handler ────────────────────────────────────────────────────────────

async def _handle_event(topic: str, payload: dict) -> None:
    logger.info("Event: %s %s", topic, payload.get("purchaseId", payload.get("userId", "")))

    user_id = payload.get("userId") or payload.get("organizerId") or payload.get("targetId")
    channel = f"user:{user_id}" if user_id else "broadcast"

    if topic == "purchase.created":
        await _centrifugo_publish(channel, {"type": "purchase_created", "data": payload})

    elif topic == "purchase.voting.started":
        await _centrifugo_publish(f"purchase:{payload.get('purchaseId')}", {"type": "voting_started", "data": payload})

    elif topic == "purchase.voting.closed":
        await _centrifugo_publish(f"purchase:{payload.get('purchaseId')}", {"type": "voting_closed", "data": payload})

    elif topic == "purchase.voting.tie":
        await _centrifugo_publish(f"purchase:{payload.get('purchaseId')}", {"type": "voting_tie", "data": payload})

    elif topic == "purchase.cancelled":
        await _centrifugo_publish(f"purchase:{payload.get('purchaseId')}", {"type": "purchase_cancelled", "data": payload})

    elif topic == "payment.topup.completed":
        await _centrifugo_publish(channel, {"type": "topup_completed", "data": payload})

    elif topic == "payment.committed":
        await _centrifugo_publish(channel, {"type": "payment_committed", "data": payload})

    elif topic == "escrow.disputed":
        await _centrifugo_publish(f"purchase:{payload.get('purchaseId')}", {"type": "escrow_disputed", "data": payload})

    elif topic == "user.auto_blocked":
        await _centrifugo_publish(channel, {"type": "account_blocked", "data": payload})

    elif topic == "auth.registered":
        email = payload.get("email")
        if email:
            await _send_email(
                email,
                "Welcome to GroupBuy!",
                f"<h1>Welcome!</h1><p>Your account has been created. User ID: {payload.get('userId')}</p>",
                "Welcome! Your account has been created.",
            )

    elif topic == "auth.password_reset":
        email = payload.get("email")
        token = payload.get("token", "")
        if email:
            await _send_email(
                email,
                "Password Reset Request",
                f"<p>Use this token to reset your password: <strong>{token}</strong></p>",
                f"Password reset token: {token}",
            )


async def _consumer_loop() -> None:
    retry_delay = 5
    while True:
        consumer = AIOKafkaConsumer(
            *TOPICS,
            bootstrap_servers=KAFKA_BROKERS,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        try:
            await consumer.start()
            logger.info("Notification consumer started")
            async for msg in consumer:
                try:
                    await _handle_event(msg.topic, msg.value)
                except Exception as exc:
                    logger.error("Handler error on %s: %s", msg.topic, exc)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Consumer error: %s — retrying in %ds", exc, retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass


# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_task
    _consumer_task = asyncio.create_task(_consumer_loop())
    logger.info("Notification service started on :%d", PORT)
    yield
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("Notification service stopped")


app = FastAPI(title="Notification Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification-service"}


class NotifyRequest(BaseModel):
    userId: str | None = None
    email: str | None = None
    phone: str | None = None
    telegramChatId: str | None = None
    type: str
    subject: str | None = None
    body: str | None = None
    data: dict | None = None


@app.post("/internal/notify")
async def internal_notify(body: NotifyRequest):
    """Direct notification endpoint for other services (not via Kafka)."""
    tasks = []
    if body.email and body.body:
        tasks.append(_send_email(body.email, body.subject or "Notification", body.body))
    if body.telegramChatId and body.body:
        tasks.append(_send_telegram(body.telegramChatId, body.body))
    if body.userId:
        tasks.append(_centrifugo_publish(f"user:{body.userId}", {"type": body.type, "data": body.data or {}}))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    return {"success": True}


class SendOtpRequest(BaseModel):
    email: str
    otp: str
    subject: str | None = None
    context: str = "login"


@app.post("/internal/send-otp")
async def internal_send_otp(body: SendOtpRequest):
    """Send OTP verification code by email. Called by auth-service."""
    is_registration = body.context == "registration"
    subject = body.subject or (
        "Groupbuy — код подтверждения регистрации" if is_registration else "Groupbuy — код для входа"
    )
    action_label = "регистрации" if is_registration else "входа"
    body_html = (
        f"<div style='font-family:sans-serif;max-width:480px;margin:0 auto'>"
        f"<h2>Ваш код подтверждения</h2>"
        f"<p>Введите этот код для завершения {action_label}:</p>"
        f"<div style='font-size:32px;font-weight:bold;letter-spacing:8px;padding:16px;background:#f5f5f5;"
        f"border-radius:8px;text-align:center'>{body.otp}</div>"
        f"<p style='color:#888;font-size:13px'>Код действителен 10 минут. Не передавайте его никому.</p>"
        f"</div>"
    )
    body_text = f"Ваш код для {action_label}: {body.otp}\nКод действителен 10 минут."
    await _send_email(body.email, subject, body_html, body_text)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
