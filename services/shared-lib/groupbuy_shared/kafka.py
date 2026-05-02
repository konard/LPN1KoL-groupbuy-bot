import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer(brokers: str) -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",
            enable_idempotence=True,
            compression_type="gzip",
        )
        await _producer.start()
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


async def publish(brokers: str, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
    producer = await get_producer(brokers)
    key_bytes = key.encode() if key else None
    await producer.send_and_wait(topic, value=payload, key=key_bytes)
    logger.debug("Published to %s: %s", topic, payload)


def build_consumer(
    brokers: str,
    topics: list[str],
    group_id: str,
    handler: Callable[[str, dict], Awaitable[None]],
) -> asyncio.Task:
    async def _loop() -> None:
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=brokers,
            group_id=group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        retry_delay = 5
        while True:
            try:
                await consumer.start()
                logger.info("Kafka consumer started — topics: %s", topics)
                async for msg in consumer:
                    try:
                        await handler(msg.topic, msg.value)
                    except Exception as exc:
                        logger.error("Error processing %s: %s", msg.topic, exc)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Kafka consumer error: %s — retrying in %ds", exc, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            finally:
                try:
                    await consumer.stop()
                except Exception:
                    pass

    return asyncio.create_task(_loop())
