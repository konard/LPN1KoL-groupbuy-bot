from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.kafka_producer import stop_producer
from app.modules.auth.router import router as auth_router, users_router
from app.modules.chat.router import router as chat_router
from app.modules.notification.router import router as notify_router
from app.modules.payment.router import escrow_router, router as wallet_router
from app.modules.purchase.router import categories_router, router as purchase_router
from app.modules.reputation.router import router as reputation_router
from app.modules.search.router import router as search_router
from app.modules.search.service import close_es
from app.socket.socketio_server import sio


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await stop_producer()
    await close_es()


app = FastAPI(
    title="GroupBuy Backend Monolith",
    version="2.1.0",
    description=(
        "Consolidated FastAPI backend for the GroupBuy platform.\n\n"
        "**Modules:**\n"
        "- **auth** — registration, login, JWT refresh, 2FA (TOTP)\n"
        "- **users** — user management: list, search, balance, role, WebSocket token\n"
        "- **categories** — procurement category hierarchy\n"
        "- **purchases** — full group-purchase lifecycle: create, join, vote, approve supplier, close\n"
        "- **wallets / escrow** — internal balance and escrow management\n"
        "- **reputation** — reviews and aggregate ratings\n"
        "- **chat** — chat rooms and messages\n"
        "- **search** — Elasticsearch-backed full-text search\n"
        "- **notification** — multi-channel notification dispatch\n"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

cors_origins = (
    [o.strip() for o in settings.cors_origins.split(",")]
    if settings.cors_origins != "*"
    else ["*"]
)
# CORS spec forbids `Access-Control-Allow-Origin: *` together with
# `Access-Control-Allow-Credentials: true` — browsers reject such responses.
# When origins are wildcarded (typical dev setup), drop the credentials flag
# so the header negotiation succeeds.
allow_credentials = cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing modules
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(purchase_router)
app.include_router(wallet_router)
app.include_router(escrow_router)
app.include_router(reputation_router)

# Consolidated modules (formerly separate microservices)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(notify_router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/ready")
async def ready():
    return JSONResponse({"status": "ready"})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "code": "INTERNAL_ERROR", "message": str(exc)},
    )


# NOTE: Mount Socket.IO ASGI app at /ws so existing HTTP routes are unaffected.
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
