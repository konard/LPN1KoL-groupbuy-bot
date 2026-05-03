"""User Cabinet — authenticated user's own profile, balance, and order history."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import ParticipantModel, PaymentModel, ProcurementModel, UserModel
from app.services.auth_service import current_user

router = APIRouter(prefix="/profile", tags=["User Cabinet"])


class ProfileOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class OrderHistoryItem(BaseModel):
    id: int
    procurement_id: int
    procurement_title: str
    quantity: float
    amount: float
    status: str
    joined_at: datetime

    class Config:
        from_attributes = True


class PaymentHistoryItem(BaseModel):
    id: int
    payment_type: str
    amount: float
    status: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get(
    "",
    response_model=ProfileOut,
    summary="Get own profile",
    description="Return the authenticated user's profile information.",
)
def get_profile(user: UserModel = Depends(current_user)):
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "is_active": user.is_active, "is_admin": user.is_admin,
        "balance": float(user.balance or 0), "created_at": user.created_at,
    }


@router.patch(
    "",
    response_model=ProfileOut,
    summary="Update own profile",
    description="Update the authenticated user's username or email.",
)
def update_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    if data.username is not None:
        existing = db.query(UserModel).filter(
            UserModel.username == data.username, UserModel.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = data.username
    if data.email is not None:
        existing = db.query(UserModel).filter(
            UserModel.email == data.email, UserModel.id != user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = data.email
    db.commit()
    db.refresh(user)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "is_active": user.is_active, "is_admin": user.is_admin,
        "balance": float(user.balance or 0), "created_at": user.created_at,
    }


@router.get(
    "/orders",
    response_model=list[OrderHistoryItem],
    summary="Get order history",
    description="Return the authenticated user's procurement participation history.",
)
def get_order_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    participants = (
        db.query(ParticipantModel)
        .filter(ParticipantModel.user_id == user.id)
        .order_by(ParticipantModel.joined_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for pt in participants:
        proc = db.query(ProcurementModel).filter(ProcurementModel.id == pt.procurement_id).first()
        result.append({
            "id": pt.id,
            "procurement_id": pt.procurement_id,
            "procurement_title": proc.title if proc else "",
            "quantity": float(pt.quantity or 1),
            "amount": float(pt.amount or 0),
            "status": pt.status,
            "joined_at": pt.joined_at,
        })
    return result


@router.get(
    "/payments",
    response_model=list[PaymentHistoryItem],
    summary="Get payment history",
    description="Return the authenticated user's payment transaction history.",
)
def get_payment_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: UserModel = Depends(current_user),
):
    payments = (
        db.query(PaymentModel)
        .filter(PaymentModel.user_id == user.id)
        .order_by(PaymentModel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "payment_type": p.payment_type,
            "amount": float(p.amount),
            "status": p.status,
            "description": p.description or "",
            "created_at": p.created_at,
        }
        for p in payments
    ]
