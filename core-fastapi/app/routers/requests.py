"""Buyer request endpoints (issue #194: form 1.1 "Создать запрос").

A buyer request expresses interest in a product the buyer wants to find. It is
distinct from a procurement (which is owned by an organizer) and is shown in
the vertical chat feed for organizers and other buyers to discover.
"""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateBuyerRequest, UpdateBuyerRequest

logger = logging.getLogger("core.requests")
router = APIRouter(prefix="/requests", tags=["requests"])


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("/", summary="List buyer requests")
async def list_requests(
    user_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    pool=Depends(get_pool),
):
    clauses = []
    args: list = []
    if active_only:
        clauses.append("is_active=TRUE")
    if user_id is not None:
        args.append(user_id)
        clauses.append(f"user_id=${len(args)}")
    if q and q.strip():
        args.append(f"%{q.strip().lower()}%")
        clauses.append(f"LOWER(product_name) LIKE ${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = await pool.fetch(
        f"SELECT * FROM buyer_requests {where} ORDER BY created_at DESC LIMIT 200",
        *args,
    )
    return {"results": [_row_to_dict(r) for r in rows]}


@router.post("/", status_code=201, summary="Create buyer request")
async def create_request(body: CreateBuyerRequest, pool=Depends(get_pool)):
    if not body.product_name or not body.product_name.strip():
        raise HTTPException(status_code=400, detail={"product_name": ["Обязательное поле."]})
    row = await pool.fetchrow(
        """INSERT INTO buyer_requests
             (user_id, product_name, quantity, unit, city, notes)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING *""",
        body.user_id,
        body.product_name.strip(),
        body.quantity if body.quantity is not None else Decimal("1"),
        body.unit or "units",
        body.city or "",
        body.notes or "",
    )
    return _row_to_dict(row)


@router.get("/{request_id}/", summary="Get a buyer request")
async def get_request(request_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM buyer_requests WHERE id=$1", request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_dict(row)


@router.patch("/{request_id}/", summary="Update a buyer request")
async def update_request(request_id: int, body: UpdateBuyerRequest, pool=Depends(get_pool)):
    updates: list[str] = []
    values: list = [request_id]
    for field in ("product_name", "quantity", "unit", "city", "notes", "is_active"):
        val = getattr(body, field)
        if val is not None:
            values.append(val)
            updates.append(f"{field}=${len(values)}")
    if not updates:
        return await get_request(request_id, pool)
    updates.append("updated_at=NOW()")
    row = await pool.fetchrow(
        f"UPDATE buyer_requests SET {', '.join(updates)} WHERE id=$1 RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_dict(row)


@router.delete("/{request_id}/", status_code=204, summary="Delete a buyer request")
async def delete_request(request_id: int, pool=Depends(get_pool)):
    result = await pool.execute("DELETE FROM buyer_requests WHERE id=$1", request_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Not found.")


@router.get("/search/", summary="Search buyer requests by product name")
async def search_requests(q: str = Query(...), pool=Depends(get_pool)):
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    rows = await pool.fetch(
        """SELECT * FROM buyer_requests
           WHERE is_active=TRUE AND LOWER(product_name) LIKE $1
           ORDER BY created_at DESC LIMIT 50""",
        f"%{q.strip().lower()}%",
    )
    return {"results": [_row_to_dict(r) for r in rows]}
