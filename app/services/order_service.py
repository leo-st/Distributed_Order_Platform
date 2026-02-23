import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import PaymentAttempt, PaymentStatus
from app.schemas.order import (
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
    PaymentAttemptResponse,
)
from app.services import payment_service

logger = logging.getLogger(__name__)

_MENU_SEED = [
    {"name": "Margherita Pizza", "description": "Classic tomato & mozzarella", "price": Decimal("12.99")},
    {"name": "Pepperoni Pizza", "description": "Loaded with pepperoni", "price": Decimal("14.99")},
    {"name": "Caesar Salad", "description": "Romaine, croutons, parmesan", "price": Decimal("8.99")},
    {"name": "Chicken Burger", "description": "Grilled chicken with lettuce & tomato", "price": Decimal("10.99")},
    {"name": "Veggie Wrap", "description": "Grilled vegetables in a tortilla", "price": Decimal("9.49")},
    {"name": "Garlic Bread", "description": "Toasted bread with garlic butter", "price": Decimal("4.99")},
    {"name": "Coke", "description": "330 ml can", "price": Decimal("2.50")},
    {"name": "Water", "description": "500 ml bottle", "price": Decimal("1.99")},
]


async def seed_menu_items() -> None:
    """Populate menu_items if the table is empty. Called once on startup."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MenuItem).limit(1))
        if result.scalars().first() is not None:
            return
        for item_data in _MENU_SEED:
            db.add(MenuItem(**item_data))
        await db.commit()
        logger.info("Seeded %d menu items", len(_MENU_SEED))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(order: Order) -> OrderResponse:
    items = [
        OrderItemResponse(
            id=item.id,
            menu_item_id=item.menu_item_id,
            menu_item_name=item.menu_item.name if item.menu_item else "Unknown",
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )
        for item in order.items
    ]

    payment_attempts = [
        PaymentAttemptResponse(
            id=pa.id,
            status=pa.status,
            attempt_count=pa.attempt_count,
            error_message=pa.error_message,
            processing_time_ms=pa.processing_time_ms,
            created_at=pa.created_at,
        )
        for pa in order.payment_attempts
    ]

    payment_successful = any(pa.status == PaymentStatus.SUCCESS for pa in order.payment_attempts)

    return OrderResponse(
        id=order.id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items,
        payment_attempts=payment_attempts,
        payment_successful=payment_successful,
    )


async def _fetch_order(db: AsyncSession, order_id: uuid.UUID) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.menu_item),
            selectinload(Order.payment_attempts),
        )
    )
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> OrderResponse | None:
    order = await _fetch_order(db, order_id)
    if order is None:
        return None
    return _build_response(order)


async def create_order(
    db: AsyncSession,
    order_data: OrderCreate,
    request_id: str,
) -> OrderResponse:
    # 1. Validate menu items
    menu_item_ids = [item.menu_item_id for item in order_data.items]
    result = await db.execute(
        select(MenuItem).where(
            MenuItem.id.in_(menu_item_ids),
            MenuItem.is_available.is_(True),
        )
    )
    menu_items: dict[uuid.UUID, MenuItem] = {m.id: m for m in result.scalars().all()}

    missing = set(menu_item_ids) - set(menu_items.keys())
    if missing:
        raise ValueError(f"Menu items not found or unavailable: {[str(m) for m in missing]}")

    # 2. Calculate totals
    line_items: list[dict] = []
    total = Decimal("0.00")
    for req_item in order_data.items:
        menu_item = menu_items[req_item.menu_item_id]
        unit_price = menu_item.price
        subtotal = unit_price * req_item.quantity
        total += subtotal
        line_items.append(
            {
                "menu_item_id": req_item.menu_item_id,
                "quantity": req_item.quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
            }
        )

    # 3. Persist order + items (status: PROCESSING while payment runs)
    order = Order(
        customer_name=order_data.customer_name,
        customer_email=str(order_data.customer_email),
        status=OrderStatus.PROCESSING,
        total_amount=total,
    )
    db.add(order)
    await db.flush()  # obtain order.id before inserting items

    for line in line_items:
        db.add(OrderItem(order_id=order.id, **line))

    await db.commit()

    logger.info(
        "Order created, initiating payment",
        extra={
            "order_id": str(order.id),
            "request_id": request_id,
            "amount": float(total),
            "item_count": len(line_items),
        },
    )

    # 4. Process payment (handles retries + circuit breaker internally)
    result = await payment_service.process_payment(
        order_id=order.id,
        amount=float(total),
        request_id=request_id,
    )

    # 5. Record payment attempt
    pa = PaymentAttempt(
        order_id=order.id,
        status=PaymentStatus.SUCCESS if result.success else PaymentStatus.FAILED,
        amount=total,
        attempt_count=result.attempt_count,
        error_message=result.error_message,
        processing_time_ms=result.processing_time_ms,
    )
    db.add(pa)

    # 6. Finalise order status
    order.status = OrderStatus.COMPLETED if result.success else OrderStatus.FAILED
    await db.commit()

    logger.info(
        "Order finalised",
        extra={
            "order_id": str(order.id),
            "request_id": request_id,
            "status": order.status.value,
            "payment_success": result.success,
        },
    )

    # 7. Re-fetch with all relationships for the response
    order = await _fetch_order(db, order.id)
    return _build_response(order)
