import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/search", tags=["search"])

_redis: aioredis.Redis | None = None
_es = None
_ES_AVAILABLE = False

try:
    from elasticsearch import AsyncElasticsearch
    _ES_AVAILABLE = True
except ImportError:
    pass

INDEX_NAME = "purchases"


async def get_search_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_search_es():
    return _es


async def init_search() -> None:
    global _redis, _es
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    if settings.elasticsearch_url and _ES_AVAILABLE:
        _es = AsyncElasticsearch(settings.elasticsearch_url)
        try:
            if not await _es.indices.exists(index=INDEX_NAME):
                await _es.indices.create(index=INDEX_NAME, body={
                    "mappings": {
                        "properties": {
                            "title": {"type": "text", "analyzer": "russian"},
                            "description": {"type": "text", "analyzer": "russian"},
                            "category": {"type": "keyword"},
                            "status": {"type": "keyword"},
                            "organizer_id": {"type": "keyword"},
                            "created_at": {"type": "date"},
                        }
                    }
                })
        except Exception:
            pass


async def close_search() -> None:
    global _redis, _es
    if _redis:
        await _redis.aclose()
        _redis = None
    if _es:
        await _es.close()
        _es = None


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


class SearchRequest(BaseModel):
    query: str
    category: str | None = None
    status: str | None = None
    page: int = 1
    pageSize: int = 20


class SavedFilterRequest(BaseModel):
    name: str
    filter: dict


@router.post("", summary="Search purchases")
async def search(
    body: SearchRequest,
    user_id: str = Depends(_get_user_id),
    redis: aioredis.Redis = Depends(get_search_redis),
):
    start_ms = datetime.now(timezone.utc).timestamp() * 1000
    results = []
    total = 0

    if _es:
        must = [{"multi_match": {"query": body.query, "fields": ["title^2", "description"]}}]
        filters = []
        if body.category:
            filters.append({"term": {"category": body.category}})
        if body.status:
            filters.append({"term": {"status": body.status}})
        es_query = {"bool": {"must": must, "filter": filters}} if filters else {"bool": {"must": must}}
        from_ = (body.page - 1) * body.pageSize
        try:
            resp = await _es.search(index=INDEX_NAME, body={"query": es_query, "from": from_, "size": body.pageSize})
            total = resp["hits"]["total"]["value"]
            results = [hit["_source"] | {"id": hit["_id"], "score": hit["_score"]} for hit in resp["hits"]["hits"]]
        except Exception:
            pass

    latency_ms = int(datetime.now(timezone.utc).timestamp() * 1000 - start_ms)
    history_entry = json.dumps({
        "query": body.query, "resultsCount": total,
        "latencyMs": latency_ms, "ts": datetime.now(timezone.utc).isoformat(),
    })
    await redis.lpush(f"search:history:{user_id}", history_entry)
    await redis.ltrim(f"search:history:{user_id}", 0, 49)
    await redis.publish("search.events", json.dumps({
        "topic": "search.query", "userId": user_id,
        "query": body.query, "latencyMs": latency_ms,
    }))
    return {"success": True, "data": results, "total": total, "page": body.page, "pageSize": body.pageSize}


@router.post("/index", summary="Index a document for search")
async def index_document(doc: dict):
    if not _es:
        raise HTTPException(status_code=503, detail="Elasticsearch not available")
    doc_id = doc.pop("id", str(uuid.uuid4()))
    await _es.index(index=INDEX_NAME, id=doc_id, body=doc)
    return {"success": True, "id": doc_id}


@router.get("/filters", summary="Get saved search filters")
async def get_saved_filters(
    user_id: str = Depends(_get_user_id),
    redis: aioredis.Redis = Depends(get_search_redis),
):
    raw = await redis.get(f"search:filters:{user_id}")
    return {"success": True, "data": json.loads(raw) if raw else []}


@router.post("/filters", status_code=201, summary="Save a search filter")
async def create_saved_filter(
    body: SavedFilterRequest,
    user_id: str = Depends(_get_user_id),
    redis: aioredis.Redis = Depends(get_search_redis),
):
    key = f"search:filters:{user_id}"
    raw = await redis.get(key)
    filters = json.loads(raw) if raw else []
    new_filter = {
        "id": str(uuid.uuid4()), "name": body.name, "filter": body.filter,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    filters.append(new_filter)
    await redis.set(key, json.dumps(filters))
    return {"success": True, "data": new_filter}


@router.delete("/filters/{filter_id}", summary="Delete a saved search filter")
async def delete_saved_filter(
    filter_id: str,
    user_id: str = Depends(_get_user_id),
    redis: aioredis.Redis = Depends(get_search_redis),
):
    key = f"search:filters:{user_id}"
    raw = await redis.get(key)
    filters = json.loads(raw) if raw else []
    filters = [f for f in filters if f["id"] != filter_id]
    await redis.set(key, json.dumps(filters))
    return {"success": True}


@router.get("/history", summary="Get recent search history")
async def get_search_history(
    user_id: str = Depends(_get_user_id),
    redis: aioredis.Redis = Depends(get_search_redis),
):
    items = await redis.lrange(f"search:history:{user_id}", 0, 49)
    return {"success": True, "data": [json.loads(i) for i in items]}
