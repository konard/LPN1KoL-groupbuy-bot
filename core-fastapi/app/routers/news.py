"""News feed endpoints (issue #194: form 2.2 / 3.4 — "Лента новостей").

News posts are authored by organizers and suppliers and shown in the public
news feed. Only the author or an admin may edit/delete a post.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_pool
from ..schemas import CreateNewsPost, UpdateNewsPost

logger = logging.getLogger("core.news")
router = APIRouter(prefix="/news", tags=["news"])

ALLOWED_AUTHOR_ROLES = {"organizer", "supplier", "admin"}


def _row_to_dict(row) -> dict:
    return dict(row)


@router.get("/", summary="List news posts")
async def list_news(
    author_id: UUID | None = Query(default=None),
    pool=Depends(get_pool),
):
    if author_id is not None:
        rows = await pool.fetch(
            "SELECT * FROM news_posts WHERE is_deleted=FALSE AND author_id=$1 ORDER BY created_at DESC LIMIT 100",
            author_id,
        )
    else:
        rows = await pool.fetch(
            "SELECT * FROM news_posts WHERE is_deleted=FALSE ORDER BY created_at DESC LIMIT 100"
        )
    return {"results": [_row_to_dict(r) for r in rows]}


@router.post("/", status_code=201, summary="Create news post")
async def create_news(body: CreateNewsPost, pool=Depends(get_pool)):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail={"title": ["Обязательное поле."]})
    role = await pool.fetchval("SELECT role FROM users WHERE id=$1", body.author_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Author not found.")
    if role not in ALLOWED_AUTHOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Only organizers and suppliers may publish news.",
        )
    row = await pool.fetchrow(
        """INSERT INTO news_posts (author_id, title, content)
           VALUES ($1, $2, $3) RETURNING *""",
        body.author_id, body.title.strip(), body.content,
    )
    return _row_to_dict(row)


@router.get("/{post_id}/", summary="Get a news post")
async def get_news_post(post_id: int, pool=Depends(get_pool)):
    row = await pool.fetchrow(
        "SELECT * FROM news_posts WHERE id=$1 AND is_deleted=FALSE", post_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_dict(row)


@router.patch("/{post_id}/", summary="Update a news post")
async def update_news_post(post_id: int, body: UpdateNewsPost, pool=Depends(get_pool)):
    updates: list[str] = []
    values: list = [post_id]
    for field in ("title", "content"):
        val = getattr(body, field)
        if val is not None:
            values.append(val)
            updates.append(f"{field}=${len(values)}")
    if not updates:
        return await get_news_post(post_id, pool)
    updates.append("updated_at=NOW()")
    row = await pool.fetchrow(
        f"UPDATE news_posts SET {', '.join(updates)} WHERE id=$1 AND is_deleted=FALSE RETURNING *",
        *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _row_to_dict(row)


@router.delete("/{post_id}/", status_code=204, summary="Delete a news post (soft)")
async def delete_news_post(post_id: int, pool=Depends(get_pool)):
    result = await pool.execute(
        "UPDATE news_posts SET is_deleted=TRUE, updated_at=NOW() WHERE id=$1 AND is_deleted=FALSE",
        post_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Not found.")
