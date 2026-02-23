import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr

from app.models.order import OrderStatus
from app.models.payment import PaymentStatus


class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int


class OrderCreate(BaseModel):
    customer_name: str
    customer_email: EmailStr
    items: list[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    menu_item_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class PaymentAttemptResponse(BaseModel):
    id: uuid.UUID
    status: PaymentStatus
    attempt_count: int
    error_message: str | None
    processing_time_ms: int | None
    created_at: datetime


class OrderResponse(BaseModel):
    id: uuid.UUID
    customer_name: str
    customer_email: str
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]
    payment_attempts: list[PaymentAttemptResponse]
    payment_successful: bool
