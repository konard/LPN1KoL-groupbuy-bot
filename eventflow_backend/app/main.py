import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
import structlog
from celery import uuid as celery_uuid
from celery.result import AsyncResult
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from .cache import RedisEventCache
from .config import settings
from .database import get_session, init_db
from .errors import (
    EventFlowError,
    EventNotFoundError,
    ForbiddenTicketError,
    PaymentRejectedError,
    RateLimitExceededError,
    SoldOutError,
    TicketNotFoundError,
)
from .models import Event, Ticket, utc_now
from .observability import configure_logging
from .schemas import (
    Actor,
    EventCreate,
    EventRead,
    HealthRead,
    TicketPurchase,
    TicketRead,
    TicketReturnRequest,
    TicketStatus,
    TokenRequest,
    TokenResponse,
)
from .stripe_mock import StripePaymentError, stripe_client
from .tasks import celery_app, generate_ticket, return_ticket_task


configure_logging()
logger = structlog.get_logger(__name__)
redis_client: Redis | None = None
bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize database and Redis resources for the API process."""

    global redis_client
    await init_db()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("eventflow_started")
    yield
    if redis_client is not None:
        await redis_client.aclose()
    logger.info("eventflow_stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(EventFlowError)
async def eventflow_exception_handler(
    request: Request,
    exc: EventFlowError,
) -> JSONResponse:
    """Map domain errors to consistent JSON HTTP responses."""

    logger.error(
        "eventflow_error",
        path=request.url.path,
        code=exc.code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "detail": exc.detail},
    )


async def get_redis() -> Redis:
    """Return the initialized Redis client."""

    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_client


async def get_event_cache(redis: Redis = Depends(get_redis)) -> RedisEventCache:
    """Return the event listing cache dependency."""

    return RedisEventCache(redis, settings.event_cache_ttl)


async def get_current_actor(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> Actor:
    """Decode the bearer JWT into an authenticated actor."""

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from exc

    role = payload.get("role")
    subject = payload.get("sub")
    if role not in {"organizer", "user"} or not isinstance(subject, str):
        raise HTTPException(status_code=401, detail="Invalid token claims")
    return Actor(subject=subject, role=role)


def require_role(*roles: str) -> Callable[[Actor], Awaitable[Actor]]:
    """Create a dependency that allows only selected actor roles."""

    async def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if actor.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return actor

    return dependency


def rate_limit(scope: str) -> Callable[[Request, Redis], Awaitable[None]]:
    """Create a Redis-backed rate limit dependency."""

    async def dependency(
        request: Request,
        redis: Redis = Depends(get_redis),
    ) -> None:
        client_host = request.client.host if request.client is not None else "unknown"
        token = request.headers.get("authorization", client_host)
        key = f"eventflow:rate:{scope}:{token}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, settings.rate_limit_window_seconds)
        if current > settings.rate_limit_max_requests:
            raise RateLimitExceededError("Too many requests")

    return dependency


@app.post("/auth/token", response_model=TokenResponse)
async def create_token(payload: TokenRequest) -> TokenResponse:
    """Issue a signed demo JWT for organizer or user workflows."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    token = jwt.encode(
        {"sub": payload.subject, "role": payload.role, "exp": expires_at},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(access_token=token, expires_at=expires_at)


@app.get("/health", response_model=HealthRead)
async def health(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> HealthRead:
    """Check database, Redis, and broker connectivity."""

    database_ok = await _check_database(session)
    redis_ok = await _check_redis(redis)
    broker_ok = await _check_broker()
    overall = "ok" if database_ok and redis_ok and broker_ok else "degraded"
    return HealthRead(
        status=overall,
        database=database_ok,
        redis=redis_ok,
        broker=broker_ok,
    )


@app.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    actor: Actor = Depends(require_role("organizer")),
    _: None = Depends(rate_limit("events:create")),
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> Event:
    """Create a new event as an organizer."""

    event = Event(**payload.model_dump(), organizer_id=actor.subject)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    await cache.invalidate()
    logger.info("event_created", event_id=event.id, organizer_id=actor.subject)
    return event


@app.get("/events", response_model=list[EventRead])
async def list_events(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    date_from: datetime | None = None,
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> list[dict[str, object]]:
    """List events with pagination, date filtering, and Redis caching."""

    cache_key = cache.build_key(page=page, size=size, date_from=date_from)
    cached = await cache.get_events(cache_key)
    if cached is not None:
        return cached

    statement = select(Event)
    if date_from is not None:
        statement = statement.where(Event.starts_at >= date_from)
    statement = (
        statement.order_by(Event.starts_at).offset((page - 1) * size).limit(size)
    )
    result = await session.execute(statement)
    events = result.scalars().all()
    serialized = [
        EventRead.model_validate(event).model_dump(mode="json") for event in events
    ]
    await cache.set_events(cache_key, serialized)
    return serialized


@app.post(
    "/tickets/purchase",
    response_model=TicketRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def purchase_ticket(
    payload: TicketPurchase,
    actor: Actor = Depends(require_role("user", "organizer")),
    _: None = Depends(rate_limit("tickets:purchase")),
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> Ticket:
    """Purchase a ticket and queue background ticket generation."""

    result = await session.execute(
        select(Event).where(Event.id == payload.event_id).with_for_update()
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise EventNotFoundError("Event not found")
    if event.tickets_available <= 0:
        raise SoldOutError("Tickets are sold out")

    try:
        stripe_client.charge(payload.card_number, event.price_cents)
    except StripePaymentError as exc:
        raise PaymentRejectedError(str(exc)) from exc

    task_id = celery_uuid()
    ticket = Ticket(
        event_id=event.id,
        buyer_id=actor.subject,
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
    logger.info("ticket_purchase_queued", ticket_id=ticket.id, task_id=task_id)
    return ticket


@app.post("/tickets/{ticket_id}/return", response_model=TicketRead)
async def return_ticket(
    ticket_id: int,
    payload: TicketReturnRequest,
    actor: Actor = Depends(require_role("user", "organizer")),
    _: None = Depends(rate_limit("tickets:return")),
    session: AsyncSession = Depends(get_session),
    cache: RedisEventCache = Depends(get_event_cache),
) -> Ticket:
    """Return a ticket, update inventory, and publish a worker event."""

    result = await session.execute(
        select(Ticket, Event).join(Event).where(Ticket.id == ticket_id).with_for_update()
    )
    row = result.first()
    if row is None:
        raise TicketNotFoundError("Ticket not found")
    ticket, event = row
    if ticket.buyer_id != actor.subject and actor.role != "organizer":
        raise ForbiddenTicketError("Only the buyer or organizer can return this ticket")
    if ticket.status in {"return_queued", "returned"}:
        return ticket

    ticket.status = "return_queued"
    ticket.returned_at = utc_now()
    event.tickets_available += 1
    await session.commit()
    await session.refresh(ticket)
    return_ticket_task.apply_async(args=[ticket.id, payload.reason])
    await cache.invalidate()
    logger.info("ticket_return_queued", ticket_id=ticket.id, actor_id=actor.subject)
    return ticket


@app.get("/tickets/{task_id}", response_model=TicketStatus)
async def get_ticket_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TicketStatus:
    """Return ticket generation status by Celery task identifier."""

    result = await session.execute(select(Ticket).where(Ticket.task_id == task_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise TicketNotFoundError("Ticket task not found")

    celery_state = AsyncResult(task_id, app=celery_app).state
    return TicketStatus(
        task_id=task_id,
        celery_state=celery_state,
        ticket_status=ticket.status,
        file_path=ticket.file_path,
    )


async def _check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("health_database_failed", error=str(exc))
        return False


async def _check_redis(redis: Redis) -> bool:
    try:
        await redis.ping()
        return True
    except Exception as exc:
        logger.error("health_redis_failed", error=str(exc))
        return False


async def _check_broker() -> bool:
    try:
        await asyncio.to_thread(_ensure_broker_connection)
        return True
    except Exception as exc:
        logger.error("health_broker_failed", error=str(exc))
        return False


def _ensure_broker_connection() -> None:
    with celery_app.connection_for_read() as connection:
        connection.ensure_connection(max_retries=1)
