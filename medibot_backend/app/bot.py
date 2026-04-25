from datetime import datetime, timedelta, timezone

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from .calendar_client import GoogleCalendarClient, GoogleCalendarMock
from .config import Settings
from .database import AsyncSessionLocal, init_db
from .models import Appointment, Clinic
from .observability import configure_logging
from .tasks import send_appointment_reminder


SELECT_CLINIC, SELECT_TIME = range(2)
TIME_OPTIONS = (
    "2026-05-01T09:00:00+00:00",
    "2026-05-01T13:00:00+00:00",
    "2026-05-02T10:30:00+00:00",
)
logger = structlog.get_logger(__name__)


class RedisStateStore:
    """Redis storage for conversation state and rate limits."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    async def set_clinic_choice(self, user_id: int, clinic_id: int) -> None:
        """Persist the selected clinic for a Telegram user."""

        await self.redis.set(f"medibot:user:{user_id}:clinic", clinic_id, ex=900)

    async def get_clinic_choice(self, user_id: int) -> int | None:
        """Return the selected clinic id for a Telegram user."""

        value = await self.redis.get(f"medibot:user:{user_id}:clinic")
        return int(value) if value is not None else None

    async def check_rate_limit(self, user_id: int, action: str) -> bool:
        """Return whether a user can perform an action in the current window."""

        key = f"medibot:rate:{action}:{user_id}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, self.settings.rate_limit_window_seconds)
        return current <= self.settings.rate_limit_max_requests


class MediBot:
    """Telegram bot for booking doctor appointments."""

    def __init__(
        self,
        settings: Settings,
        calendar: GoogleCalendarClient | None = None,
    ) -> None:
        configure_logging()
        self.settings = settings
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.state_store = RedisStateStore(self.redis, settings)
        self.calendar = calendar or GoogleCalendarMock()
        self.application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .post_init(self.on_startup)
            .post_shutdown(self.on_shutdown)
            .build()
        )
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("clinics", self.clinics))
        self.application.add_handler(CommandHandler("appointments", self.list_appointments))
        self.application.add_handler(self._build_appointment_conversation())

    async def on_startup(self, application: Application) -> None:
        """Initialize database resources when polling starts."""

        await init_db()

    async def on_shutdown(self, application: Application) -> None:
        """Close Redis resources when polling stops."""

        await self.redis.aclose()

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /start."""

        if update.message is not None:
            await update.message.reply_text(
                "MediBot: use /clinics, /appointment, or /appointments."
            )

    async def clinics(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /clinics with inline clinic selection buttons."""

        clinics = await self._load_clinics()
        text = "\n".join(
            f"{clinic.id}. {clinic.name} - {clinic.address}" for clinic in clinics
        )
        markup = self._clinic_markup(clinics)
        if update.message is not None:
            await update.message.reply_text(
                text or "No clinics available.",
                reply_markup=markup,
            )

    async def start_appointment(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Start the /appointment conversation."""

        if update.effective_user is None or update.message is None:
            return ConversationHandler.END
        allowed = await self.state_store.check_rate_limit(
            update.effective_user.id,
            "appointment",
        )
        if not allowed:
            await update.message.reply_text("Too many appointment attempts.")
            return ConversationHandler.END

        if context.args:
            return await self._start_appointment_from_args(update, context.args)

        clinics = await self._load_clinics()
        await update.message.reply_text(
            "Choose a clinic for your appointment.",
            reply_markup=self._clinic_markup(clinics),
        )
        return SELECT_CLINIC

    async def select_clinic(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Store selected clinic and ask the user to choose a time."""

        query = update.callback_query
        if query is None or update.effective_user is None or query.data is None:
            return ConversationHandler.END
        await query.answer()
        clinic_id = int(query.data.split(":", maxsplit=1)[1])
        await self.state_store.set_clinic_choice(update.effective_user.id, clinic_id)
        await query.edit_message_text(
            "Choose an appointment time.",
            reply_markup=self._time_markup(),
        )
        return SELECT_TIME

    async def select_time(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Create an appointment for the selected clinic and time."""

        query = update.callback_query
        if query is None or update.effective_user is None or query.data is None:
            return ConversationHandler.END
        await query.answer()
        appointment_at = parse_datetime(query.data.split(":", maxsplit=1)[1])
        clinic_id = await self.state_store.get_clinic_choice(update.effective_user.id)
        if clinic_id is None:
            await query.edit_message_text("Clinic selection expired. Use /appointment.")
            return ConversationHandler.END

        appointment = await self._create_appointment(
            telegram_user_id=update.effective_user.id,
            clinic_id=clinic_id,
            appointment_at=appointment_at,
        )
        self._schedule_reminder(appointment)
        await query.edit_message_text(
            f"Appointment scheduled for {appointment_at.isoformat()}."
        )
        logger.info(
            "appointment_scheduled",
            appointment_id=appointment.id,
            telegram_user_id=update.effective_user.id,
        )
        return ConversationHandler.END

    async def list_appointments(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /appointments."""

        if update.effective_user is None or update.message is None:
            return
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Appointment, Clinic)
                .join(Clinic)
                .where(
                    Appointment.telegram_user_id == update.effective_user.id,
                    Appointment.appointment_at >= datetime.now(timezone.utc),
                )
                .order_by(Appointment.appointment_at)
            )
            rows = result.all()

        if not rows:
            await update.message.reply_text("No upcoming appointments.")
            return
        lines = [
            f"{appointment.appointment_at.isoformat()} - {clinic.name}"
            for appointment, clinic in rows
        ]
        await update.message.reply_text("\n".join(lines))

    async def cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Cancel the active conversation."""

        if update.message is not None:
            await update.message.reply_text("Appointment flow cancelled.")
        return ConversationHandler.END

    def _build_appointment_conversation(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler("appointment", self.start_appointment)],
            states={
                SELECT_CLINIC: [
                    CallbackQueryHandler(self.select_clinic, pattern=r"^clinic:\d+$")
                ],
                SELECT_TIME: [
                    CallbackQueryHandler(self.select_time, pattern=r"^time:.+")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

    async def _start_appointment_from_args(
        self,
        update: Update,
        args: list[str],
    ) -> int:
        if update.effective_user is None or update.message is None:
            return ConversationHandler.END
        try:
            clinic_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Usage: /appointment <clinic_id>")
            return ConversationHandler.END

        clinic = await self._get_clinic(clinic_id)
        if clinic is None:
            await update.message.reply_text("Clinic not found.")
            return ConversationHandler.END

        await self.state_store.set_clinic_choice(update.effective_user.id, clinic_id)
        if len(args) > 1:
            try:
                appointment_at = parse_datetime(args[1])
            except ValueError:
                await update.message.reply_text(
                    "Usage: /appointment <clinic_id> <datetime>"
                )
                return ConversationHandler.END
            appointment = await self._create_appointment(
                telegram_user_id=update.effective_user.id,
                clinic_id=clinic_id,
                appointment_at=appointment_at,
            )
            self._schedule_reminder(appointment)
            await update.message.reply_text(
                f"Appointment scheduled for {appointment_at.isoformat()}."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            f"Choose a time for {clinic.name}.",
            reply_markup=self._time_markup(),
        )
        return SELECT_TIME

    async def _load_clinics(self) -> list[Clinic]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Clinic).order_by(Clinic.id))
            return list(result.scalars().all())

    async def _get_clinic(self, clinic_id: int) -> Clinic | None:
        async with AsyncSessionLocal() as session:
            return await session.get(Clinic, clinic_id)

    def _clinic_markup(self, clinics: list[Clinic]) -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(clinic.name, callback_data=f"clinic:{clinic.id}")]
            for clinic in clinics
        ]
        return InlineKeyboardMarkup(buttons)

    def _time_markup(self) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton(
                    parse_datetime(value).strftime("%Y-%m-%d %H:%M UTC"),
                    callback_data=f"time:{value}",
                )
            ]
            for value in TIME_OPTIONS
        ]
        return InlineKeyboardMarkup(buttons)

    async def _create_appointment(
        self,
        telegram_user_id: int,
        clinic_id: int,
        appointment_at: datetime,
    ) -> Appointment:
        async with AsyncSessionLocal() as session:
            clinic = await session.get(Clinic, clinic_id)
            if clinic is None:
                raise ValueError("Clinic not found")
            event = await self.calendar.create_event(
                summary=f"Appointment at {clinic.name}",
                start_at=appointment_at,
                end_at=appointment_at + timedelta(minutes=30),
                attendees=[],
            )
            appointment = Appointment(
                clinic_id=clinic.id,
                telegram_user_id=telegram_user_id,
                appointment_at=appointment_at,
                calendar_event_id=event["id"],
                status="scheduled",
            )
            session.add(appointment)
            await session.commit()
            await session.refresh(appointment)
            return appointment

    def _schedule_reminder(self, appointment: Appointment) -> None:
        reminder_at = max(
            appointment.appointment_at - timedelta(hours=1),
            datetime.now(timezone.utc),
        )
        send_appointment_reminder.apply_async(args=[appointment.id], eta=reminder_at)


def parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime string into UTC."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_application(settings: Settings) -> Application:
    """Build the python-telegram-bot application."""

    return MediBot(settings).application
