import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.purchase import schemas, service

router = APIRouter(prefix="/purchases", tags=["purchases"])
categories_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


# ── Category endpoints ────────────────────────────────────────────────────────


@categories_router.get("", response_model=list[schemas.CategoryOut])
async def list_categories(
    parent_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List categories. Pass parent_id to get children of a category."""
    return await service.list_categories(db, parent_id=parent_id)


@categories_router.post("", response_model=schemas.CategoryOut, status_code=201)
async def create_category(
    req: schemas.CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Create a new category."""
    return await service.create_category(db, req)


@categories_router.get("/{category_id}", response_model=schemas.CategoryOut)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single category by ID."""
    cat = await service.get_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


# ── Purchase / Procurement endpoints ─────────────────────────────────────────


@router.post("", response_model=schemas.PurchaseOut, status_code=201)
async def create_purchase(
    req: schemas.PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new group purchase / procurement."""
    return await service.create_purchase(db, req, current_user.id)


@router.get("", response_model=list[schemas.PurchaseOut])
async def list_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    city: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    organizer_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List purchases with optional filters."""
    return await service.list_purchases(
        db,
        skip=skip,
        limit=limit,
        status=status,
        city=city,
        category_id=category_id,
        organizer_id=organizer_id,
        active_only=active_only,
    )


@router.get("/{purchase_id}", response_model=schemas.PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single purchase by ID."""
    p = await service.get_purchase(db, purchase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return p


@router.post("/{purchase_id}/update_status", response_model=schemas.PurchaseOut)
async def update_status(
    purchase_id: uuid.UUID,
    req: schemas.PurchaseStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the status of a purchase (organizer only)."""
    return await service.update_status(db, purchase_id, req.status, current_user.id)


@router.post("/{purchase_id}/close", response_model=schemas.PurchaseOut)
async def close_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a purchase as completed (organizer only)."""
    return await service.close_purchase(db, purchase_id, current_user.id)


@router.post("/{purchase_id}/approve_supplier", response_model=schemas.PurchaseOut)
async def approve_supplier(
    purchase_id: uuid.UUID,
    req: schemas.ApproveSupplierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a supplier and move purchase to payment stage (organizer only)."""
    return await service.approve_supplier(db, purchase_id, req.supplier_id, current_user.id)


@router.post("/{purchase_id}/stop_amount", response_model=schemas.PurchaseOut)
async def stop_amount(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger stop-amount: mark purchase as stopped (organizer only)."""
    return await service.stop_amount(db, purchase_id, current_user.id)


@router.get("/{purchase_id}/receipt_table")
async def receipt_table(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a receipt table (participant list with amounts) for supplier export."""
    return await service.get_receipt_table(db, purchase_id)


# ── Participant endpoints ─────────────────────────────────────────────────────


@router.get("/{purchase_id}/participants", response_model=list[schemas.ParticipantOut])
async def list_participants(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List active participants of a purchase."""
    return await service.list_participants(db, purchase_id)


@router.post("/{purchase_id}/join", response_model=schemas.ParticipantOut, status_code=201)
async def join_purchase(
    purchase_id: uuid.UUID,
    req: schemas.JoinPurchaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Join a purchase as a participant."""
    return await service.join_purchase(db, purchase_id, current_user.id, req)


@router.post("/{purchase_id}/leave")
async def leave_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leave (cancel participation in) a purchase."""
    return await service.leave_purchase(db, purchase_id, current_user.id)


# ── Vote endpoints ────────────────────────────────────────────────────────────


@router.post("/{purchase_id}/vote", response_model=schemas.VoteOut, status_code=201)
async def vote(
    purchase_id: uuid.UUID,
    req: schemas.VoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cast a vote (e.g., for a supplier candidate)."""
    return await service.cast_vote(db, purchase_id, current_user.id, req)


@router.get("/{purchase_id}/vote_results", response_model=list[schemas.VoteResultOut])
async def vote_results(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get aggregated vote results for a purchase."""
    return await service.get_vote_results(db, purchase_id)
