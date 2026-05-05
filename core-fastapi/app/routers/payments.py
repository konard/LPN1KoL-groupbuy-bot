"""Payment endpoints — mirrors core-rust handlers/payments.rs"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_pool
from ..schemas import CreatePayment

logger = logging.getLogger("core.payments")
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", status_code=201, summary="Create payment")
async def create_payment(body: CreatePayment, pool=Depends(get_pool)):
    try:
        row = await pool.fetchrow(
            """INSERT INTO payments (user_id, payment_type, amount, procurement_id, description)
               VALUES ($1,$2,$3,$4,$5)
               RETURNING *""",
            body.user_id,
            body.payment_type,
            body.amount,
            body.procurement_id,
            body.description or "",
        )
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}/status/", summary="Get payment status")
async def get_payment_status(payment_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM payments WHERE id=$1", payment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    status_display = {
        "pending": "Pending",
        "waiting_for_capture": "Waiting for Capture",
        "succeeded": "Succeeded",
        "cancelled": "Cancelled",
        "refunded": "Refunded",
    }.get(row["status"], row["status"])
    return {
        "id": row["id"],
        "status": row["status"],
        "status_display": status_display,
        "amount": row["amount"],
        "confirmation_url": row["confirmation_url"],
    }
