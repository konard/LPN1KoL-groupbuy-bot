"""Admin API — admin-only endpoints for managing users, categories, and viewing statistics."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import CategoryModel, ParticipantModel, PaymentModel, ProcurementModel, UserModel
from app.services.auth_service import admin_user

router = APIRouter(prefix="/admin/api", tags=["Admin"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    icon: str = ""


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str
    parent_id: Optional[int]
    icon: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_users: int
    active_users: int
    total_procurements: int
    active_procurements: int
    total_payments: int
    total_revenue: float
    total_participants: int


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=list[AdminUserOut],
    summary="List all users",
    description="Return a paginated list of all registered users. Admin only.",
)
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(admin_user),
):
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "is_active": u.is_active, "is_admin": u.is_admin,
            "balance": float(u.balance or 0), "created_at": u.created_at,
        }
        for u in users
    ]


@router.get(
    "/users/{user_id}",
    response_model=AdminUserOut,
    summary="Get user by ID",
    description="Return a single user by ID. Admin only.",
)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "is_active": user.is_active, "is_admin": user.is_admin,
        "balance": float(user.balance or 0), "created_at": user.created_at,
    }


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserOut,
    summary="Update user",
    description="Update any user's fields including admin status. Admin only.",
)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    _=Depends(admin_user),
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "is_active": user.is_active, "is_admin": user.is_admin,
        "balance": float(user.balance or 0), "created_at": user.created_at,
    }


@router.delete(
    "/users/{user_id}",
    status_code=204,
    summary="Delete user",
    description="Permanently delete a user account. Admin only.",
)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


# ── Categories ────────────────────────────────────────────────────────────────

@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=201,
    summary="Create category",
    description="Create a new procurement category. Admin only.",
)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    _=Depends(admin_user),
):
    cat = CategoryModel(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete(
    "/categories/{cat_id}",
    status_code=204,
    summary="Deactivate category",
    description="Soft-delete (deactivate) a category. Admin only.",
)
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = db.query(CategoryModel).filter(CategoryModel.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    db.commit()


# ── Statistics ────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=StatsOut,
    summary="Platform statistics",
    description="Return aggregate platform statistics. Admin only.",
)
def get_stats(db: Session = Depends(get_db), _=Depends(admin_user)):
    total_users = db.query(UserModel).count()
    active_users = db.query(UserModel).filter(UserModel.is_active == True).count()
    total_procurements = db.query(ProcurementModel).count()
    active_procurements = db.query(ProcurementModel).filter(
        ProcurementModel.status == "active"
    ).count()
    total_payments = db.query(PaymentModel).count()
    revenue_result = db.query(PaymentModel).filter(
        PaymentModel.payment_type == "deposit",
        PaymentModel.status == "succeeded",
    ).all()
    total_revenue = sum(float(p.amount) for p in revenue_result)
    total_participants = db.query(ParticipantModel).filter(
        ParticipantModel.is_active == True
    ).count()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_procurements": total_procurements,
        "active_procurements": active_procurements,
        "total_payments": total_payments,
        "total_revenue": total_revenue,
        "total_participants": total_participants,
    }
