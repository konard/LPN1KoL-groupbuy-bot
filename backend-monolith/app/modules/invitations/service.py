import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invitations.models import Invitation
from app.modules.invitations.schemas import InviteBuyerRequest, InviteSupplierRequest


async def invite_supplier(
    db: AsyncSession, req: InviteSupplierRequest, sender_id: uuid.UUID
) -> Invitation:
    invitation = Invitation(
        sender_id=sender_id,
        recipient_email=req.email,
        purchase_id=req.purchase_id,
        invitation_type="supplier",
        message=req.message,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def invite_buyer(
    db: AsyncSession, req: InviteBuyerRequest, sender_id: uuid.UUID
) -> Invitation:
    invitation = Invitation(
        sender_id=sender_id,
        purchase_id=req.purchase_id,
        invitation_type="buyer",
        message=req.message,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def list_my_invitations(
    db: AsyncSession, recipient_id: uuid.UUID
) -> list[Invitation]:
    result = await db.execute(
        select(Invitation)
        .where(Invitation.recipient_id == recipient_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


async def list_sent_invitations(
    db: AsyncSession, sender_id: uuid.UUID
) -> list[Invitation]:
    result = await db.execute(
        select(Invitation)
        .where(Invitation.sender_id == sender_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())
