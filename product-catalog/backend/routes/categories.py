from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import UserModel, UserRole
from repositories import CategoryRepository, LogRepository
from schemas import CategoryIn, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return CategoryRepository(db).list_all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    data: CategoryIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    repo = CategoryRepository(db)
    if repo.get_by_name(data.name):
        raise HTTPException(status_code=400, detail="Категория с таким именем уже существует")
    cat = repo.create(data.name)
    LogRepository(db).create(user.id, "create_category", f"name={data.name}")
    return cat


@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    data: CategoryIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    repo = CategoryRepository(db)
    existing = repo.get_by_name(data.name)
    if existing and existing.id != cat_id:
        raise HTTPException(status_code=400, detail="Категория с таким именем уже существует")
    cat = repo.update(cat_id, data.name)
    LogRepository(db).create(user.id, "update_category", f"id={cat_id} name={data.name}")
    return cat


@router.delete("/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    CategoryRepository(db).delete(cat_id)
    LogRepository(db).create(user.id, "delete_category", f"id={cat_id}")
