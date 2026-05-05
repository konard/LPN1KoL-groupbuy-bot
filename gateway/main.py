"""FastAPI API gateway for the GroupBuy microservices stack.

Implements the contract described in issue #178:

* Listens on `${PORT}` (default 3000).
* Routes `/api/v1/{service}/{path:path}` to the matching upstream URL
  resolved from `${SERVICE}_SERVICE_URL` env vars.
* Validates JWT in the `Authorization: Bearer <token>` header against
  `JWT_SECRET`. A short whitelist (e.g. `/api/v1/auth/login`) is exempt.
* Per-IP (or per-user-id when authenticated) rate limiting backed by
  Redis using a fixed-window counter at `${RATE_LIMIT_RPM}` rpm.
* CORS middleware fed from `CORS_ORIGINS` (comma-separated).
* `GET /health` returns a 200 for the docker healthcheck.

Frontend note (issue #178, section 3): the React frontend container
must point at the gateway, e.g. `API_BASE_URL=http://gateway:3000`,
not directly at `core:8000`.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Iterable

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt

# ─── Configuration ────────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "3000"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

REDIS_ADDR = os.getenv("REDIS_ADDR", "redis:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_URL = os.getenv(
    "REDIS_URL",
    f"redis://{':' + REDIS_PASSWORD + '@' if REDIS_PASSWORD else ''}{REDIS_ADDR}/0",
)

SERVICE_URLS: dict[str, str] = {
    "auth":          os.getenv("AUTH_SERVICE_URL",          "http://auth-service:4001"),
    "purchases":     os.getenv("PURCHASE_SERVICE_URL",      "http://purchase-service:4002"),
    "payments":      os.getenv("PAYMENT_SERVICE_URL",       "http://payment-service:4003"),
    "chat":          os.getenv("CHAT_SERVICE_URL",          "http://chat-service:4004"),
    "notifications": os.getenv("NOTIFICATION_SERVICE_URL",  "http://notification-service:4005"),
    "analytics":     os.getenv("ANALYTICS_SERVICE_URL",     "http://analytics-service:4006"),
    "search":        os.getenv("SEARCH_SERVICE_URL",        "http://search-service:4007"),
    "reputation":    os.getenv("REPUTATION_SERVICE_URL",    "http://reputation-service:4008"),
}

# Paths under /api/v1 that bypass the JWT requirement.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "auth/login",
        "auth/register",
        "auth/refresh",
        "auth/forgot-password",
        "auth/reset-password",
    }
)

# Headers that must not be forwarded to upstream services or back to the client.
HOP_BY_HOP_HEADERS: frozenset[str] = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("gateway")


# ─── Lifespan: shared httpx client + Redis client ────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
    try:
        app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await app.state.redis.ping()
        logger.info("Redis ready at %s", REDIS_ADDR)
    except Exception as exc:  # pragma: no cover - logged and degrades gracefully
        logger.warning("Redis unavailable (%s); rate limiting will fail-open", exc)
        app.state.redis = None

    logger.info("Gateway listening on :%d", PORT)
    try:
        yield
    finally:
        await app.state.http.aclose()
        if app.state.redis is not None:
            await app.state.redis.aclose()


app = FastAPI(title="GroupBuy Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def _filter_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {k: v for k, v in headers if k.lower() not in HOP_BY_HOP_HEADERS}


async def _enforce_rate_limit(redis: aioredis.Redis | None, identity: str) -> None:
    """Fixed-window-per-minute counter. Fails open if Redis is unavailable."""
    if redis is None:
        return
    key = f"ratelimit:{identity}"
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Redis INCR failed (%s); skipping rate limit for %s", exc, identity)
        return
    if current > RATE_LIMIT_RPM:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}


@app.api_route(
    "/api/v1/{service_name}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(service_name: str, path: str, request: Request) -> Response:
    base_url = SERVICE_URLS.get(service_name)
    if base_url is None:
        raise HTTPException(status_code=404, detail=f"Unknown service '{service_name}'")

    # Authentication: required unless the path is in PUBLIC_PATHS.
    is_public = f"{service_name}/{path}".rstrip("/") in PUBLIC_PATHS
    claims: dict | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        claims = _decode_jwt(auth_header.split(" ", 1)[1].strip())

    if not is_public and claims is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Rate limit: prefer userId from token, fall back to client IP.
    identity = (
        f"user:{claims.get('sub')}"
        if claims and claims.get("sub")
        else f"ip:{request.client.host if request.client else 'unknown'}"
    )
    await _enforce_rate_limit(request.app.state.redis, identity)

    # Build upstream request.
    target_url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    forwarded = _filter_headers(request.headers.items())
    if claims:
        forwarded["x-user-id"] = str(claims.get("sub", ""))
        forwarded["x-user-role"] = str(claims.get("role", "user"))

    body = await request.body()

    try:
        upstream = await request.app.state.http.request(
            method=request.method,
            url=target_url,
            headers=forwarded,
            content=body,
        )
    except httpx.RequestError as exc:
        logger.error("Upstream %s unreachable: %s", target_url, exc)
        raise HTTPException(status_code=502, detail="Upstream service unavailable") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_filter_headers(upstream.headers.items()),
        media_type=upstream.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level=LOG_LEVEL.lower())
