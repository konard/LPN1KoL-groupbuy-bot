"""
Точка входа FastAPI-монолита groupbuy-core.
Объединяет все микросервисы: auth, purchases, payments, chat,
notifications, analytics, search, reputation, gateway.

Swagger UI: http://localhost:8000/docs
Health:     http://localhost:8000/health
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.clients.kafka_client import close_kafka, init_kafka
from app.clients.redis_client import close_redis, init_redis
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME, CORS_ORIGINS
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.security import hash_password

# Регистрируем все модели в Base.metadata перед create_all
import app.models  # noqa: F401

# Роутеры новых модулей (из микросервисов)
from app.routers import analytics, auth as new_auth, chat as new_chat, gateway
from app.routers import notifications, payments as new_payments, purchases, reputation, search

# Роутеры существующей структуры (обратная совместимость)
from app.api import auth, chat, payments, procurements, users, profile, admin_api
from app.admin.views import setup_admin
from app.models.models import UserModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Инициализирует внешние клиенты при старте и освобождает при остановке."""
    # Создаём таблицы (в продакшне используйте alembic)
    Base.metadata.create_all(bind=engine)

    # Инициализация клиентов (не блокируют запуск при недоступности)
    await init_redis()
    await init_kafka()

    # Создаём администратора по умолчанию
    db = SessionLocal()
    try:
        if not db.query(UserModel).filter(UserModel.is_admin == True).first():  # noqa: E712
            db.add(UserModel(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                is_admin=True,
                is_active=True,
            ))
            db.commit()
            logger.info("Создан администратор по умолчанию: %s", ADMIN_USERNAME)
    finally:
        db.close()

    logger.info("groupbuy-core запущен")
    yield

    await close_kafka()
    await close_redis()
    logger.info("groupbuy-core остановлен")


app = FastAPI(
    title="GroupBuy Core API",
    description=(
        "Единый FastAPI-монолит GroupBuy Platform.\n\n"
        "## Аутентификация\n\n"
        "Используйте `POST /api/auth/login` для получения Bearer-токена, "
        "затем нажмите кнопку **Authorize** (🔒) и введите `Bearer <токен>`.\n\n"
        "## Модули (новые /api/* роуты из микросервисов)\n\n"
        "- **auth** → `/api/auth/*` — регистрация, вход, профиль\n"
        "- **purchases** → `/api/purchases/*` — закупки, голосование за поставщиков\n"
        "- **payments** → `/api/payments/*` — кошелёк, транзакции, эскроу\n"
        "- **chat** → `/api/chat/*` — комнаты, сообщения, Centrifugo WebSocket\n"
        "- **notifications** → `/api/notifications/*` — email, Telegram, in-app\n"
        "- **analytics** → `/api/analytics/*` — статистика, отчёты, S3\n"
        "- **search** → `/api/search/*` — Elasticsearch, сохранённые фильтры, история\n"
        "- **reputation** → `/api/reputation/*` — отзывы, жалобы, автоблокировка\n"
        "- **gateway** → `/api/gateway/*` — статус шлюза\n\n"
        "## Существующие маршруты\n\n"
        "- `/auth/*`, `/procurements/*`, `/payments/*`, `/chat/*` (legacy)\n\n"
        "Docs: `/docs` · ReDoc: `/redoc` · Admin: `/admin`"
    ),
    version="3.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Аутентификация и профиль"},
        {"name": "purchases", "description": "Закупки и голосование за поставщиков"},
        {"name": "payments", "description": "Кошелёк, транзакции и эскроу"},
        {"name": "chat", "description": "Чат-комнаты и сообщения"},
        {"name": "notifications", "description": "Уведомления (email, Telegram, in-app)"},
        {"name": "analytics", "description": "Аналитика и отчёты"},
        {"name": "search", "description": "Полнотекстовый поиск и фильтры"},
        {"name": "reputation", "description": "Репутация: отзывы и жалобы"},
        {"name": "gateway", "description": "Статус шлюза"},
        {"name": "system", "description": "Системные эндпоинты"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Новые роутеры из микросервисов (/api/*) ─────────────────────────────────
app.include_router(new_auth.router)
app.include_router(purchases.router)
app.include_router(new_payments.router)
app.include_router(new_chat.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(reputation.router)
app.include_router(gateway.router)

# ─── Существующие роутеры (обратная совместимость) ───────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(procurements.router)
app.include_router(payments.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(admin_api.router)

setup_admin(app, engine)


# ─── OpenAPI схема с BearerAuth ───────────────────────────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=app.openapi_tags,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    """Проверяет доступность сервиса и базы данных."""
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return JSONResponse({
        "status": "ok",
        "database": db_status,
        "version": app.version,
    })
