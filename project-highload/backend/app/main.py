from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import close_db, get_session, init_db, ping_db
from app.models import Item
from app.redis_client import redis_publisher


items_created_total = 0


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await redis_publisher.connect()
    yield
    await redis_publisher.close()
    await close_db()


app = FastAPI(title="GroupBuy Highload Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    await ping_db()
    await redis_publisher.ping()
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return (
        "# HELP groupbuy_backend_items_created_total Items created through the REST API\n"
        "# TYPE groupbuy_backend_items_created_total counter\n"
        f"groupbuy_backend_items_created_total {items_created_total}\n"
    )


@app.get("/api/items")
async def list_items(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    result = await session.execute(select(Item).order_by(Item.id.desc()).limit(100))
    return [item.to_dict() for item in result.scalars()]


@app.post("/api/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    global items_created_total

    item = Item(name=payload.name.strip(), description=payload.description)
    session.add(item)
    await session.commit()
    await session.refresh(item)

    item_dict = item.to_dict()
    try:
        await redis_publisher.publish_item_created(item_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="item persisted but Redis publish failed",
        ) from exc

    items_created_total += 1
    return item_dict
