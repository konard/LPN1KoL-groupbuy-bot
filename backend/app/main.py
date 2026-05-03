from sqlalchemy import text

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import CORS_ORIGINS
from app.core.database import Base, engine, get_db, SessionLocal
from app.core.security import hash_password
from app.models.models import UserModel  # noqa: F401 — registers all models with Base
from app.models.models import (CategoryModel, ChatMessageModel,  # noqa: F401
                                 ParticipantModel, PaymentModel, ProcurementModel)
from app.api import auth, chat, payments, procurements, users
from app.admin.views import setup_admin

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GroupBuy Backend API",
    description=(
        "Unified FastAPI backend for the GroupBuy platform.\n\n"
        "Covers authentication, user cabinet, procurements, payments, and chat.\n\n"
        "**Authentication**: use `/auth/login` to get a Bearer token, "
        "then click **Authorize** above.\n\n"
        "Interactive docs: `/docs` · Admin panel: `/admin`"
    ),
    version="2.0.0",
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

setup_admin(app, engine)


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
