import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from elasticsearch import AsyncElasticsearch
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("search-service")

PORT = int(os.getenv("PORT", "4007"))
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()] or ["*"]
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

INDEX_NAME = "purchases"

_redis: aioredis.Redis | None = None
_es: "AsyncElasticsearch | None" = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis, _es
    _redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    if ELASTICSEARCH_URL and ES_AVAILABLE:
        _es = AsyncElasticsearch(ELASTICSEARCH_URL)
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
                logger.info("Created ES index: %s", INDEX_NAME)
        except Exception as exc:
            logger.warning("ES index setup failed: %s", exc)
    else:
        logger.warning("Elasticsearch not configured — search will use Redis fallback")

    logger.info("Search service started on :%d", PORT)
    yield

    await _redis.aclose()
    if _es:
        await _es.close()
    logger.info("Search service stopped")


app = FastAPI(title="Search Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_redis() -> aioredis.Redis:
    return _redis


def _user_id(x_user_id: Optional[str] = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    category: str | None = None
    status: str | None = None
    page: int = 1
    pageSize: int = 20


class SavedFilterRequest(BaseModel):
    name: str
    filter: dict


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "search-service", "elasticsearch": _es is not None}


@app.post("/search")
async def search(
    body: SearchRequest,
    user_id: str = Depends(_user_id),
    redis: aioredis.Redis = Depends(get_redis),
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
        except Exception as exc:
            logger.error("ES search error: %s", exc)

    latency_ms = int(datetime.now(timezone.utc).timestamp() * 1000 - start_ms)

    # Save to search history
    history_key = f"search:history:{user_id}"
    history_entry = json.dumps({
        "query": body.query, "resultsCount": total,
        "latencyMs": latency_ms, "ts": datetime.now(timezone.utc).isoformat(),
    })
    await redis.lpush(history_key, history_entry)
    await redis.ltrim(history_key, 0, 49)  # keep last 50

    # Publish search event to Redis pub/sub (for analytics)
    await redis.publish("search.events", json.dumps({
        "topic": "search.query", "userId": user_id,
        "query": body.query, "latencyMs": latency_ms,
    }))

    return {"success": True, "data": results, "total": total, "page": body.page, "pageSize": body.pageSize}


@app.post("/search/index")
async def index_document(doc: dict):
    if not _es:
        raise HTTPException(status_code=503, detail="Elasticsearch not available")
    doc_id = doc.pop("id", str(uuid.uuid4()))
    await _es.index(index=INDEX_NAME, id=doc_id, body=doc)
    return {"success": True, "id": doc_id}


@app.get("/filters")
async def get_saved_filters(user_id: str = Depends(_user_id), redis: aioredis.Redis = Depends(get_redis)):
    key = f"search:filters:{user_id}"
    raw = await redis.get(key)
    filters = json.loads(raw) if raw else []
    return {"success": True, "data": filters}


@app.post("/filters", status_code=201)
async def create_saved_filter(
    body: SavedFilterRequest,
    user_id: str = Depends(_user_id),
    redis: aioredis.Redis = Depends(get_redis),
):
    key = f"search:filters:{user_id}"
    raw = await redis.get(key)
    filters = json.loads(raw) if raw else []
    new_filter = {"id": str(uuid.uuid4()), "name": body.name, "filter": body.filter,
                  "createdAt": datetime.now(timezone.utc).isoformat()}
    filters.append(new_filter)
    await redis.set(key, json.dumps(filters))
    return {"success": True, "data": new_filter}


@app.delete("/filters/{filter_id}")
async def delete_saved_filter(
    filter_id: str,
    user_id: str = Depends(_user_id),
    redis: aioredis.Redis = Depends(get_redis),
):
    key = f"search:filters:{user_id}"
    raw = await redis.get(key)
    filters = json.loads(raw) if raw else []
    filters = [f for f in filters if f["id"] != filter_id]
    await redis.set(key, json.dumps(filters))
    return {"success": True}


@app.get("/history")
async def get_search_history(user_id: str = Depends(_user_id), redis: aioredis.Redis = Depends(get_redis)):
    key = f"search:history:{user_id}"
    items = await redis.lrange(key, 0, 49)
    return {"success": True, "data": [json.loads(i) for i in items]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
