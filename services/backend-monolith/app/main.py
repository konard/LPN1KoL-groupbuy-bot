from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.kafka_producer import stop_producer
from app.modules.analytics.router import (
    router as analytics_router,
    start_analytics_consumer,
    stop_analytics_consumer,
)
from app.modules.auth.router import router as auth_router
from app.modules.chat.router import close_chat_connections, router as chat_router
from app.modules.notification.router import (
    router as notification_router,
    start_notification_consumer,
    stop_notification_consumer,
)
from app.modules.payment.router import escrow_router, router as wallet_router
from app.modules.purchase.router import router as purchase_router
from app.modules.reputation.router import router as reputation_router
from app.modules.search.router import close_search, init_search, router as search_router

CORS_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_search()
    start_notification_consumer()
    start_analytics_consumer()
    yield
    await stop_producer()
    await stop_notification_consumer()
    await stop_analytics_consumer()
    await close_chat_connections()
    await close_search()


app = FastAPI(
    title="GroupBuy Backend",
    description=(
        "Unified backend for the GroupBuy platform. "
        "Covers authentication, purchases, payments, chat, notifications, analytics, and search.\n\n"
        "**Authentication**: use `/auth/login` to obtain a Bearer token, then click **Authorize** above.\n\n"
        "Interactive docs: `/docs` · Machine-readable schema: `/openapi.json`"
    ),
    version="2.0.0",
    contact={"name": "GroupBuy Team"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(purchase_router)
app.include_router(wallet_router)
app.include_router(escrow_router)
app.include_router(reputation_router)
app.include_router(chat_router)
app.include_router(notification_router)
app.include_router(analytics_router)
app.include_router(search_router)


@app.get("/health", tags=["system"], summary="Liveness check")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/ready", tags=["system"], summary="Readiness check")
async def ready():
    return JSONResponse({"status": "ready"})


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from /auth/login",
        }
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict):
                operation.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
