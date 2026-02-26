"""
At-least-once Kafka consumer for the payment service.

Guarantees:
  - Idempotency: skips messages if a PaymentAttempt already exists for the order_id
  - At-least-once delivery: offset committed only after DB write + downstream publish
  - DLQ: unparseable / fatally broken messages are forwarded to payment.dlq
"""

import logging
import uuid
from datetime import datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from payment_service.config import settings
from payment_service.database import AsyncSessionLocal
from payment_service.metrics import MESSAGES_CONSUMED, PAYMENT_OUTCOMES, PROCESSING_TIME
from payment_service.models import Order, OrderStatus, PaymentAttempt, PaymentStatus
from payment_service.payment_processor import process_payment
from shared.events import OrderPlacedEvent, PaymentCompletedEvent

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def run_consumer(consumer: AIOKafkaConsumer, producer: AIOKafkaProducer) -> None:
    """Main consumer loop — runs until cancelled."""
    async for msg in consumer:
        await _handle_message(msg, consumer, producer)


async def _handle_message(msg, consumer: AIOKafkaConsumer, producer: AIOKafkaProducer) -> None:
    # Extract W3C trace context propagated via Kafka headers
    headers = {k: v.decode() for k, v in msg.headers} if msg.headers else {}
    ctx = extract(headers)

    with tracer.start_as_current_span("kafka.consume.order.placed", context=ctx):
        try:
            event = OrderPlacedEvent.model_validate_json(msg.value)
        except Exception as exc:
            logger.error(
                "Failed to parse order.placed message — sending to DLQ",
                extra={"error": str(exc), "offset": msg.offset, "partition": msg.partition},
            )
            await producer.send_and_wait("payment.dlq", value=msg.value)
            MESSAGES_CONSUMED.labels("dlq").inc()
            await consumer.commit()
            return

        order_id = event.order_id
        correlation_id = event.correlation_id

        logger.info(
            "Received order.placed event",
            extra={"order_id": str(order_id), "correlation_id": correlation_id},
        )

        async with AsyncSessionLocal() as db:
            # --- Idempotency check ---
            existing = await db.execute(
                select(PaymentAttempt).where(PaymentAttempt.order_id == order_id)
            )
            if existing.scalars().first() is not None:
                logger.info(
                    "PaymentAttempt already exists — skipping (idempotency)",
                    extra={"order_id": str(order_id), "correlation_id": correlation_id},
                )
                MESSAGES_CONSUMED.labels("skipped").inc()
                await consumer.commit()
                return

            # --- Process payment ---
            try:
                result = await process_payment(
                    order_id=order_id,
                    amount=float(event.total_amount),
                    request_id=correlation_id,
                )
            except Exception as exc:
                logger.error(
                    "Unexpected error during payment processing — sending to DLQ",
                    extra={"order_id": str(order_id), "error": str(exc)},
                )
                await producer.send_and_wait("payment.dlq", value=msg.value)
                MESSAGES_CONSUMED.labels("dlq").inc()
                await consumer.commit()
                return

            # --- Persist PaymentAttempt + update Order status atomically ---
            order_result = await db.execute(select(Order).where(Order.id == order_id))
            order = order_result.scalars().first()
            if order is not None:
                order.status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
                order.updated_at = datetime.utcnow()

            pa = PaymentAttempt(
                order_id=order_id,
                status=PaymentStatus.SUCCESS if result.success else PaymentStatus.FAILED,
                amount=event.total_amount,
                attempt_count=result.attempt_count,
                error_message=result.error_message,
                processing_time_ms=result.processing_time_ms,
            )
            db.add(pa)

            await db.commit()  # atomic: both Order.status and PaymentAttempt written together

            # Record metrics
            PROCESSING_TIME.observe(result.processing_time_ms / 1000)
            if result.success:
                PAYMENT_OUTCOMES.labels("success").inc()
            elif result.error_message and "circuit breaker" in (result.error_message or "").lower():
                PAYMENT_OUTCOMES.labels("circuit_open").inc()
            elif result.error_message and "declined" in (result.error_message or "").lower():
                PAYMENT_OUTCOMES.labels("declined").inc()
            else:
                PAYMENT_OUTCOMES.labels("failed").inc()
            MESSAGES_CONSUMED.labels("processed").inc()

            logger.info(
                "Order payment finalised",
                extra={
                    "order_id": str(order_id),
                    "correlation_id": correlation_id,
                    "success": result.success,
                    "attempt_count": result.attempt_count,
                    "processing_time_ms": result.processing_time_ms,
                },
            )

        # --- Publish payment.completed ---
        final_status = "completed" if result.success else "failed"
        completed_event = PaymentCompletedEvent(
            correlation_id=correlation_id,
            order_id=order_id,
            success=result.success,
            final_status=final_status,
            attempt_count=result.attempt_count,
            processing_time_ms=result.processing_time_ms,
            error_message=result.error_message,
        )

        # Propagate trace context into the downstream Kafka message
        outgoing_headers: dict[str, str] = {}
        inject(outgoing_headers)
        kafka_headers = [(k, v.encode()) for k, v in outgoing_headers.items()]

        await producer.send_and_wait(
            "payment.completed",
            key=str(order_id).encode(),
            value=completed_event.model_dump_json().encode(),
            headers=kafka_headers,
        )

        logger.info(
            "Published payment.completed event",
            extra={"order_id": str(order_id), "correlation_id": correlation_id},
        )

        # --- Commit offset only after successful DB write + publish ---
        await consumer.commit()
