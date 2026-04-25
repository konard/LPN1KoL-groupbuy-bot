import asyncio
from pathlib import Path

import structlog
from celery import Celery
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .models import Event, Ticket, utc_now
from .observability import configure_logging


configure_logging()
logger = structlog.get_logger(__name__)

celery_app = Celery(
    "eventflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task(name="eventflow.generate_ticket")
def generate_ticket(ticket_id: int) -> dict[str, int | str]:
    """Generate a ticket file for a purchased ticket."""

    return asyncio.run(_generate_ticket(ticket_id))


@celery_app.task(name="eventflow.return_ticket")
def return_ticket_task(ticket_id: int, reason: str) -> dict[str, int | str]:
    """Process a ticket return event in the worker."""

    return asyncio.run(_return_ticket(ticket_id, reason))


async def _generate_ticket(ticket_id: int) -> dict[str, int | str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket, Event).join(Event).where(Ticket.id == ticket_id)
        )
        row = result.first()
        if row is None:
            logger.error("ticket_missing", ticket_id=ticket_id)
            return {"ticket_id": ticket_id, "status": "missing"}

        ticket, event = row
        if ticket.status.startswith("return"):
            return {"ticket_id": ticket.id, "status": ticket.status}

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
        logger.info("ticket_generated", ticket_id=ticket.id)
        return {"ticket_id": ticket.id, "status": ticket.status}


async def _return_ticket(ticket_id: int, reason: str) -> dict[str, int | str]:
    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            logger.error("ticket_return_missing", ticket_id=ticket_id)
            return {"ticket_id": ticket_id, "status": "missing"}

        ticket.status = "returned"
        ticket.returned_at = utc_now()
        await session.commit()
        logger.info("ticket_returned", ticket_id=ticket.id, reason=reason)
        return {"ticket_id": ticket.id, "status": ticket.status}
