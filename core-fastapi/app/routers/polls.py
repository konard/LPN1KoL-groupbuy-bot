"""Polls / voting endpoints (issue #194: процессы 2.3 + 10).

Two flavours are supported via `poll_type`:

  * ``supplier_vote`` — created by an organizer to choose a supplier for a
    procurement. Options correspond to candidate suppliers (free-form text).
  * ``general``      — open polls created by any participant in a chat.

A user may cast a single vote per poll. Switching choice replaces the prior
vote. Tallies are returned together with the poll.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_pool
from ..schemas import CreatePoll, CastVote

logger = logging.getLogger("core.polls")
router = APIRouter(prefix="/polls", tags=["polls"])


async def _serialize_poll(pool, poll_row) -> dict:
    options = await pool.fetch(
        "SELECT id, text, position FROM poll_options WHERE poll_id=$1 ORDER BY position, id",
        poll_row["id"],
    )
    counts = await pool.fetch(
        "SELECT option_id, COUNT(*) AS votes FROM poll_votes WHERE poll_id=$1 GROUP BY option_id",
        poll_row["id"],
    )
    by_option = {r["option_id"]: r["votes"] for r in counts}
    total = sum(by_option.values())
    return {
        "id": poll_row["id"],
        "procurement_id": poll_row["procurement_id"],
        "author_id": poll_row["author_id"],
        "question": poll_row["question"],
        "poll_type": poll_row["poll_type"],
        "is_closed": poll_row["is_closed"],
        "created_at": poll_row["created_at"],
        "total_votes": total,
        "options": [
            {
                "id": o["id"],
                "text": o["text"],
                "position": o["position"],
                "votes": by_option.get(o["id"], 0),
            }
            for o in options
        ],
    }


@router.post("/", status_code=201, summary="Create a poll")
async def create_poll(body: CreatePoll, pool=Depends(get_pool)):
    if not body.options or len([o for o in body.options if o.strip()]) < 2:
        raise HTTPException(status_code=400, detail="At least two non-empty options are required.")

    async with pool.acquire() as conn:
        async with conn.transaction():
            poll = await conn.fetchrow(
                """INSERT INTO polls (procurement_id, author_id, question, poll_type)
                   VALUES ($1, $2, $3, $4) RETURNING *""",
                body.procurement_id,
                body.author_id,
                body.question.strip(),
                body.poll_type or "general",
            )
            for idx, opt in enumerate(body.options):
                if not opt.strip():
                    continue
                await conn.execute(
                    "INSERT INTO poll_options (poll_id, text, position) VALUES ($1, $2, $3)",
                    poll["id"], opt.strip(), idx,
                )
    return await _serialize_poll(pool, poll)


@router.get("/{poll_id}/", summary="Get a poll with tallies")
async def get_poll(poll_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow("SELECT * FROM polls WHERE id=$1", poll_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return await _serialize_poll(pool, row)


@router.post("/{poll_id}/vote/", summary="Cast or change a vote")
async def cast_vote(poll_id: int, body: CastVote, pool=Depends(get_pool)):
    poll = await pool.fetchrow("SELECT * FROM polls WHERE id=$1", poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found.")
    if poll["is_closed"]:
        raise HTTPException(status_code=400, detail="Poll is closed.")
    option = await pool.fetchrow(
        "SELECT id FROM poll_options WHERE id=$1 AND poll_id=$2", body.option_id, poll_id
    )
    if not option:
        raise HTTPException(status_code=400, detail="Option does not belong to this poll.")
    await pool.execute(
        """INSERT INTO poll_votes (poll_id, option_id, user_id)
           VALUES ($1, $2, $3)
           ON CONFLICT (poll_id, user_id) DO UPDATE
             SET option_id=EXCLUDED.option_id, created_at=NOW()""",
        poll_id, body.option_id, body.user_id,
    )
    return await _serialize_poll(pool, poll)


@router.post("/{poll_id}/close/", summary="Close a poll (no further votes accepted)")
async def close_poll(poll_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        "UPDATE polls SET is_closed=TRUE WHERE id=$1 RETURNING *", poll_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return await _serialize_poll(pool, row)


@router.get("/", summary="List polls (optionally filtered by procurement)")
async def list_polls(procurement_id: int | None = None, pool=Depends(get_pool)):
    if procurement_id is not None:
        rows = await pool.fetch(
            "SELECT * FROM polls WHERE procurement_id=$1 ORDER BY created_at DESC",
            procurement_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM polls ORDER BY created_at DESC LIMIT 100"
        )
    return {"results": [await _serialize_poll(pool, r) for r in rows]}
