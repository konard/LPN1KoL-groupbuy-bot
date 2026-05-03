from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import CategoryModel, ParticipantModel, ProcurementModel
from app.services.auth_service import admin_user, current_user

router = APIRouter(tags=["procurements"])


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    icon: str = ""


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str
    parent_id: Optional[int]
    icon: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProcurementCreate(BaseModel):
    title: str
    description: str = ""
    category_id: Optional[int] = None
    city: str = ""
    delivery_address: str = ""
    target_amount: float
    stop_at_amount: Optional[float] = None
    unit: str = "units"
    price_per_unit: Optional[float] = None
    commission_percent: float = 0.0
    deadline: datetime
    image_url: str = ""
    is_featured: bool = False


class ProcurementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    city: Optional[str] = None
    delivery_address: Optional[str] = None
    target_amount: Optional[float] = None
    stop_at_amount: Optional[float] = None
    unit: Optional[str] = None
    price_per_unit: Optional[float] = None
    commission_percent: Optional[float] = None
    deadline: Optional[datetime] = None
    image_url: Optional[str] = None
    is_featured: Optional[bool] = None


class ProcurementOut(BaseModel):
    id: int
    title: str
    description: str
    category_id: Optional[int]
    organizer_id: int
    organizer_username: str
    city: str
    delivery_address: str
    target_amount: float
    current_amount: float
    stop_at_amount: Optional[float]
    unit: str
    price_per_unit: Optional[float]
    commission_percent: float
    status: str
    deadline: datetime
    image_url: str
    is_featured: bool
    participant_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParticipantCreate(BaseModel):
    quantity: float = 1.0


class ParticipantOut(BaseModel):
    id: int
    procurement_id: int
    user_id: int
    username: str
    quantity: float
    amount: float
    status: str
    is_active: bool
    joined_at: datetime

    class Config:
        from_attributes = True


def _proc_out(p: ProcurementModel) -> dict:
    return {
        "id": p.id, "title": p.title, "description": p.description or "",
        "category_id": p.category_id, "organizer_id": p.organizer_id,
        "organizer_username": p.organizer.username if p.organizer else "",
        "city": p.city or "", "delivery_address": p.delivery_address or "",
        "target_amount": float(p.target_amount),
        "current_amount": float(p.current_amount or 0),
        "stop_at_amount": float(p.stop_at_amount) if p.stop_at_amount else None,
        "unit": p.unit or "units",
        "price_per_unit": float(p.price_per_unit) if p.price_per_unit else None,
        "commission_percent": float(p.commission_percent or 0),
        "status": p.status, "deadline": p.deadline,
        "image_url": p.image_url or "", "is_featured": p.is_featured,
        "participant_count": len([pt for pt in p.participants if pt.is_active]),
        "created_at": p.created_at, "updated_at": p.updated_at,
    }


def _part_out(pt: ParticipantModel) -> dict:
    return {
        "id": pt.id, "procurement_id": pt.procurement_id, "user_id": pt.user_id,
        "username": pt.user.username if pt.user else "",
        "quantity": float(pt.quantity or 1), "amount": float(pt.amount or 0),
        "status": pt.status, "is_active": pt.is_active, "joined_at": pt.joined_at,
    }


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(CategoryModel).filter(CategoryModel.is_active == True).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = CategoryModel(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = db.query(CategoryModel).filter(CategoryModel.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    db.commit()


@router.get("/procurements", response_model=list[ProcurementOut])
def list_procurements(
    status: Optional[str] = None,
    city: Optional[str] = None,
    category_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(ProcurementModel)
    if status:
        q = q.filter(ProcurementModel.status == status)
    if city:
        q = q.filter(ProcurementModel.city.ilike(f"%{city}%"))
    if category_id:
        q = q.filter(ProcurementModel.category_id == category_id)
    return [_proc_out(p) for p in q.order_by(ProcurementModel.created_at.desc()).offset(skip).limit(limit).all()]


@router.post("/procurements", response_model=ProcurementOut, status_code=201)
def create_procurement(data: ProcurementCreate, db: Session = Depends(get_db), user=Depends(current_user)):
    p = ProcurementModel(organizer_id=user.id, **data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _proc_out(p)


@router.get("/procurements/{proc_id}", response_model=ProcurementOut)
def get_procurement(proc_id: int, db: Session = Depends(get_db)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    return _proc_out(p)


@router.patch("/procurements/{proc_id}", response_model=ProcurementOut)
def update_procurement(proc_id: int, data: ProcurementUpdate, db: Session = Depends(get_db), user=Depends(current_user)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return _proc_out(p)


@router.delete("/procurements/{proc_id}", status_code=204)
def delete_procurement(proc_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.organizer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not the organizer")
    db.delete(p)
    db.commit()


@router.get("/procurements/{proc_id}/participants", response_model=list[ParticipantOut])
def list_participants(proc_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return [_part_out(pt) for pt in
            db.query(ParticipantModel).filter(ParticipantModel.procurement_id == proc_id).all()]


@router.post("/procurements/{proc_id}/join", response_model=ParticipantOut, status_code=201)
def join_procurement(proc_id: int, data: ParticipantCreate, db: Session = Depends(get_db), user=Depends(current_user)):
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procurement not found")
    if p.status != "active":
        raise HTTPException(status_code=400, detail="Procurement is not active")
    existing = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already joined")
    amount = float(data.quantity) * float(p.price_per_unit or 0)
    pt = ParticipantModel(procurement_id=proc_id, user_id=user.id, quantity=data.quantity, amount=amount)
    db.add(pt)
    p.current_amount = float(p.current_amount) + amount
    if p.stop_at_amount and float(p.current_amount) >= float(p.stop_at_amount):
        p.status = "stopped"
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pt)
    return _part_out(pt)


@router.delete("/procurements/{proc_id}/leave", status_code=204)
def leave_procurement(proc_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    pt = db.query(ParticipantModel).filter(
        ParticipantModel.procurement_id == proc_id,
        ParticipantModel.user_id == user.id,
        ParticipantModel.is_active == True,
    ).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Not a participant")
    p = db.query(ProcurementModel).filter(ProcurementModel.id == proc_id).first()
    if p:
        p.current_amount = max(0, float(p.current_amount) - float(pt.amount))
        p.updated_at = datetime.now(timezone.utc)
    pt.is_active = False
    pt.status = "cancelled"
    db.commit()
