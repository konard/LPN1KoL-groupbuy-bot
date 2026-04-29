import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user
from config import NBRB_API_URL
from logging_setup import logger
from schemas import UsdConversion

router = APIRouter(tags=["currency"])


@router.get("/convert-usd", response_model=UsdConversion)
async def convert_usd(
    amount: float = Query(..., description="Amount in BYN rubles"),
    _=Depends(get_current_user),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(NBRB_API_URL)
            resp.raise_for_status()
            data = resp.json()
            rate = data["Cur_OfficialRate"] / data["Cur_Scale"]
    except Exception as e:
        logger.error("NBRB API error: %s", e)
        raise HTTPException(status_code=502, detail="Не удалось получить курс валюты от НБРБ")
    price_usd = amount / rate
    return UsdConversion(price_rub=amount, price_usd=round(price_usd, 4), rate=round(rate, 4))
