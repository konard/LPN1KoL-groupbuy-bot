"""
Kafka producer for analytics events.
Publishes to 'analytics-raw' topic consumed by the analytics service.
"""
import logging
from datetime import datetime, timezone

from app.config import settings
from app.kafka_producer import publish

logger = logging.getLogger(__name__)

_TOPIC = settings.analytics_topic


async def emit_event(event_type: str, user_id: str, payload: dict) -> None:
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "payload": payload,
    }
    await publish(_TOPIC, event)
