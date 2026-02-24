"""
Pydantic event schemas shared across all services.
All events extend EventBase which carries correlation/tracing metadata.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_version: int = 1
    correlation_id: str  # carries X-Request-ID from the HTTP layer
    occurred_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "ignore"}


class OrderItemEvent(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = {"extra": "ignore"}


class OrderPlacedEvent(EventBase):
    order_id: uuid.UUID
    customer_name: str
    customer_email: str
    total_amount: Decimal
    items: list[OrderItemEvent]


class PaymentCompletedEvent(EventBase):
    order_id: uuid.UUID
    success: bool
    final_status: str  # "completed" | "failed"
    attempt_count: int
    processing_time_ms: int
    error_message: str | None = None
