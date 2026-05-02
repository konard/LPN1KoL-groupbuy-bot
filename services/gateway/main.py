import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gateway")

PORT = int(os.getenv("PORT", "3000"))
JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_ALGORITHM = "HS256"
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
VOTING_RATE_LIMIT_RPM = int(os.getenv("VOTING_RATE_LIMIT_RPM", "120"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

SERVICE_URLS = {
    "auth":         os.getenv("AUTH_SERVICE_URL", "http://auth-service:4001"),
    "purchases":    os.getenv("PURCHASE_SERVICE_URL", "http://purchase-service:4002"),
    "payments":     os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:4003"),
    "chat":         os.getenv("CHAT_SERVICE_URL", "http://chat-service:4004"),
    "notifications": os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:4005"),
    "analytics":    os.getenv("ANALYTICS_SERVICE_URL", "http://analytics-service:4006"),
    "search":       os.getenv("SEARCH_SERVICE_URL", "http://search-service:4007"),
    "reputation":   os.getenv("REPUTATION_SERVICE_URL", "http://reputation-service:4008"),
}

# ─── Rate Limiter (token-bucket per IP) ──────────────────────────────────────

class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float):
        self.tokens = capacity
        self.last_refill = time.monotonic()

_buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(RATE_LIMIT_RPM))
_voting_buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(VOTING_RATE_LIMIT_RPM))


def _check_rate_limit(ip: str, is_voting: bool = False) -> bool:
    capacity = VOTING_RATE_LIMIT_RPM if is_voting else RATE_LIMIT_RPM
    bucket = _voting_buckets[ip] if is_voting else _buckets[ip]
    now = time.monotonic()
    elapsed = now - bucket.last_refill
    bucket.tokens = min(capacity, bucket.tokens + elapsed * (capacity / 60.0))
    bucket.last_refill = now
    if bucket.tokens >= 1:
        bucket.tokens -= 1
        return True
    return False


# ─── HTTP client pool ─────────────────────────────────────────────────────────

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    logger.info("Gateway started on :%d", PORT)
    yield
    await _http_client.aclose()
    logger.info("Gateway stopped")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="GroupBuy Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer(auto_error=False)


def _verify_jwt(credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    if not credentials:
        return None
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# Public paths that do NOT require authentication
_PUBLIC_PREFIXES = {
    "/health",
    "/auth/login",
    "/auth/register",
    "/auth/refresh",
    "/auth/forgot-password",
    "/auth/reset-password",
}


def _resolve_service(path: str) -> tuple[str, str] | None:
    """Return (base_url, upstream_path) or None if no service matches."""
    parts = path.lstrip("/").split("/", 1)
    prefix = parts[0]
    if prefix in SERVICE_URLS:
        return SERVICE_URLS[prefix], path
    # /api prefix stripping
    if prefix == "api" and len(parts) > 1:
        sub = parts[1].split("/", 1)
        svc = sub[0]
        if svc in SERVICE_URLS:
            return SERVICE_URLS[svc], "/" + (sub[1] if len(sub) > 1 else "")
    return None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(
    full_path: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    path = "/" + full_path
    ip = request.client.host if request.client else "unknown"

    is_voting = "/vote" in path and "purchases" in path
    if not _check_rate_limit(ip, is_voting=is_voting):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    is_public = any(path.startswith(p) for p in _PUBLIC_PREFIXES)
    claims = _verify_jwt(credentials)
    if not is_public and claims is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    resolved = _resolve_service(path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Service not found")

    base_url, upstream_path = resolved
    target_url = base_url + upstream_path
    if request.url.query:
        target_url += "?" + request.url.query

    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    if claims:
        headers["X-User-Id"] = str(claims.get("sub", ""))
        headers["X-User-Role"] = str(claims.get("role", "user"))

    try:
        upstream_response = await _http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
    except httpx.RequestError as exc:
        logger.error("Upstream request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Upstream service unavailable")

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=dict(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
