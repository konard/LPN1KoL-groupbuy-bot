from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import PaymentModel
from app.services.auth_service import current_user

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCreate(BaseModel):
    payment_type: str
    amount: float
    procurement_id: Optional[int] = None
    description: str = ""


class PaymentOut(BaseModel):
    id: int
    user_id: int
    procurement_id: Optional[int]
    payment_type: str
    amount: float
    status: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


def _pay_out(pay: PaymentModel) -> dict:
    return {
        "id": pay.id, "user_id": pay.user_id, "procurement_id": pay.procurement_id,
        "payment_type": pay.payment_type, "amount": float(pay.amount),
        "status": pay.status, "description": pay.description or "",
        "created_at": pay.created_at,
    }


@router.get("", response_model=list[PaymentOut])
def list_payments(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), user=Depends(current_user)):
    q = db.query(PaymentModel)
    if not user.is_admin:
        q = q.filter(PaymentModel.user_id == user.id)
    return [_pay_out(p) for p in q.order_by(PaymentModel.created_at.desc()).offset(skip).limit(limit).all()]


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(data: PaymentCreate, db: Session = Depends(get_db), user=Depends(current_user)):
    if data.payment_type not in ("deposit", "withdrawal", "procurement_payment"):
        raise HTTPException(status_code=400, detail="Invalid payment_type")
    pay = PaymentModel(
        user_id=user.id, procurement_id=data.procurement_id,
        payment_type=data.payment_type, amount=data.amount,
        description=data.description, status="succeeded",
    )
    db.add(pay)
    if data.payment_type == "deposit":
        user.balance = float(user.balance) + data.amount
    elif data.payment_type in ("withdrawal", "procurement_payment"):
        if float(user.balance) < data.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance = float(user.balance) - data.amount
    db.commit()
    db.refresh(pay)
    return _pay_out(pay)


@router.get("/{pay_id}", response_model=PaymentOut)
def get_payment(pay_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    pay = db.query(PaymentModel).filter(PaymentModel.id == pay_id).first()
    if not pay:
        raise HTTPException(status_code=404, detail="Payment not found")
    if pay.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _pay_out(pay)
