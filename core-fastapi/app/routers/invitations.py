"""Invitation endpoints (issue #194: process 9, "Приглашение поставщика/покупателя").

The organizer creates an invitation (by email or by user id) optionally tied to
a procurement. The invitee can list their inbound invitations and update the
status (accepted / declined). When an invitation is accepted and a procurement
is attached, the invitee is auto-registered as a participant (for buyers) or
recorded as the candidate supplier (for suppliers).
"""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateInvitation, UpdateInvitationStatus

logger = logging.getLogger("core.invitations")
router = APIRouter(prefix="/invitations", tags=["invitations"])

VALID_STATUSES = {"pending", "accepted", "declined", "cancelled"}


def _row_to_dict(row) -> dict:
    return dict(row)


@router.post("/", status_code=201, summary="Create an invitation")
async def create_invitation(body: CreateInvitation, pool=Depends(get_pool)):
    if body.invitee_id is None and not body.invitee_email.strip():
        raise HTTPException(
            status_code=400,
            detail="Either invitee_id or invitee_email is required.",
        )
    organizer_role = await pool.fetchval(
        "SELECT role FROM users WHERE id=$1", body.organizer_id
    )
    if organizer_role is None:
        raise HTTPException(status_code=404, detail="Organizer not found.")
    if organizer_role not in ("organizer", "admin"):
        raise HTTPException(
            status_code=403, detail="Only organizers can send invitations."
        )

    row = await pool.fetchrow(
        """INSERT INTO invitations
             (organizer_id, invitee_id, invitee_email, invitee_role, procurement_id, message)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
        body.organizer_id,
        body.invitee_id,
        (body.invitee_email or "").strip().lower(),
        body.invitee_role,
        body.procurement_id,
        body.message,
    )

    # Create an in-app notification when we know the invitee user.
    if body.invitee_id is not None:
        await pool.execute(
            """INSERT INTO notifications (user_id, notification_type, title, message, procurement_id)
               VALUES ($1, 'invitation', 'Приглашение в закупку', $2, $3)""",
            body.invitee_id,
            body.message or "Вас пригласили принять участие.",
            body.procurement_id,
        )
    return _row_to_dict(row)


@router.get("/", summary="List invitations for an invitee")
async def list_invitations(
    invitee_id: UUID | None = Query(default=None),
    organizer_id: UUID | None = Query(default=None),
    email: str | None = Query(default=None),
    status: str | None = Query(default=None),
    pool=Depends(get_pool),
):
    clauses: list[str] = []
    args: list = []
    if invitee_id is not None:
        args.append(invitee_id)
        clauses.append(f"invitee_id=${len(args)}")
    if organizer_id is not None:
        args.append(organizer_id)
        clauses.append(f"organizer_id=${len(args)}")
    if email:
        args.append(email.strip().lower())
        clauses.append(f"LOWER(invitee_email)=${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status=${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = await pool.fetch(
        f"SELECT * FROM invitations {where} ORDER BY created_at DESC LIMIT 200",
        *args,
    )
    return {"results": [_row_to_dict(r) for r in rows]}


@router.patch("/{invitation_id}/", summary="Update invitation status")
async def update_invitation(
    invitation_id: int,
    body: UpdateInvitationStatus,
    pool=Depends(get_pool),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )
    row = await pool.fetchrow(
        "UPDATE invitations SET status=$2, updated_at=NOW() WHERE id=$1 RETURNING *",
        invitation_id, body.status,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")

    # Side-effect: when an invitation is accepted and a procurement is attached
    # auto-register the invitee. This wires the form 1.2 ("Форма добавления в
    # закупку") through the invitations channel.
    if body.status == "accepted" and row["procurement_id"] and row["invitee_id"]:
        if row["invitee_role"] == "buyer":
            try:
                await pool.execute(
                    """INSERT INTO participants (procurement_id, user_id, quantity, amount)
                       VALUES ($1, $2, $3, 0)
                       ON CONFLICT (procurement_id, user_id) DO NOTHING""",
                    row["procurement_id"], row["invitee_id"], Decimal("1"),
                )
            except Exception as exc:  # pragma: no cover — best-effort side effect
                logger.warning("Failed to auto-register participant: %s", exc)
    return _row_to_dict(row)


@router.delete("/{invitation_id}/", status_code=204, summary="Cancel an invitation")
async def cancel_invitation(invitation_id: int, pool=Depends(get_pool)):
    result = await pool.execute(
        "UPDATE invitations SET status='cancelled', updated_at=NOW() WHERE id=$1 AND status='pending'",
        invitation_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Not found or not cancellable.")
