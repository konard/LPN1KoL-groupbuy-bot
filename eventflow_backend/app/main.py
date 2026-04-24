from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from celery import uuid as celery_uuid
from celery.result import AsyncResult
from fastapi import Depends, FastAPI, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import RedisEventCache
from .config import settings
from .database import get_session, init_db
from .models import Event, Ticket
from .schemas import EventCreate, EventRead, TicketPurchase, TicketRead, TicketStatus
from .stripe_mock import StripePaymentError, stripe_client
from .tasks import celery_app, generate_ticket


redis_client: Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global redis_client
    await init_db()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await redis_client.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


async def get_event_cache() -> RedisEventCache:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return RedisEventCache(redis_client, settings.event_cache_ttl)


@app.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> Event:
    event = Event(**payload.model_dump())
    session.add(event)
    await session.commit()
    await session.refresh(event)
    await cache.invalidate()
    return event


@app.get("/events", response_model=list[EventRead])
async def list_events(
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> list[dict[str, object]]:
    cached = await cache.get_events()
    if cached is not None:
        return cached

    result = await session.execute(select(Event).order_by(Event.starts_at))
    events = result.scalars().all()
    serialized = [
        EventRead.model_validate(event).model_dump(mode="json") for event in events
    ]
    await cache.set_events(serialized)
    return serialized


@app.post(
    "/tickets/purchase",
    response_model=TicketRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def purchase_ticket(
    payload: TicketPurchase,
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> Ticket:
    result = await session.execute(
        select(Event).where(Event.id == payload.event_id).with_for_update()
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.tickets_available <= 0:
        raise HTTPException(status_code=409, detail="Tickets are sold out")

    try:
        stripe_client.charge(payload.card_number, event.price_cents)
    except StripePaymentError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    task_id = celery_uuid()
    ticket = Ticket(
        event_id=event.id,
        buyer_email=payload.buyer_email,
        task_id=task_id,
        status="queued",
    )
    event.tickets_available -= 1
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    generate_ticket.apply_async(args=[ticket.id], task_id=task_id)
    await cache.invalidate()
    return ticket


@app.get("/tickets/{task_id}", response_model=TicketStatus)
async def get_ticket_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TicketStatus:
    result = await session.execute(select(Ticket).where(Ticket.task_id == task_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket task not found")

    celery_state = AsyncResult(task_id, app=celery_app).state
    return TicketStatus(
        task_id=task_id,
        celery_state=celery_state,
        ticket_status=ticket.status,
        file_path=ticket.file_path,
    )
