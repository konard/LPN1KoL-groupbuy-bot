"""Payment endpoints — mirrors core-rust handlers/payments.rs"""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreatePayment, CreateWithdrawal

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


@router.get("/", summary="List payments for a user")
async def list_payments(
    user_id: UUID | None = Query(default=None),
    pool=Depends(get_pool),
):
    if user_id is not None:
        rows = await pool.fetch(
            "SELECT * FROM payments WHERE user_id=$1 ORDER BY created_at DESC LIMIT 200",
            user_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM payments ORDER BY created_at DESC LIMIT 200"
        )
    return {"results": [dict(r) for r in rows]}


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


# ─── Withdrawal requests (issue #194: form 1.4 «Вывод средств») ───────────────

@router.post("/withdrawals/", status_code=201, summary="Request a withdrawal")
async def create_withdrawal(body: CreateWithdrawal, pool=Depends(get_pool)):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive.")
    if not body.bank_details.strip():
        raise HTTPException(
            status_code=400,
            detail={"bank_details": ["Обязательное поле."]},
        )
    user = await pool.fetchrow("SELECT id, balance FROM users WHERE id=$1", body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user["balance"] < body.amount:
        raise HTTPException(status_code=400, detail="Insufficient funds.")
    row = await pool.fetchrow(
        """INSERT INTO withdrawal_requests (user_id, amount, bank_details, status)
           VALUES ($1, $2, $3, 'pending') RETURNING *""",
        body.user_id, body.amount, body.bank_details.strip(),
    )
    return dict(row)


@router.get("/withdrawals/", summary="List withdrawal requests")
async def list_withdrawals(
    user_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    pool=Depends(get_pool),
):
    clauses: list[str] = []
    args: list = []
    if user_id is not None:
        args.append(user_id)
        clauses.append(f"user_id=${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status=${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = await pool.fetch(
        f"SELECT * FROM withdrawal_requests {where} ORDER BY created_at DESC LIMIT 200",
        *args,
    )
    return {"results": [dict(r) for r in rows]}


@router.post("/withdrawals/{withdrawal_id}/process/", summary="Process a withdrawal request")
async def process_withdrawal(withdrawal_id: int, body: dict | None = None, pool=Depends(get_pool)):
    """Marks a withdrawal as approved or rejected. On approval the amount is
    debited from the user's balance and recorded in ``transactions``."""
    new_status = (body or {}).get("status", "approved")
    if new_status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'rejected'.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            wr = await conn.fetchrow(
                "SELECT * FROM withdrawal_requests WHERE id=$1 FOR UPDATE", withdrawal_id
            )
            if not wr:
                raise HTTPException(status_code=404, detail="Not found.")
            if wr["status"] != "pending":
                raise HTTPException(status_code=400, detail="Already processed.")

            if new_status == "approved":
                user = await conn.fetchrow(
                    "SELECT balance FROM users WHERE id=$1 FOR UPDATE", wr["user_id"]
                )
                if not user or user["balance"] < wr["amount"]:
                    raise HTTPException(status_code=400, detail="Insufficient funds.")
                new_balance = user["balance"] - wr["amount"]
                await conn.execute(
                    "UPDATE users SET balance=$2, updated_at=NOW() WHERE id=$1",
                    wr["user_id"], new_balance,
                )
                await conn.execute(
                    """INSERT INTO transactions
                         (user_id, transaction_type, amount, balance_after, description)
                       VALUES ($1, 'withdrawal', $2, $3, 'Withdrawal request approved')""",
                    wr["user_id"], -wr["amount"], new_balance,
                )

            row = await conn.fetchrow(
                """UPDATE withdrawal_requests
                      SET status=$2, processed_at=NOW()
                    WHERE id=$1 RETURNING *""",
                withdrawal_id, new_status,
            )
    return dict(row)
