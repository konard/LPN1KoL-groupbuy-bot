"""
Бизнес-логика поиска закупок: full-text search, сохранённые фильтры, история.
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Максимальное число записей в истории поиска на пользователя
SEARCH_HISTORY_LIMIT = 50


async def search_purchases(query: str, category: Optional[str] = None,
                            status: Optional[str] = None, page: int = 1,
                            size: int = 20) -> Dict[str, Any]:
    """
    Ищет закупки через Elasticsearch.
    При недоступности ES возвращает пустой результат.
    """
    from app.config import ELASTICSEARCH_URL
    if not ELASTICSEARCH_URL:
        logger.debug("Elasticsearch не настроен, поиск недоступен")
        return {"total": 0, "page": page, "size": size, "items": []}

    try:
        from elasticsearch import AsyncElasticsearch
        es = AsyncElasticsearch(ELASTICSEARCH_URL)
        body: Dict[str, Any] = {
            "from": (page - 1) * size,
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {"multi_match": {
                            "query": query,
                            "fields": ["title^2", "description"],
                            "analyzer": "russian",
                        }}
                    ],
                    "filter": [],
                }
            },
        }
        if category:
            body["query"]["bool"]["filter"].append({"term": {"category": category}})
        if status:
            body["query"]["bool"]["filter"].append({"term": {"status": status}})

        result = await es.search(index="purchases", body=body)
        await es.close()

        hits = result["hits"]["hits"]
        return {
            "total": result["hits"]["total"]["value"],
            "page": page,
            "size": size,
            "items": [h["_source"] for h in hits],
        }
    except Exception as exc:
        logger.error("Elasticsearch ошибка: %s", exc)
        return {"total": 0, "page": page, "size": size, "items": []}


async def save_filter(user_id: int, name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Сохраняет фильтр поиска в Redis."""
    from app.clients.redis_client import get_redis
    redis = get_redis()
    if not redis:
        return {"id": str(uuid.uuid4()), "name": name, "filters": filters}

    filter_id = str(uuid.uuid4())
    key = f"search:filters:{user_id}"
    data = {"id": filter_id, "name": name, "filters": filters}
    await redis.hset(key, filter_id, json.dumps(data))
    return data


async def get_filters(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает все сохранённые фильтры пользователя."""
    from app.clients.redis_client import get_redis
    redis = get_redis()
    if not redis:
        return []
    key = f"search:filters:{user_id}"
    raw = await redis.hgetall(key)
    return [json.loads(v) for v in raw.values()]


async def delete_filter(user_id: int, filter_id: str) -> None:
    """Удаляет сохранённый фильтр."""
    from app.clients.redis_client import get_redis
    redis = get_redis()
    if redis:
        await redis.hdel(f"search:filters:{user_id}", filter_id)


async def add_to_history(user_id: int, query: str) -> None:
    """Добавляет запрос в историю поиска пользователя (Redis list, max 50 записей)."""
    from app.clients.redis_client import get_redis
    redis = get_redis()
    if not redis:
        return
    key = f"search:history:{user_id}"
    await redis.lpush(key, query)
    await redis.ltrim(key, 0, SEARCH_HISTORY_LIMIT - 1)


async def get_history(user_id: int) -> List[str]:
    """Возвращает историю поисковых запросов пользователя."""
    from app.clients.redis_client import get_redis
    redis = get_redis()
    if not redis:
        return []
    return await redis.lrange(f"search:history:{user_id}", 0, SEARCH_HISTORY_LIMIT - 1)
