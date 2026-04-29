from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import UserModel, UserRole
from repositories import CategoryRepository, LogRepository, ProductRepository
from schemas import ProductIn, ProductUpdate
from services import build_product_out, has_special_access

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    products = ProductRepository(db).list_all(search=search, category_id=category_id, skip=skip, limit=limit)
    include_special = has_special_access(user.role)
    return [build_product_out(p, include_special) for p in products]


@router.post("", status_code=201)
def create_product(
    data: ProductIn,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.simple_user, UserRole.advanced_user, UserRole.admin)),
):
    cat = CategoryRepository(db).get(data.category_id)
    if not cat:
        raise HTTPException(status_code=400, detail="Категория не найдена")
    product = ProductRepository(db).create(data.model_dump())
    LogRepository(db).create(user.id, "create_product", f"name={data.name}")
    return build_product_out(product, include_special=True)


@router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    product = ProductRepository(db).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return build_product_out(product, has_special_access(user.role))


@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.simple_user, UserRole.advanced_user, UserRole.admin)),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if "category_id" in updates:
        cat = CategoryRepository(db).get(updates["category_id"])
        if not cat:
            raise HTTPException(status_code=400, detail="Категория не найдена")
    product = ProductRepository(db).update(product_id, updates)
    LogRepository(db).create(user.id, "update_product", f"id={product_id}")
    return build_product_out(product, has_special_access(user.role))


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_role(UserRole.advanced_user, UserRole.admin)),
):
    ProductRepository(db).delete(product_id)
    LogRepository(db).create(user.id, "delete_product", f"id={product_id}")
