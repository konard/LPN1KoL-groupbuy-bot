import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.payment import schemas, service

router = APIRouter(prefix="/wallets", tags=["Кошелёк"])
escrow_router = APIRouter(prefix="/escrow", tags=["Эскроу"])


@router.get(
    "/me",
    response_model=schemas.WalletOut,
    summary="Получить кошелёк",
    description="Возвращает данные кошелька текущего пользователя: баланс и заблокированную сумму.",
)
async def my_wallet(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить кошелёк текущего пользователя."""
    return await service.get_or_create_wallet(db, current_user.id)


@router.post(
    "/me/deposit",
    response_model=schemas.WalletOut,
    summary="Пополнить баланс",
    description=(
        "Позволяет покупателю пополнить баланс кошелька. "
        "После заполнения формы происходит перенаправление на страницу оплаты через API банка. "
        "Поля: сумма пополнения, способ оплаты."
    ),
    responses={422: {"description": "Ошибка валидации данных"}},
)
async def deposit(
    req: schemas.DepositRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пополнить баланс кошелька."""
    return await service.deposit(db, current_user.id, req.amount)


@router.post(
    "/me/withdraw",
    response_model=schemas.WalletOut,
    summary="Вывести средства",
    description=(
        "Позволяет покупателю вывести средства с баланса кошелька на указанный счёт. "
        "Поля: сумма вывода, реквизиты счёта. "
        "Средства списываются немедленно, перевод осуществляется через платёжную систему."
    ),
    responses={
        400: {"description": "Недостаточно средств для вывода"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def withdraw(
    req: schemas.WithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Вывести средства с баланса кошелька."""
    return await service.withdraw(db, current_user.id, req.amount, req.account_details)


@router.post(
    "/me/hold",
    response_model=schemas.WalletOut,
    summary="Заблокировать средства",
    description="Блокирует (резервирует) указанную сумму на балансе для участия в закупке.",
    responses={
        400: {"description": "Недостаточно средств для блокировки"},
        422: {"description": "Ошибка валидации данных"},
    },
)
async def hold(
    req: schemas.HoldRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Заблокировать средства на балансе."""
    return await service.hold(db, current_user.id, req.amount)


@escrow_router.post(
    "",
    response_model=schemas.EscrowOut,
    status_code=201,
    summary="Создать эскроу",
    description="Создаёт счёт эскроу для закупки — резервирует средства покупателя до завершения сделки.",
    responses={422: {"description": "Ошибка валидации данных"}},
)
async def create_escrow(
    req: schemas.EscrowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать эскроу для закупки."""
    return await service.create_escrow(db, current_user.id, req.purchase_id, req.amount)


@escrow_router.post(
    "/{escrow_id}/release",
    response_model=schemas.EscrowOut,
    summary="Освободить эскроу",
    description="Освобождает средства из эскроу после завершения закупки и получения товара.",
    responses={404: {"description": "Эскроу не найден"}},
)
async def release_escrow(
    escrow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Освободить эскроу."""
    return await service.release_escrow(db, escrow_id)
