import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.order import OrderCreate, OrderResponse
from app.services import order_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    body: OrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    request_id = _request_id(request)
    logger.info(
        "Received place_order request",
        extra={"request_id": request_id, "customer_email": str(body.customer_email)},
    )
    try:
        return await order_service.create_order(db, body, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    request_id = _request_id(request)
    logger.info(
        "Received get_order request",
        extra={"request_id": request_id, "order_id": str(order_id)},
    )
    order = await order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
