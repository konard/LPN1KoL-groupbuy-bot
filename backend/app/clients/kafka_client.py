"""
Kafka producer для публикации событий (из shared-lib).
Producer инициализируется при старте приложения (lifespan).
"""
import json
import logging
from typing import Optional

from app.config import KAFKA_BROKERS, KAFKA_CLIENT_ID

logger = logging.getLogger(__name__)

# Глобальный producer; None если Kafka недоступна
_producer = None


def get_producer():
    """Возвращает глобальный экземпляр Kafka producer."""
    return _producer


async def init_kafka() -> None:
    """Инициализирует Kafka producer при старте приложения."""
    global _producer
    try:
        from aiokafka import AIOKafkaProducer
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKERS,
            client_id=KAFKA_CLIENT_ID,
            acks="all",
            enable_idempotence=True,
            compression_type="gzip",
        )
        await _producer.start()
        logger.info("Kafka producer запущен: %s", KAFKA_BROKERS)
    except Exception as exc:
        logger.warning("Kafka недоступна при старте: %s. События не будут публиковаться.", exc)
        _producer = None


async def close_kafka() -> None:
    """Останавливает Kafka producer при завершении приложения."""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer остановлен")


async def publish(topic: str, payload: dict, key: Optional[str] = None) -> bool:
    """
    Публикует событие в Kafka-топик.
    Возвращает True при успехе, False если Kafka недоступна.
    """
    if not _producer:
        logger.debug("Kafka недоступна, пропускаем публикацию в '%s'", topic)
        return False
    try:
        key_bytes = key.encode() if key else None
        await _producer.send_and_wait(
            topic,
            value=json.dumps(payload, default=str).encode(),
            key=key_bytes,
        )
        return True
    except Exception as exc:
        logger.error("Ошибка публикации в '%s': %s", topic, exc)
        return False
