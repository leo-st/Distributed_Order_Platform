"""
Payment Service entry point.
Starts AIOKafka consumer + producer, then runs the consumer loop.
"""

import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from payment_service.config import settings
from payment_service.consumer import run_consumer
from payment_service.utils.logging import setup_logging

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def main() -> None:
    consumer = AIOKafkaConsumer(
        "order.placed",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        enable_idempotence=True,
    )

    await producer.start()
    await consumer.start()
    logger.info(
        "Payment service started",
        extra={
            "bootstrap_servers": settings.kafka_bootstrap_servers,
            "consumer_group": settings.kafka_consumer_group,
        },
    )

    try:
        await run_consumer(consumer, producer)
    finally:
        await consumer.stop()
        await producer.stop()
        logger.info("Payment service stopped")


if __name__ == "__main__":
    asyncio.run(main())
