"""Procurement endpoints — mirrors core-rust handlers/procurements.rs"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateProcurement, JoinProcurement, ApproveSupplier

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


@router.post("/{proc_id}/check_access/", summary="Check if user has access to procurement chat")
async def check_access(proc_id: int, body: dict, pool=Depends(get_pool)):
    user_id = (body or {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        user_uuid = UUID(str(user_id))
    except Exception:
        raise HTTPException(status_code=400, detail="user_id must be a valid UUID")
    row = await pool.fetchrow(
        "SELECT organizer_id FROM procurements WHERE id=$1", proc_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    is_participant = await pool.fetchval(
        """SELECT EXISTS(
               SELECT 1 FROM participants
                WHERE procurement_id=$1 AND user_id=$2 AND is_active=TRUE
           )""",
        proc_id, user_uuid,
    )
    if row["organizer_id"] == user_uuid or is_participant:
        return {"access": True}
    raise HTTPException(
        status_code=403, detail={"access": False, "error": "No access to this procurement"}
    )


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
async def leave_procurement(proc_id: int, body: dict | None = None, pool=Depends(get_pool)):
    user_id = (body or {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        user_uuid = UUID(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="user_id must be a valid UUID")
    result = await pool.execute(
        """UPDATE participants SET is_active=FALSE, updated_at=NOW()
           WHERE procurement_id=$1 AND user_id=$2 AND is_active=TRUE""",
        proc_id, user_uuid,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Not a participant of this procurement.")
    await pool.execute(
        """UPDATE procurements
              SET current_amount=(SELECT COALESCE(SUM(amount),0) FROM participants WHERE procurement_id=$1 AND is_active=TRUE),
                  updated_at=NOW()
            WHERE id=$1""",
        proc_id,
    )
    return {"message": "Left procurement", "procurement_id": proc_id}


@router.post("/{proc_id}/stop_amount/", summary="Stop-sum: freeze procurement and notify participants")
async def stop_amount(proc_id: int, pool=Depends(get_pool)):
    """Implements the «Стоп-сумма» button: marks the procurement as `stopped`
    and sends a confirmation request notification to every active participant.
    """
    row = await pool.fetchrow(
        """UPDATE procurements
              SET status='stopped',
                  stop_at_amount=COALESCE(stop_at_amount, current_amount),
                  updated_at=NOW()
            WHERE id=$1 AND status='active'
            RETURNING *""",
        proc_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Active procurement not found.")
    await pool.execute(
        """INSERT INTO notifications (user_id, notification_type, title, message, procurement_id)
           SELECT pt.user_id,
                  'confirm_participation',
                  'Подтвердите участие',
                  'Закупка остановлена. Подтвердите участие, чтобы перейти в закрытый чат.',
                  $1
           FROM participants pt WHERE pt.procurement_id=$1 AND pt.is_active=TRUE""",
        proc_id,
    )
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=TRUE", proc_id
    ) or 0
    return _to_response(dict(row), count)


@router.post("/{proc_id}/confirm/", summary="Buyer confirms participation after stop-sum")
async def confirm_participation(proc_id: int, body: dict, pool=Depends(get_pool)):
    user_id = (body or {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        user_uuid = UUID(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="user_id must be a valid UUID")
    result = await pool.execute(
        """UPDATE participants SET status='confirmed', updated_at=NOW()
           WHERE procurement_id=$1 AND user_id=$2 AND is_active=TRUE""",
        proc_id, user_uuid,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Not a participant of this procurement.")
    return {"message": "Participation confirmed", "procurement_id": proc_id}


@router.post("/{proc_id}/approve_supplier/", summary="Approve a supplier for a procurement")
async def approve_supplier(proc_id: int, body: ApproveSupplier, pool=Depends(get_pool)):
    role = await pool.fetchval("SELECT role FROM users WHERE id=$1", body.supplier_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    if role != "supplier":
        raise HTTPException(status_code=400, detail="User is not a supplier.")
    row = await pool.fetchrow(
        """UPDATE procurements
              SET supplier_id=$2, status='payment', updated_at=NOW()
            WHERE id=$1 AND status IN ('active','stopped')
            RETURNING *""",
        proc_id, body.supplier_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Procurement not found or not approvable.")
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=TRUE", proc_id
    ) or 0
    return _to_response(dict(row), count)


@router.post("/{proc_id}/close/", summary="Close a procurement (organizer)")
async def close_procurement(proc_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        """UPDATE procurements SET status='completed', updated_at=NOW()
            WHERE id=$1 AND status NOT IN ('completed','cancelled')
            RETURNING *""",
        proc_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Procurement not found or already closed.")
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=TRUE", proc_id
    ) or 0
    return _to_response(dict(row), count)


@router.get("/{proc_id}/receipt_summary/", summary="Receipt summary table sent to the supplier")
async def receipt_summary(proc_id: int, pool=Depends(get_pool)):
    """Implements the «Создать и отправить таблицу чеков» button: returns the
    rolled-up table with each confirmed participant's name, address, quantity
    and amount, plus the procurement totals."""
    proc = await pool.fetchrow(
        """SELECT id, title, organizer_id, supplier_id, current_amount, commission_percent,
                  delivery_address, city
             FROM procurements WHERE id=$1""",
        proc_id,
    )
    if not proc:
        raise HTTPException(status_code=404, detail="Procurement not found.")
    rows = await pool.fetch(
        """SELECT u.id              AS user_id,
                  TRIM(u.first_name || ' ' || u.last_name) AS full_name,
                  u.username        AS username,
                  u.email           AS email,
                  u.phone           AS phone,
                  pt.quantity       AS quantity,
                  pt.amount         AS amount,
                  pt.status         AS status,
                  pt.notes          AS notes
             FROM participants pt
             JOIN users u ON u.id = pt.user_id
            WHERE pt.procurement_id=$1 AND pt.is_active=TRUE
            ORDER BY u.last_name, u.first_name""",
        proc_id,
    )
    total = sum((r["amount"] or Decimal("0")) for r in rows)
    commission = (total * (proc["commission_percent"] or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"))
    return {
        "procurement_id": proc["id"],
        "title": proc["title"],
        "city": proc["city"],
        "delivery_address": proc["delivery_address"],
        "organizer_id": proc["organizer_id"],
        "supplier_id": proc["supplier_id"],
        "total_amount": total,
        "commission_percent": proc["commission_percent"],
        "commission_amount": commission,
        "rows": [dict(r) for r in rows],
    }


@router.get("/history/", summary="Completed procurement history")
async def procurement_history(
    user_id: UUID | None = Query(default=None),
    role: str | None = Query(default=None),
    pool=Depends(get_pool),
):
    """Returns finished procurements. If ``user_id`` is supplied, results are
    scoped to that user — as organizer, participant, or supplier depending on
    the optional ``role`` filter ("organizer", "participant", "supplier")."""
    base = "SELECT DISTINCT p.* FROM procurements p"
    where = ["p.status IN ('completed','cancelled')"]
    args: list = []
    if user_id is not None:
        if role == "organizer":
            args.append(user_id)
            where.append(f"p.organizer_id=${len(args)}")
        elif role == "supplier":
            args.append(user_id)
            where.append(f"p.supplier_id=${len(args)}")
        elif role == "participant":
            base += " JOIN participants pt ON pt.procurement_id=p.id AND pt.is_active=TRUE"
            args.append(user_id)
            where.append(f"pt.user_id=${len(args)}")
        else:
            base += " LEFT JOIN participants pt ON pt.procurement_id=p.id AND pt.is_active=TRUE"
            args.append(user_id)
            where.append(
                f"(p.organizer_id=${len(args)} OR p.supplier_id=${len(args)} OR pt.user_id=${len(args)})"
            )
    sql = f"{base} WHERE {' AND '.join(where)} ORDER BY p.updated_at DESC LIMIT 200"
    rows = await pool.fetch(sql, *args)
    results = []
    for row in rows:
        count = await pool.fetchval(
            "SELECT COUNT(*) FROM participants WHERE procurement_id=$1 AND is_active=TRUE",
            row["id"],
        ) or 0
        results.append(_to_response(dict(row), count))
    return {"results": results}
