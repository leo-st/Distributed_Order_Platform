"""
Notification Service entry point.
Starts AIOKafka consumer and runs the consumer loop.
"""

import asyncio
import logging

import prometheus_client
from aiokafka import AIOKafkaConsumer

from notification_service.config import settings
from notification_service.consumer import run_consumer
from notification_service.utils.logging import setup_logging
from shared.tracing import setup_tracing

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

prometheus_client.start_http_server(settings.metrics_port)
setup_tracing("notification-service", settings.otlp_endpoint)


async def main() -> None:
    consumer = AIOKafkaConsumer(
        "payment.completed",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )

    await consumer.start()
    logger.info(
        "Notification service started",
        extra={
            "bootstrap_servers": settings.kafka_bootstrap_servers,
            "consumer_group": settings.kafka_consumer_group,
            "metrics_port": settings.metrics_port,
        },
    )

    try:
        await run_consumer(consumer)
    finally:
        await consumer.stop()
        logger.info("Notification service stopped")


if __name__ == "__main__":
    asyncio.run(main())
