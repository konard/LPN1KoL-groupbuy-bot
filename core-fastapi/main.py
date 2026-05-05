"""FastAPI core service entry point.

Exposes:
    GET  /health                Liveness probe used by docker-compose healthcheck
    *    /api/products[/{id}]   Example CRUD resource
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import connect, disconnect, init_schema
from app.routers import products
from app.schemas import HealthResponse

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("core")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    await init_schema()
    logger.info("Core service started on :%d", settings.port)
    try:
        yield
    finally:
        await disconnect()
        logger.info("Core service stopped")


app = FastAPI(title="GroupBuy Core", version="1.0.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(products.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
