from sqlalchemy import text

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session

from app.core.config import CORS_ORIGINS
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.security import hash_password
from app.models.models import UserModel  # noqa: F401 — registers all models with Base
from app.models.models import (CategoryModel, ChatMessageModel,  # noqa: F401
                                 ParticipantModel, PaymentModel, ProcurementModel)
from app.api import auth, chat, payments, procurements, users, profile, admin_api
from app.admin.views import setup_admin

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GroupBuy Backend API",
    description=(
        "Unified FastAPI backend for the GroupBuy platform.\n\n"
        "## Authentication\n\n"
        "Use `POST /auth/login` to obtain a Bearer token, then click the "
        "**Authorize** button (🔒) at the top of this page and enter "
        "`Bearer <your-token>`.\n\n"
        "## Sections\n\n"
        "- **Auth** — registration, login, current user profile\n"
        "- **User Cabinet** — view/update own profile, order history, balance, payments\n"
        "- **Procurements** — browse, create, and manage group-buy procurements\n"
        "- **Admin** — manage users, categories, and view platform statistics (admin only)\n"
        "- **Chat** — per-room message history\n"
        "- **Payments** — deposit, withdraw, and query transactions\n\n"
        "Interactive docs: `/docs` · ReDoc: `/redoc` · Admin panel: `/admin`"
    ),
    version="2.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Registration, login and token operations"},
        {"name": "User Cabinet", "description": "Authenticated user's own profile, orders, and balance"},
        {"name": "procurements", "description": "Browse and manage group-buy procurements"},
        {"name": "payments", "description": "Deposit, withdraw, and query payment transactions"},
        {"name": "chat", "description": "Per-room chat message history"},
        {"name": "Admin", "description": "Admin-only: manage users, categories, and view statistics"},
        {"name": "system", "description": "Health and internal service endpoints"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(procurements.router)
app.include_router(payments.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(admin_api.router)

setup_admin(app, engine)


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


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return JSONResponse({"status": "ok", "database": db_status})


@app.on_event("startup")
def _seed_admin():
    """Create default admin user on first run if none exists."""
    import os
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@localhost")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    db = SessionLocal()
    try:
        if not db.query(UserModel).filter(UserModel.is_admin == True).first():
            db.add(UserModel(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                is_admin=True,
                is_active=True,
            ))
            db.commit()
    finally:
        db.close()
