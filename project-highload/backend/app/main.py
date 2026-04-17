import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db, create_tables
from .models import Item
from .redis_client import publish, close_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    await create_tables()
    logger.info("Database tables created")
    yield
    await close_redis()
    logger.info("Redis connection closed")


app = FastAPI(title="GroupBuy High-Load Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemOut(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/items", response_model=list[ItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).order_by(Item.id.desc()).limit(100))
    return result.scalars().all()


@app.post("/api/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(name=payload.name, description=payload.description)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    event = json.dumps({"id": item.id, "name": item.name, "description": item.description})
    await publish("items:new", event)
    logger.info("Published items:new event for item %s", item.id)

    return item
