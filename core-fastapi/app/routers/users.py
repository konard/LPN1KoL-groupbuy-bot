"""User management endpoints — mirrors core-rust handlers/users.rs"""

import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool, get_redis
from ..schemas import (
    BalanceUpdateResponse,
    ClearSessionRequest,
    CreateUser,
    ErrorDetail,
    ExistsResponse,
    MessageResponse,
    SetSessionState,
    UpdateBalanceRequest,
    UpdateUser,
    UserBalanceResponse,
    UserResponse,
    UserRoleResponse,
    WsTokenResponse,
)
from ..config import settings

logger = logging.getLogger("core.users")
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={
        400: {"model": ErrorDetail, "description": "Bad request"},
        404: {"model": ErrorDetail, "description": "User not found"},
    },
)

WS_TOKEN_TTL_SECS = 86400


def _role_display(role: str) -> str:
    return {"buyer": "Buyer", "organizer": "Organizer", "supplier": "Supplier"}.get(role, role)


def _row_to_response(row: dict) -> dict:
    full_name = f"{row['first_name']} {row['last_name']}".strip()
    return {
        "id": row["id"],
        "platform": row["platform"],
        "platform_user_id": row["platform_user_id"],
        "username": row["username"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "full_name": full_name,
        "phone": row["phone"],
        "email": row["email"],
        "role": row["role"],
        "role_display": _role_display(row["role"]),
        "balance": row["balance"],
        "language_code": row["language_code"],
        "is_active": row["is_active"],
        "is_verified": row["is_verified"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _truncate(s: str, max_chars: int) -> str:
    return s[:max_chars] if len(s) > max_chars else s


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users",
    description=(
        "Returns every user record sorted by creation time (newest first). "
        "Used by the admin frontend and integration tests."
    ),
    response_description="Array of user records",
)
async def list_users(pool=Depends(get_pool)):
    rows = await pool.fetch("SELECT * FROM users ORDER BY created_at DESC")
    return [_row_to_response(dict(r)) for r in rows]


@router.post(
    "/",
    response_model=UserResponse,
    status_code=201,
    summary="Create or upsert a user",
    description=(
        "Idempotent upsert on (`platform`, `platform_user_id`).  Re-syncing the "
        "same platform user is safe — fields are overwritten on conflict.  When "
        "`id` is supplied (e.g. by auth-service propagating its own UUID) it is "
        "used as the primary key so later `/api/users/{id}/…` calls resolve."
    ),
    response_description="The created or updated user",
)
async def create_user(body: CreateUser, pool=Depends(get_pool)):
    if not body.platform_user_id or not body.platform_user_id.strip():
        raise HTTPException(status_code=400, detail={"platform_user_id": ["Обязательное поле."]})

    platform = _truncate(body.platform or "telegram", 20)
    role = _truncate(body.role or "buyer", 20)
    language_code = _truncate(body.language_code or "ru", 20)
    phone = _truncate(body.phone or "", 30)
    if phone and not phone.startswith("+"):
        phone = f"+{phone}"

    # Idempotent upsert: callers like auth-service may retry sync after a
    # failure, and re-registering the same user must not raise.  When an
    # explicit id is supplied (e.g. auth-service passes its own UUID), it is
    # used as the primary key so subsequent /api/users/{id}/... calls from the
    # frontend resolve to the same record.  Two conflict targets are handled:
    #   1. ON CONFLICT (id)                     — PK re-sync for the same UUID
    #   2. ON CONFLICT (platform, platform_user_id) — same platform user
    # Both update the mutable fields so the record is always up-to-date.
    # See issues #256 and #262.
    try:
        if body.id is not None:
            row = await pool.fetchrow(
                """INSERT INTO users
                   (id, platform, platform_user_id, username, first_name, last_name, phone, email, role, language_code, selfie_file_id, is_banned)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,false)
                   ON CONFLICT (id) DO UPDATE SET
                     platform=EXCLUDED.platform,
                     platform_user_id=EXCLUDED.platform_user_id,
                     username=EXCLUDED.username,
                     first_name=EXCLUDED.first_name,
                     last_name=EXCLUDED.last_name,
                     phone=EXCLUDED.phone,
                     email=EXCLUDED.email,
                     role=EXCLUDED.role,
                     language_code=EXCLUDED.language_code,
                     selfie_file_id=EXCLUDED.selfie_file_id,
                     updated_at=NOW()
                   RETURNING *""",
                body.id,
                platform,
                body.platform_user_id,
                body.username or "",
                body.first_name or "",
                body.last_name or "",
                phone,
                body.email or "",
                role,
                language_code,
                body.selfie_file_id or "",
            )
        else:
            row = await pool.fetchrow(
                """INSERT INTO users
                   (platform, platform_user_id, username, first_name, last_name, phone, email, role, language_code, selfie_file_id, is_banned)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,false)
                   ON CONFLICT (platform, platform_user_id) DO UPDATE SET
                     username=EXCLUDED.username,
                     first_name=EXCLUDED.first_name,
                     last_name=EXCLUDED.last_name,
                     phone=EXCLUDED.phone,
                     email=EXCLUDED.email,
                     role=EXCLUDED.role,
                     language_code=EXCLUDED.language_code,
                     selfie_file_id=EXCLUDED.selfie_file_id,
                     updated_at=NOW()
                   RETURNING *""",
                platform,
                body.platform_user_id,
                body.username or "",
                body.first_name or "",
                body.last_name or "",
                phone,
                body.email or "",
                role,
                language_code,
                body.selfie_file_id or "",
            )
        return _row_to_response(dict(row))
    except Exception as e:
        err = str(e)
        if "unique" in err.lower() or "duplicate" in err.lower():
            raise HTTPException(status_code=400, detail="User with this platform and platform_user_id already exists")
        raise HTTPException(status_code=400, detail=err)


@router.get(
    "/by_platform/",
    response_model=UserResponse,
    summary="Get user by platform identity",
    description="Look up a user by (`platform`, `platform_user_id`).",
)
async def get_user_by_platform(
    platform: str | None = Query(default="telegram", description="Platform name (telegram, vk, mattermost…)", examples=["telegram"]),
    platform_user_id: str | None = Query(default=None, description="Per-platform external user id", examples=["123456789"]),
    pool=Depends(get_pool),
):
    if not platform_user_id:
        raise HTTPException(status_code=400, detail="platform_user_id is required")
    row = await pool.fetchrow(
        "SELECT * FROM users WHERE platform=$1 AND platform_user_id=$2",
        platform or "telegram", platform_user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_response(dict(row))


@router.get(
    "/by_email/",
    response_model=UserResponse,
    summary="Get user by email",
    description="Case-insensitive lookup by email address.",
)
async def get_user_by_email(
    email: str | None = Query(default=None, description="Email address", examples=["user@example.com"]),
    pool=Depends(get_pool),
):
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    row = await pool.fetchrow("SELECT * FROM users WHERE LOWER(email)=LOWER($1)", email)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_response(dict(row))


@router.get(
    "/by_phone/",
    response_model=UserResponse,
    summary="Get user by phone",
    description="Lookup by phone number. A leading `+` is added automatically when missing.",
)
async def get_user_by_phone(
    phone: str | None = Query(default=None, description="Phone in E.164 format", examples=["+79991234567"]),
    pool=Depends(get_pool),
):
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    if not phone.startswith("+"):
        phone = f"+{phone}"
    row = await pool.fetchrow("SELECT * FROM users WHERE phone=$1", phone)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_response(dict(row))


@router.get(
    "/check_exists/",
    response_model=ExistsResponse,
    summary="Check if user exists",
    description="Returns `{exists: true|false}` for the given platform identity. Never 404s.",
    responses={404: {"description": "Not used by this endpoint"}},
)
async def check_user_exists(
    platform: str | None = Query(default="telegram", description="Platform name", examples=["telegram"]),
    platform_user_id: str | None = Query(default=None, description="Per-platform external user id", examples=["123456789"]),
    pool=Depends(get_pool),
):
    if not platform_user_id:
        raise HTTPException(status_code=400, detail="platform_user_id is required")
    exists = await pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM users WHERE platform=$1 AND platform_user_id=$2)",
        platform or "telegram", platform_user_id,
    )
    return {"exists": exists}


@router.get(
    "/search/",
    response_model=list[UserResponse],
    summary="Search users",
    description=(
        "Case-insensitive `LIKE` search across `first_name`, `last_name`, "
        "`username`, `email`, and `phone`.  Returns at most 20 records."
    ),
    responses={404: {"description": "Not used by this endpoint"}},
)
async def search_users(
    q: str | None = Query(default=None, description="Search query (matches any of the searchable fields)", examples=["ivan"]),
    pool=Depends(get_pool),
):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="q (search query) is required")
    pattern = f"%{q.strip().lower()}%"
    rows = await pool.fetch(
        """SELECT * FROM users
           WHERE LOWER(first_name) LIKE $1 OR LOWER(last_name) LIKE $1
              OR LOWER(username) LIKE $1 OR LOWER(email) LIKE $1 OR phone LIKE $1
           LIMIT 20""",
        pattern,
    )
    return [_row_to_response(dict(r)) for r in rows]


@router.post(
    "/sessions/set_state/",
    summary="Set session state",
    description=(
        "Upserts the bot/web dialog state for a user.  `dialog_data` is stored "
        "as JSONB so any serialisable structure is accepted."
    ),
    responses={404: {"description": "Not used by this endpoint"}},
)
async def set_session_state(body: SetSessionState, pool=Depends(get_pool)):
    import json
    dialog_data = body.dialog_data if body.dialog_data is not None else {}
    if not isinstance(dialog_data, str):
        dialog_data = json.dumps(dialog_data)
    row = await pool.fetchrow(
        """INSERT INTO user_sessions (user_id, dialog_type, dialog_state, dialog_data)
           VALUES ($1,$2,$3,$4::jsonb)
           ON CONFLICT (user_id) DO UPDATE SET
             dialog_type=EXCLUDED.dialog_type,
             dialog_state=EXCLUDED.dialog_state,
             dialog_data=EXCLUDED.dialog_data,
             updated_at=NOW()
           RETURNING *""",
        body.user_id,
        body.dialog_type or "",
        body.dialog_state or "",
        dialog_data,
    )
    return dict(row)


@router.post(
    "/sessions/clear_state/",
    response_model=MessageResponse,
    summary="Clear session state",
    description="Deletes the persisted dialog state for the supplied user. Idempotent.",
    responses={404: {"description": "Not used by this endpoint"}},
)
async def clear_session_state(body: ClearSessionRequest, pool=Depends(get_pool)):
    await pool.execute("DELETE FROM user_sessions WHERE user_id=$1", body.user_id)
    return {"message": "Session cleared"}


@router.get(
    "/{user_id}/",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Fetch a single user record by its UUID primary key.",
)
async def get_user(user_id: UUID, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_response(dict(row))


@router.put(
    "/{user_id}/",
    response_model=UserResponse,
    summary="Replace user fields",
    description=(
        "Updates the supplied fields on a user.  Unspecified fields are left "
        "untouched.  Accepts both PUT and PATCH for client convenience."
    ),
)
@router.patch(
    "/{user_id}/",
    response_model=UserResponse,
    summary="Patch user fields",
    description="Partial update — see PUT for semantics.",
)
async def update_user(user_id: UUID, body: UpdateUser, pool=Depends(get_pool)):
    updates = []
    values = [user_id]
    idx = 1

    for field, col in [("first_name", "first_name"), ("last_name", "last_name"),
                        ("phone", "phone"), ("email", "email"), ("role", "role")]:
        val = getattr(body, field)
        if val is not None:
            idx += 1
            updates.append(f"{col}=${idx}")
            values.append(val)

    if not updates:
        row = await pool.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(status_code=404, detail="Not found.")
        return _row_to_response(dict(row))

    updates.append("updated_at=NOW()")
    query = f"UPDATE users SET {', '.join(updates)} WHERE id=$1 RETURNING *"
    row = await pool.fetchrow(query, *values)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_response(dict(row))


@router.delete(
    "/{user_id}/",
    status_code=204,
    summary="Delete user",
    description="Permanently removes a user record. Returns 204 on success.",
    responses={
        204: {"description": "User deleted"},
        400: {"description": "Not used by this endpoint"},
    },
)
async def delete_user(user_id: UUID, pool=Depends(get_pool)):
    result = await pool.execute("DELETE FROM users WHERE id=$1", user_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Not found.")


@router.get(
    "/{user_id}/balance/",
    response_model=UserBalanceResponse,
    summary="Get user balance",
    description=(
        "Returns the cached `balance` column plus aggregates derived from the "
        "`transactions` table: total deposited, total spent, and currently "
        "available funds."
    ),
)
async def get_user_balance(user_id: UUID, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    deposited = await pool.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=$1 AND transaction_type='deposit'",
        user_id,
    ) or 0
    spent = await pool.fetchval(
        "SELECT COALESCE(SUM(ABS(amount)),0) FROM transactions WHERE user_id=$1 AND amount<0",
        user_id,
    ) or 0
    return {
        "balance": row["balance"],
        "total_deposited": deposited,
        "total_spent": spent,
        "available": row["balance"],
    }


@router.post(
    "/{user_id}/update_balance/",
    response_model=BalanceUpdateResponse,
    summary="Add delta to user balance",
    description=(
        "Adjusts a user's balance by the signed `amount` (may be negative).  "
        "Use the dedicated `/payments/` and `/payments/withdrawals/` endpoints "
        "for real money flows — this endpoint is intended for admin tooling."
    ),
)
async def update_user_balance(user_id: UUID, body: UpdateBalanceRequest, pool=Depends(get_pool)):
    from decimal import Decimal
    amount = Decimal(str(body.amount))
    row = await pool.fetchrow(
        "UPDATE users SET balance=balance+$2, updated_at=NOW() WHERE id=$1 RETURNING *",
        user_id, amount,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return {"balance": row["balance"], "message": "Balance updated successfully"}


@router.get(
    "/{user_id}/role/",
    response_model=UserRoleResponse,
    summary="Get user role",
    description="Returns the user's role and a human-readable display label.",
    responses={400: {"description": "Not used by this endpoint"}},
)
async def get_user_role(user_id: UUID, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT role FROM users WHERE id=$1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return {"role": row["role"], "role_display": _role_display(row["role"])}


@router.get(
    "/{user_id}/ws_token/",
    response_model=WsTokenResponse,
    summary="Issue WebSocket JWT",
    description=(
        "Returns a short-lived HS256 JWT consumed by the WebSocket gateway to "
        "authenticate the client.  Token TTL is exposed as `expires_in` (seconds)."
    ),
    responses={400: {"description": "Not used by this endpoint"}},
)
async def get_ws_token(user_id: UUID, pool=Depends(get_pool)):
    exists = await pool.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE id=$1)", user_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Not found.")

    from jose import jwt as jose_jwt
    now = int(time.time())
    payload = {"user_id": str(user_id), "iat": now, "exp": now + WS_TOKEN_TTL_SECS}
    token = jose_jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"token": token, "expires_in": WS_TOKEN_TTL_SECS}
