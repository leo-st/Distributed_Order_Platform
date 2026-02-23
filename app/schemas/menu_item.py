import uuid
from decimal import Decimal

from pydantic import BaseModel


class MenuItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    is_available: bool

    model_config = {"from_attributes": True}
