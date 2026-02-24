"""
Notification service consumer — listens to payment.completed and logs
a structured notification. In a real system this would send email/SMS/push.
"""

import logging

from aiokafka import AIOKafkaConsumer

from shared.events import PaymentCompletedEvent

logger = logging.getLogger(__name__)


async def run_consumer(consumer: AIOKafkaConsumer) -> None:
    """Main consumer loop — runs until cancelled."""
    async for msg in consumer:
        await _handle_message(msg)


async def _handle_message(msg) -> None:
    try:
        event = PaymentCompletedEvent.model_validate_json(msg.value)
    except Exception as exc:
        logger.error(
            "Failed to parse payment.completed message",
            extra={"error": str(exc), "offset": msg.offset, "partition": msg.partition},
        )
        return

    if event.success:
        logger.info(
            "NOTIFICATION: Order payment succeeded",
            extra={
                "order_id": str(event.order_id),
                "correlation_id": event.correlation_id,
                "attempt_count": event.attempt_count,
                "processing_time_ms": event.processing_time_ms,
            },
        )
    else:
        logger.info(
            "NOTIFICATION: Order payment failed",
            extra={
                "order_id": str(event.order_id),
                "correlation_id": event.correlation_id,
                "attempt_count": event.attempt_count,
                "error_message": event.error_message,
            },
        )
