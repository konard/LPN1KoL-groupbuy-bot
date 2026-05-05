"""CRUD example router for the `products` resource."""

import json

from fastapi import APIRouter, HTTPException, status

from ..db import get_pool, get_redis
from ..schemas import Product, ProductCreate, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

_CACHE_TTL_SECONDS = 30


def _row_to_product(row) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price_cents=row["price_cents"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[Product])
async def list_products() -> list[Product]:
    redis = get_redis()
    cached = await redis.get("products:list")
    if cached:
        return [Product.model_validate(item) for item in json.loads(cached)]

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, description, price_cents, created_at FROM products ORDER BY id"
        )
    products = [_row_to_product(r) for r in rows]
    await redis.set(
        "products:list",
        json.dumps([p.model_dump(mode="json") for p in products]),
        ex=_CACHE_TTL_SECONDS,
    )
    return products


@router.post("", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate) -> Product:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (name, description, price_cents)
            VALUES ($1, $2, $3)
            RETURNING id, name, description, price_cents, created_at
            """,
            payload.name,
            payload.description,
            payload.price_cents,
        )
    await get_redis().delete("products:list")
    return _row_to_product(row)


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int) -> Product:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description, price_cents, created_at FROM products WHERE id = $1",
            product_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _row_to_product(row)


@router.patch("/{product_id}", response_model=Product)
async def update_product(product_id: int, payload: ProductUpdate) -> Product:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(updates))
    values = list(updates.values())

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE products SET {set_clause}
            WHERE id = $1
            RETURNING id, name, description, price_cents, created_at
            """,
            product_id,
            *values,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await get_redis().delete("products:list")
    return _row_to_product(row)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Product not found")
    await get_redis().delete("products:list")
