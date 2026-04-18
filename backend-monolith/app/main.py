from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.kafka_producer import stop_producer
from app.modules.auth.router import router as auth_router
from app.modules.payment.router import escrow_router, router as wallet_router
from app.modules.purchase.router import router as purchase_router
from app.modules.reputation.router import router as reputation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await stop_producer()


app = FastAPI(title="GroupBuy Backend Monolith", version="1.0.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(purchase_router)
app.include_router(wallet_router)
app.include_router(escrow_router)
app.include_router(reputation_router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/ready")
async def ready():
    return JSONResponse({"status": "ready"})
