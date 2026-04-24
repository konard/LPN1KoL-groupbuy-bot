import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.supplier.models import ClosingDocument, CompanyCard, PriceList
from app.modules.supplier.schemas import CompanyCardCreate, CompanyCardUpdate

UPLOADS_DIR = "uploads"


async def get_or_create_company_card(
    db: AsyncSession, supplier_id: uuid.UUID, req: CompanyCardCreate
) -> CompanyCard:
    existing = await db.scalar(
        select(CompanyCard).where(CompanyCard.supplier_id == supplier_id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Карта компании уже существует. Используйте PATCH для обновления.")
    card = CompanyCard(
        supplier_id=supplier_id,
        company_name=req.company_name,
        legal_address=req.legal_address,
        postal_address=req.postal_address,
        actual_address=req.actual_address,
        okved=req.okved,
        ogrn=req.ogrn,
        inn=req.inn,
        phone=req.phone,
        email=req.email,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def get_company_card(db: AsyncSession, supplier_id: uuid.UUID) -> CompanyCard | None:
    return await db.scalar(
        select(CompanyCard).where(CompanyCard.supplier_id == supplier_id)
    )


async def update_company_card(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    req: CompanyCardUpdate,
) -> CompanyCard:
    card = await db.scalar(
        select(CompanyCard).where(CompanyCard.supplier_id == supplier_id)
    )
    if not card:
        raise HTTPException(status_code=404, detail="Карта компании не найдена")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(card, field, value)
    await db.commit()
    await db.refresh(card)
    return card


async def create_price_list(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    file: UploadFile,
    popular_items: str | None,
) -> PriceList:
    import os
    os.makedirs(f"{UPLOADS_DIR}/pricelists", exist_ok=True)
    file_path = f"{UPLOADS_DIR}/pricelists/{supplier_id}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Deactivate previous price lists
    result = await db.execute(
        select(PriceList).where(
            PriceList.supplier_id == supplier_id,
            PriceList.is_active.is_(True),
        )
    )
    for old in result.scalars().all():
        old.is_active = False

    price_list = PriceList(
        supplier_id=supplier_id,
        file_url=f"/{file_path}",
        file_name=file.filename or "pricelist",
        popular_items=popular_items,
    )
    db.add(price_list)
    await db.commit()
    await db.refresh(price_list)
    return price_list


async def get_active_price_list(
    db: AsyncSession, supplier_id: uuid.UUID
) -> PriceList | None:
    return await db.scalar(
        select(PriceList).where(
            PriceList.supplier_id == supplier_id,
            PriceList.is_active.is_(True),
        )
    )


async def create_closing_document(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    purchase_id: uuid.UUID,
    file: UploadFile,
    comment: str | None,
) -> ClosingDocument:
    import os
    os.makedirs(f"{UPLOADS_DIR}/documents", exist_ok=True)
    file_path = f"{UPLOADS_DIR}/documents/{purchase_id}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = ClosingDocument(
        supplier_id=supplier_id,
        purchase_id=purchase_id,
        file_url=f"/{file_path}",
        file_name=file.filename or "document",
        comment=comment,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_closing_documents(
    db: AsyncSession, purchase_id: uuid.UUID
) -> list[ClosingDocument]:
    result = await db.execute(
        select(ClosingDocument)
        .where(ClosingDocument.purchase_id == purchase_id)
        .order_by(ClosingDocument.created_at.desc())
    )
    return list(result.scalars().all())
