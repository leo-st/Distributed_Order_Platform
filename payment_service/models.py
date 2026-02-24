"""
Re-declares only the ORM models that payment_service needs to read/write.
Table names must match those created by the API service (app/).
payment_service never calls create_all — table ownership stays with app.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from payment_service.database import Base


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="orderstatus"), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(
        "PaymentAttempt", back_populates="order"
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="paymentstatus"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="payment_attempts")
