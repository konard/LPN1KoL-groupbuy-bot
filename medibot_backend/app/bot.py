from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .calendar_client import GoogleCalendarMock
from .config import Settings
from .database import AsyncSessionLocal, init_db
from .models import Appointment, Clinic
from .tasks import send_appointment_reminder


class RedisStateStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def set_clinic_choice(self, user_id: int, clinic_id: int) -> None:
        await self.redis.set(f"medibot:user:{user_id}:clinic", clinic_id, ex=900)

    async def get_clinic_choice(self, user_id: int) -> int | None:
        value = await self.redis.get(f"medibot:user:{user_id}:clinic")
        return int(value) if value is not None else None


class MediBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.state_store = RedisStateStore(self.redis)
        self.calendar = GoogleCalendarMock()
        self.application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .post_init(self.on_startup)
            .post_shutdown(self.on_shutdown)
            .build()
        )
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("clinics", self.clinics))
        self.application.add_handler(CommandHandler("appointment", self.appointment))

    async def on_startup(self, application: Application) -> None:
        await init_db()

    async def on_shutdown(self, application: Application) -> None:
        await self.redis.aclose()

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.message is not None:
            await update.message.reply_text("MediBot: use /clinics to choose a clinic.")

    async def clinics(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Clinic).order_by(Clinic.id))
            clinics = result.scalars().all()

        text = "\n".join(
            f"{clinic.id}. {clinic.name} - {clinic.address}" for clinic in clinics
        )
        if update.message is not None:
            await update.message.reply_text(text or "No clinics available.")

    async def appointment(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.effective_user is None or update.message is None:
            return
        if len(context.args) != 2:
            await update.message.reply_text(
                "Usage: /appointment <clinic_id> <datetime>"
            )
            return

        try:
            clinic_id = int(context.args[0])
            appointment_at = parse_datetime(context.args[1])
        except ValueError:
            await update.message.reply_text(
                "Usage: /appointment <clinic_id> <datetime>"
            )
            return

        async with AsyncSessionLocal() as session:
            clinic = await session.get(Clinic, clinic_id)
            if clinic is None:
                await update.message.reply_text("Clinic not found.")
                return

            event = await self.calendar.create_event(
                summary=f"Appointment at {clinic.name}",
                start_at=appointment_at,
                end_at=appointment_at + timedelta(minutes=30),
                attendees=[],
            )
            appointment = Appointment(
                clinic_id=clinic.id,
                telegram_user_id=update.effective_user.id,
                appointment_at=appointment_at,
                calendar_event_id=event["id"],
                status="scheduled",
            )
            session.add(appointment)
            await session.commit()
            await session.refresh(appointment)

        await self.state_store.set_clinic_choice(update.effective_user.id, clinic_id)
        reminder_at = appointment_at - timedelta(hours=1)
        if reminder_at < datetime.now(timezone.utc):
            reminder_at = datetime.now(timezone.utc)
        send_appointment_reminder.apply_async(args=[appointment.id], eta=reminder_at)
        await update.message.reply_text(
            f"Appointment scheduled for {appointment_at.isoformat()}."
        )


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_application(settings: Settings) -> Application:
    return MediBot(settings).application
