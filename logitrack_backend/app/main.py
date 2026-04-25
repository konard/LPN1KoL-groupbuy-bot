import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket
from fastapi import WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from strawberry.fastapi import GraphQLRouter

from .config import settings
from .database import AsyncSessionLocal, get_session, init_db
from .errors import LogiTrackError, OrderNotFoundError, RateLimitExceededError
from .graphql_schema import schema
from .models import Order, OrderHistory
from .observability import configure_logging
from .schemas import AssignCourier, HealthRead, OrderCreate, OrderRead
from .tracking import ConnectionManager, get_latest_coordinates, simulate_courier


configure_logging()
logger = structlog.get_logger(__name__)
redis_client: Redis | None = None
manager = ConnectionManager()
tracking_tasks: dict[int, asyncio.Task[None]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize database, Redis, and graceful tracking shutdown."""

    global redis_client
    await init_db()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("logitrack_started")
    yield
    for task in tracking_tasks.values():
        task.cancel()
    if tracking_tasks:
        await asyncio.gather(*tracking_tasks.values(), return_exceptions=True)
    if redis_client is not None:
        await redis_client.aclose()
    logger.info("logitrack_stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(LogiTrackError)
async def logitrack_exception_handler(
    request: Request,
    exc: LogiTrackError,
) -> JSONResponse:
    """Map domain errors to consistent JSON HTTP responses."""

    logger.error(
        "logitrack_error",
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


async def require_api_token(
    x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None,
) -> None:
    """Require the configured API token for REST operations."""

    if x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid API token")


def rate_limit(scope: str) -> Callable[[Request, Redis], Awaitable[None]]:
    """Create a Redis-backed rate limit dependency."""

    async def dependency(
        request: Request,
        redis: Redis = Depends(get_redis),
    ) -> None:
        client_host = request.client.host if request.client is not None else "unknown"
        token = request.headers.get("x-api-token", client_host)
        key = f"logitrack:rate:{scope}:{token}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, settings.rate_limit_window_seconds)
        if current > settings.rate_limit_max_requests:
            raise RateLimitExceededError("Too many requests")

    return dependency


async def graphql_context(
    session: AsyncSession = Depends(get_session),
) -> dict[str, AsyncSession]:
    """Provide request context for GraphQL resolvers."""

    return {"session": session}


app.include_router(
    GraphQLRouter(schema, context_getter=graphql_context),
    prefix="/graphql",
)


@app.get("/health", response_model=HealthRead)
async def health(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> HealthRead:
    """Check database and Redis connectivity."""

    database_ok = await _check_database(session)
    redis_ok = await _check_redis(redis)
    overall = "ok" if database_ok and redis_ok else "degraded"
    return HealthRead(status=overall, database=database_ok, redis=redis_ok)


@app.post("/orders", response_model=OrderRead, status_code=201)
async def create_order(
    payload: OrderCreate,
    auth: None = Depends(require_api_token),
    throttle: None = Depends(rate_limit("orders:create")),
    session: AsyncSession = Depends(get_session),
) -> Order:
    """Create a delivery order."""

    order = Order(destination=payload.destination, status="created")
    session.add(order)
    await session.flush()
    session.add(OrderHistory(order_id=order.id, status="created"))
    await session.commit()
    await session.refresh(order)
    logger.info("order_created", order_id=order.id)
    return order


@app.post("/orders/{order_id}/courier", response_model=OrderRead)
async def assign_courier(
    order_id: int,
    payload: AssignCourier,
    auth: None = Depends(require_api_token),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> Order:
    """Assign a courier and start simulated tracking."""

    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise OrderNotFoundError("Order not found")

    order.courier_id = payload.courier_id
    order.status = "assigned"
    session.add(OrderHistory(order_id=order.id, status="assigned"))
    await session.commit()
    await session.refresh(order)

    task = tracking_tasks.get(order.id)
    if task is None or task.done():
        tracking_tasks[order.id] = asyncio.create_task(
            simulate_courier(order.id, AsyncSessionLocal, redis, manager)
        )

    logger.info("courier_assigned", order_id=order.id, courier_id=payload.courier_id)
    return order


@app.websocket("/ws/orders/{order_id}")
async def order_updates(
    websocket: WebSocket,
    order_id: int,
    redis: Redis = Depends(get_redis),
) -> None:
    """Stream authenticated order coordinate updates."""

    token = websocket.query_params.get("token")
    if token != settings.api_token:
        await websocket.close(code=1008)
        return

    await manager.connect(order_id, websocket)
    latest = await get_latest_coordinates(redis, order_id)
    if latest is not None:
        await websocket.send_json(latest)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)


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
