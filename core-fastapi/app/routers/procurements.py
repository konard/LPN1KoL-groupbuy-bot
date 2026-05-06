"""Procurement endpoints — mirrors core-rust handlers/procurements.rs"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateProcurement, JoinProcurement

logger = logging.getLogger("core.procurements")
router = APIRouter(prefix="/procurements", tags=["procurements"])


def _status_display(status: str) -> str:
    return {
        "draft": "Draft",
        "active": "Active",
        "stopped": "Stopped",
        "payment": "Payment in Progress",
        "completed": "Completed",
        "cancelled": "Cancelled",
    }.get(status, status)


def _to_response(row: dict, participant_count: int) -> dict:
    now = datetime.now(timezone.utc)
    target = row["target_amount"] or Decimal("0")
    current = row["current_amount"] or Decimal("0")
    progress = int((current / target * 100).to_integral_value()) if target > 0 else 0
    progress = min(progress, 100)
    deadline = row["deadline"]
    days_left = max(0, (deadline - now).days)
    stop_at = row["stop_at_amount"]
    can_join = (
        row["status"] == "active"
        and deadline > now
        and (stop_at is None or current < stop_at)
    )
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "category_id": row["category_id"],
        "organizer_id": row["organizer_id"],
        "supplier_id": row["supplier_id"],
        "city": row["city"],
        "delivery_address": row["delivery_address"],
        "target_amount": row["target_amount"],
        "current_amount": row["current_amount"],
        "stop_at_amount": row["stop_at_amount"],
        "unit": row["unit"],
        "price_per_unit": row["price_per_unit"],
        "status": row["status"],
        "status_display": _status_display(row["status"]),
        "commission_percent": row["commission_percent"],
        "min_quantity": row["min_quantity"],
        "deadline": row["deadline"],
        "payment_deadline": row["payment_deadline"],
        "image_url": row["image_url"],
        "is_featured": row["is_featured"],
        "progress": progress,
        "participant_count": participant_count,
        "days_left": days_left,
        "can_join": can_join,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.get("/", summary="List procurements")
async def list_procurements(
    status: str | None = Query(default=None),
    city: str | None = Query(default=None),
    pool=Depends(get_pool),
):
    if status and city:
        rows = await pool.fetch(
            "SELECT * FROM procurements WHERE status=$1 AND city=$2 ORDER BY created_at DESC",
            status, city,
        )
    elif status:
        rows = await pool.fetch(
            "SELECT * FROM procurements WHERE status=$1 ORDER BY created_at DESC", status
        )
    elif city:
        rows = await pool.fetch(
            "SELECT * FROM procurements WHERE city=$1 ORDER BY created_at DESC", city
        )
    else:
        rows = await pool.fetch("SELECT * FROM procurements ORDER BY created_at DESC")

    results = []
    for row in rows:
        count = await pool.fetchval(
            "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=true",
            row["id"],
        ) or 0
        results.append(_to_response(dict(row), count))
    return {"results": results}


@router.post("/", status_code=201, summary="Create procurement")
async def create_procurement(body: CreateProcurement, pool=Depends(get_pool)):
    try:
        row = await pool.fetchrow(
            """INSERT INTO procurements
               (title, description, category_id, organizer_id, city, delivery_address,
                target_amount, stop_at_amount, unit, price_per_unit, status,
                commission_percent, min_quantity, deadline, payment_deadline, image_url)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
               RETURNING *""",
            body.title,
            body.description,
            body.category_id,
            body.organizer_id,
            body.city,
            body.delivery_address or "",
            body.target_amount,
            body.stop_at_amount,
            body.unit or "units",
            body.price_per_unit,
            body.status or "draft",
            body.commission_percent or Decimal("0"),
            body.min_quantity,
            body.deadline,
            body.payment_deadline,
            body.image_url or "",
        )
        return _to_response(dict(row), 0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/categories/", summary="List categories")
async def list_categories(pool=Depends(get_pool)):
    rows = await pool.fetch("SELECT * FROM categories WHERE is_active=true ORDER BY name")
    return [dict(r) for r in rows]


@router.get("/user/{user_id}/", summary="Get user procurements")
async def get_user_procurements(user_id: UUID, pool=Depends(get_pool)):
    organized = await pool.fetch(
        "SELECT * FROM procurements WHERE organizer_id=$1 ORDER BY created_at DESC", user_id
    )
    participating = await pool.fetch(
        """SELECT p.* FROM procurements p
           JOIN participants pt ON p.id=pt.procurement_id
           WHERE pt.user_id=$1 AND pt.is_active=true
           ORDER BY p.created_at DESC""",
        user_id,
    )

    async def enrich(rows):
        result = []
        for row in rows:
            count = await pool.fetchval(
                "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=true",
                row["id"],
            ) or 0
            result.append(_to_response(dict(row), count))
        return result

    return {
        "organized": await enrich(organized),
        "participating": await enrich(participating),
    }


@router.get("/{proc_id}/", summary="Get procurement")
async def get_procurement(proc_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM procurements WHERE id=$1", proc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=true", proc_id
    ) or 0
    return _to_response(dict(row), count)


@router.post("/{proc_id}/join/", status_code=201, summary="Join procurement")
async def join_procurement(proc_id: int, body: JoinProcurement, pool=Depends(get_pool)):
    if body.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")
    row = await pool.fetchrow("SELECT * FROM procurements WHERE id=$1", proc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    if row["status"] != "active":
        raise HTTPException(status_code=400, detail="Procurement is not active")

    try:
        participant = await pool.fetchrow(
            """INSERT INTO participants (procurement_id, user_id, quantity, amount, notes)
               VALUES ($1,$2,$3,$4,$5)
               RETURNING *""",
            proc_id,
            body.user_id,
            body.quantity or Decimal("1"),
            body.amount,
            body.notes or "",
        )
        await pool.execute(
            """UPDATE procurements
               SET current_amount=(SELECT COALESCE(SUM(amount),0) FROM participants WHERE procurement_id=$1 AND is_active=true),
                   updated_at=NOW()
               WHERE id=$1""",
            proc_id,
        )
        return dict(participant)
    except Exception as e:
        err = str(e)
        if "unique" in err.lower() or "duplicate" in err.lower():
            raise HTTPException(status_code=400, detail="Already joined this procurement")
        raise HTTPException(status_code=400, detail=err)


@router.post("/{proc_id}/leave/", summary="Leave procurement")
async def leave_procurement(proc_id: int, pool=Depends(get_pool)):
    return {"message": "Left procurement", "procurement_id": proc_id}
