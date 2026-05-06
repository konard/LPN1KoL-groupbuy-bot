"""FastAPI core service — full rewrite of core-rust.

Exposes all endpoints previously served by the Rust backend:
  /health
  /api/users/*
  /api/procurements/*
  /api/payments/*
  /api/chat/*
  /api/docs/
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import connect, disconnect, init_schema
from app.routers import users, procurements, payments, chat
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


app = FastAPI(
    title="GroupBuy Bot API",
    version="1.0.0",
    description="API for GroupBuy Bot — a multi-platform group purchasing bot",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/schema/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
@app.get("/health/", response_model=HealthResponse, tags=["health"], include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(users.router, prefix="/api")
app.include_router(procurements.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
