"""
Роутер платежей (/api/payments/*).
Перенесён из payment-service (порт 4003).
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.payment import (
    EscrowDepositRequest, HoldRequest, ReleaseRequest,
    TopUpRequest, TransactionOut, WalletOut,
)
from app.services import payment_service as svc

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/wallet", response_model=WalletOut)
def get_wallet(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Возвращает кошелёк текущего пользователя. Создаёт автоматически при первом запросе."""
    return svc.get_wallet(db, user.id)


@router.post("/wallet/topup", response_model=TransactionOut)
async def top_up(data: TopUpRequest, db: Session = Depends(get_db),
                 user=Depends(get_current_user)):
    """Пополняет кошелёк пользователя."""
    return await svc.top_up(db, user.id, data.amount, data.description or "")


@router.post("/wallet/hold", response_model=TransactionOut)
async def hold_funds(data: HoldRequest, db: Session = Depends(get_db),
                     user=Depends(get_current_user)):
    """Замораживает средства под закупку."""
    return await svc.hold_funds(db, user.id, data.amount, data.purchase_id, data.description or "")


@router.post("/wallet/release", response_model=TransactionOut)
async def release_funds(data: ReleaseRequest, db: Session = Depends(get_db),
                        user=Depends(get_current_user)):
    """Размораживает зарезервированные средства."""
    return await svc.release_funds(db, user.id, data.amount, data.purchase_id, data.description or "")


@router.post("/escrow/deposit")
async def deposit_escrow(data: EscrowDepositRequest, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    """Переводит средства на эскроу-счёт закупки."""
    escrow = await svc.deposit_escrow(db, data.purchase_id, data.amount)
    return {"success": True, "escrowId": escrow.id, "totalDeposited": float(escrow.total_deposited)}


@router.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Возвращает историю транзакций текущего пользователя."""
    return svc.list_transactions(db, user.id, skip, limit)
