import asyncio

import structlog
from celery import Celery
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .models import Appointment, Clinic
from .observability import configure_logging


configure_logging()
logger = structlog.get_logger(__name__)

celery_app = Celery(
    "medibot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="medibot.send_appointment_reminder")
def send_appointment_reminder(appointment_id: int) -> dict[str, int | str]:
    """Send a scheduled appointment reminder."""

    return asyncio.run(_send_appointment_reminder(appointment_id))


async def _send_appointment_reminder(
    appointment_id: int,
) -> dict[str, int | str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment, Clinic)
            .join(Clinic)
            .where(Appointment.id == appointment_id)
        )
        row = result.first()
        if row is None:
            logger.error("appointment_missing", appointment_id=appointment_id)
            return {"appointment_id": appointment_id, "status": "missing"}

        appointment, clinic = row
        logger.info(
            "appointment_reminder_sent",
            appointment_id=appointment.id,
            telegram_user_id=appointment.telegram_user_id,
            clinic=clinic.name,
            appointment_at=appointment.appointment_at.isoformat(),
        )
        return {"appointment_id": appointment.id, "status": "sent"}
