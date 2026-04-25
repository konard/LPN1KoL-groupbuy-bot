from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.kafka_producer import stop_producer
from app.modules.auth.router import router as auth_router, users_router
from app.modules.chat.router import router as chat_router
from app.modules.invitations.router import router as invitations_router
from app.modules.intelligence.router import router as intelligence_router
from app.modules.news.router import router as news_router
from app.modules.notification.router import router as notify_router
from app.modules.payment.router import escrow_router, router as wallet_router
from app.modules.purchase.router import categories_router, router as purchase_router
from app.modules.reputation.router import router as reputation_router
from app.modules.requests.router import router as requests_router
from app.modules.search.router import router as search_router
from app.modules.search.service import close_es
from app.modules.supplier.router import router as supplier_router
from app.socket.socketio_server import sio


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await stop_producer()
    await close_es()


app = FastAPI(
    title="Сервис организации закупок — Backend API",
    version="2.2.0",
    description=(
        "Backend API платформы для организации групповых закупок.\n\n"
        "Платформа объединяет **покупателей**, **организаторов** и **поставщиков**, "
        "обеспечивая прозрачность, удобство и автоматизацию процессов.\n\n"
        "**Модули:**\n"
        "- **Авторизация** — регистрация, вход, обновление JWT-токенов, двухфакторная аутентификация (TOTP)\n"
        "- **Пользователи** — управление профилями: поиск, баланс, роль, WebSocket-токен\n"
        "- **Категории** — иерархия категорий товаров\n"
        "- **Закупки** — полный жизненный цикл групповой закупки: создание, присоединение, голосование, утверждение поставщика, стоп-сумма, закрытие\n"
        "- **Запросы покупателей** — создание и управление запросами на товары\n"
        "- **Кошелёк / Эскроу** — управление балансом: пополнение, вывод средств, эскроу\n"
        "- **Репутация** — отзывы и агрегированные рейтинги\n"
        "- **Чат** — комнаты чата и сообщения (вертикальная лента и закрытые чаты закупок)\n"
        "- **Поиск** — полнотекстовый поиск по закупкам (Elasticsearch)\n"
        "- **Уведомления** — многоканальная отправка уведомлений (email, push, Telegram)\n"
        "- **Новости** — лента новостей от организаторов и поставщиков\n"
        "- **Поставщик** — карта компании, прайс-листы, закрывающие документы\n"
        "- **Приглашения** — приглашение поставщиков и покупателей в закупки\n"
        "- **Интеллект закупок** — прогноз достижения цели, риск-факторы, рекомендации, планы уведомлений и доставки\n"
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

# New modules per ТЗ requirements
app.include_router(news_router)
app.include_router(requests_router)
app.include_router(supplier_router)
app.include_router(invitations_router)
app.include_router(intelligence_router)


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
