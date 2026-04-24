import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import GraphQLRouter

from .config import settings
from .database import AsyncSessionLocal, get_session, init_db
from .graphql_schema import schema
from .models import Order, OrderHistory
from .schemas import AssignCourier, OrderCreate, OrderRead
from .tracking import ConnectionManager, get_latest_coordinates, simulate_courier


redis_client: Redis | None = None
manager = ConnectionManager()
tracking_tasks: dict[int, asyncio.Task[None]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global redis_client
    await init_db()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    for task in tracking_tasks.values():
        task.cancel()
    await redis_client.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


async def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return redis_client


async def graphql_context(
    session: AsyncSession = Depends(get_session),
) -> dict[str, AsyncSession]:
    return {"session": session}


app.include_router(
    GraphQLRouter(schema, context_getter=graphql_context),
    prefix="/graphql",
)


@app.post("/orders", response_model=OrderRead, status_code=201)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
) -> Order:
    order = Order(destination=payload.destination, status="created")
    session.add(order)
    await session.flush()
    session.add(OrderHistory(order_id=order.id, status="created"))
    await session.commit()
    await session.refresh(order)
    return order


@app.post("/orders/{order_id}/courier", response_model=OrderRead)
async def assign_courier(
    order_id: int,
    payload: AssignCourier,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

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

    return order


@app.websocket("/ws/orders/{order_id}")
async def order_updates(
    websocket: WebSocket,
    order_id: int,
    redis: Redis = Depends(get_redis),
) -> None:
    await manager.connect(order_id, websocket)
    latest = await get_latest_coordinates(redis, order_id)
    if latest is not None:
        await websocket.send_json(latest)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)
