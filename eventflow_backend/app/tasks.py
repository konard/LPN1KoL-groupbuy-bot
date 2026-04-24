import asyncio
from pathlib import Path

from celery import Celery
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .models import Event, Ticket


celery_app = Celery(
    "eventflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="eventflow.generate_ticket")
def generate_ticket(ticket_id: int) -> dict[str, int | str]:
    return asyncio.run(_generate_ticket(ticket_id))


async def _generate_ticket(ticket_id: int) -> dict[str, int | str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket, Event).join(Event).where(Ticket.id == ticket_id)
        )
        row = result.first()
        if row is None:
            return {"ticket_id": ticket_id, "status": "missing"}

        ticket, event = row
        ticket.status = "generating"
        await session.commit()

        output_dir = Path(settings.ticket_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"ticket_{ticket.id}.txt"
        file_path.write_text(
            "\n".join(
                [
                    f"Ticket #{ticket.id}",
                    f"Event: {event.title}",
                    f"Venue: {event.venue}",
                    f"Starts at: {event.starts_at.isoformat()}",
                    f"Buyer: {ticket.buyer_email}",
                ]
            ),
            encoding="utf-8",
        )

        ticket.status = "generated"
        ticket.file_path = str(file_path)
        await session.commit()
        return {"ticket_id": ticket.id, "status": ticket.status}
