import logging

from elasticsearch import AsyncElasticsearch, NotFoundError

from app.config import settings

logger = logging.getLogger(__name__)

_es: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch | None:
    global _es
    if _es is None and settings.elasticsearch_url:
        _es = AsyncElasticsearch(settings.elasticsearch_url)
    return _es


async def close_es() -> None:
    global _es
    if _es is not None:
        await _es.close()
        _es = None


async def search_purchases(q: str, page: int = 1, per_page: int = 20) -> dict:
    es = get_es_client()
    if es is None:
        return {"total": 0, "items": []}

    per_page = min(per_page, 100)
    from_ = (page - 1) * per_page

    body = {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["title^2", "description"],
                "fuzziness": "AUTO",
                "max_expansions": 50,
            }
        },
        "highlight": {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {"title": {}, "description": {}},
        },
        "from": from_,
        "size": per_page,
    }

    try:
        resp = await es.search(index=settings.elasticsearch_index, body=body)
    except NotFoundError:
        logger.warning("Elasticsearch index '%s' not found", settings.elasticsearch_index)
        return {"total": 0, "items": []}
    except Exception:
        logger.exception("Elasticsearch search failed")
        return {"total": 0, "items": []}

    hits = resp["hits"]
    total = hits["total"]["value"] if isinstance(hits["total"], dict) else hits["total"]
    items = []
    for hit in hits["hits"]:
        src = hit.get("_source", {})
        highlights = {}
        for field, frags in (hit.get("highlight") or {}).items():
            highlights[field] = frags[0] if frags else ""
        items.append(
            {
                "id": hit["_id"],
                "score": hit.get("_score") or 0.0,
                "title": src.get("title", ""),
                "description": src.get("description", ""),
                "status": src.get("status", ""),
                "highlights": highlights,
            }
        )

    return {"total": total, "items": items}


async def index_purchase(purchase_id: str, doc: dict) -> None:
    es = get_es_client()
    if es is None:
        return
    try:
        await es.index(index=settings.elasticsearch_index, id=purchase_id, body=doc)
    except Exception:
        logger.exception("Failed to index purchase %s", purchase_id)
