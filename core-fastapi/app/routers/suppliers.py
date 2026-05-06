"""Supplier-side endpoints (issue #194: forms 3.1, 3.2, 3.3, processes 5 + 7).

Covers:
  * Company card (карта компании) — create/read/update/list.
  * Price list (прайс-лист) — upload metadata + popular items.
  * Closing documents — supplier sends them after a procurement ships.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import (
    UpsertSupplierCompany,
    UpsertPriceList,
    CreateClosingDocument,
)

logger = logging.getLogger("core.suppliers")
router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _company_to_dict(row) -> dict:
    return dict(row)


# ─── Company cards ────────────────────────────────────────────────────────────

@router.get("/companies/", summary="List published company cards")
async def list_companies(pool=Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT * FROM supplier_companies WHERE is_published=TRUE ORDER BY name"
    )
    return {"results": [_company_to_dict(r) for r in rows]}


@router.put("/companies/", summary="Create or update a supplier company card")
async def upsert_company(body: UpsertSupplierCompany, pool=Depends(get_pool)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail={"name": ["Обязательное поле."]})
    role = await pool.fetchval("SELECT role FROM users WHERE id=$1", body.user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if role != "supplier":
        raise HTTPException(status_code=403, detail="Only suppliers can register a company card.")

    row = await pool.fetchrow(
        """INSERT INTO supplier_companies
             (user_id, name, legal_address, postal_address, actual_address,
              okved, ogrn, inn, contact_phone, email, is_published)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
           ON CONFLICT (user_id) DO UPDATE SET
             name=EXCLUDED.name,
             legal_address=EXCLUDED.legal_address,
             postal_address=EXCLUDED.postal_address,
             actual_address=EXCLUDED.actual_address,
             okved=EXCLUDED.okved,
             ogrn=EXCLUDED.ogrn,
             inn=EXCLUDED.inn,
             contact_phone=EXCLUDED.contact_phone,
             email=EXCLUDED.email,
             is_published=EXCLUDED.is_published,
             updated_at=NOW()
           RETURNING *""",
        body.user_id, body.name.strip(), body.legal_address, body.postal_address,
        body.actual_address, body.okved, body.ogrn, body.inn,
        body.contact_phone, body.email, body.is_published,
    )
    return _company_to_dict(row)


@router.get("/companies/{user_id}/", summary="Get supplier company card by user id")
async def get_company(user_id: UUID, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM supplier_companies WHERE user_id=$1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _company_to_dict(row)


# ─── Price lists ──────────────────────────────────────────────────────────────

@router.put("/price_lists/", summary="Create or update a supplier price list")
async def upsert_price_list(body: UpsertPriceList, pool=Depends(get_pool)):
    role = await pool.fetchval("SELECT role FROM users WHERE id=$1", body.supplier_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    if role != "supplier":
        raise HTTPException(status_code=403, detail="Only suppliers can publish a price list.")

    items_json = json.dumps(body.popular_items or [])
    existing = await pool.fetchval(
        "SELECT id FROM supplier_price_lists WHERE supplier_id=$1", body.supplier_id
    )
    if existing is not None:
        row = await pool.fetchrow(
            """UPDATE supplier_price_lists
                 SET file_url=$2, popular_items=$3::jsonb, is_published=$4, updated_at=NOW()
               WHERE supplier_id=$1
               RETURNING *""",
            body.supplier_id, body.file_url, items_json, body.is_published,
        )
    else:
        row = await pool.fetchrow(
            """INSERT INTO supplier_price_lists
                 (supplier_id, file_url, popular_items, is_published)
               VALUES ($1, $2, $3::jsonb, $4) RETURNING *""",
            body.supplier_id, body.file_url, items_json, body.is_published,
        )
    return dict(row)


@router.get("/price_lists/{supplier_id}/", summary="Get supplier price list")
async def get_price_list(supplier_id: UUID, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT * FROM supplier_price_lists WHERE supplier_id=$1 AND is_published=TRUE",
        supplier_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return dict(row)


# ─── Closing documents ────────────────────────────────────────────────────────

@router.post("/closing_documents/", status_code=201, summary="Send closing documents to buyers")
async def create_closing_document(body: CreateClosingDocument, pool=Depends(get_pool)):
    proc = await pool.fetchrow(
        "SELECT id, supplier_id FROM procurements WHERE id=$1", body.procurement_id
    )
    if not proc:
        raise HTTPException(status_code=404, detail="Procurement not found.")
    if proc["supplier_id"] is not None and proc["supplier_id"] != body.supplier_id:
        raise HTTPException(
            status_code=403,
            detail="Only the approved supplier can send closing documents for this procurement.",
        )
    row = await pool.fetchrow(
        """INSERT INTO closing_documents (procurement_id, supplier_id, file_url, comment)
           VALUES ($1, $2, $3, $4) RETURNING *""",
        body.procurement_id, body.supplier_id, body.file_url, body.comment,
    )
    # Notify all participants that closing docs are available.
    await pool.execute(
        """INSERT INTO notifications (user_id, notification_type, title, message, procurement_id)
           SELECT pt.user_id, 'closing_documents', 'Документы по закупке', $2, $1
           FROM participants pt
           WHERE pt.procurement_id=$1 AND pt.is_active=TRUE""",
        body.procurement_id,
        body.comment or "Поставщик отправил закрывающие документы по закупке.",
    )
    return dict(row)


@router.get("/closing_documents/{procurement_id}/", summary="List closing documents for a procurement")
async def list_closing_documents(procurement_id: int, pool=Depends(get_pool)):
    rows = await pool.fetch(
        "SELECT * FROM closing_documents WHERE procurement_id=$1 ORDER BY created_at DESC",
        procurement_id,
    )
    return {"results": [dict(r) for r in rows]}


@router.get("/{supplier_id}/shipments/", summary="Supplier shipment history")
async def list_shipments(supplier_id: UUID, pool=Depends(get_pool)):
    rows = await pool.fetch(
        """SELECT id, title, status, current_amount, deadline, created_at, updated_at
           FROM procurements
           WHERE supplier_id=$1 AND status IN ('completed', 'payment')
           ORDER BY updated_at DESC""",
        supplier_id,
    )
    return {"results": [dict(r) for r in rows]}
