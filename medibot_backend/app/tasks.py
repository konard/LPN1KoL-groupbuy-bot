import asyncio

from celery import Celery
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .models import Appointment, Clinic


celery_app = Celery(
    "medibot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="medibot.send_appointment_reminder")
def send_appointment_reminder(appointment_id: int) -> dict[str, int | str]:
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
            return {"appointment_id": appointment_id, "status": "missing"}

        appointment, clinic = row
        message = (
            f"Reminder for user {appointment.telegram_user_id}: "
            f"{clinic.name} at {appointment.appointment_at.isoformat()}"
        )
        print(message, flush=True)
        return {"appointment_id": appointment.id, "status": "sent"}
