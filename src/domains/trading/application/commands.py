"""Trading application commands."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlaceOrderCommand(BaseModel):
    """Command to place a new order."""
    
    user_id: UUID
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    order_type: str = Field(..., pattern="^(MARKET|LIMIT|STOP|STOP_LIMIT)$")
    quantity: Decimal = Field(..., gt=0)
    price: Optional[Decimal] = Field(None, gt=0)
    stop_price: Optional[Decimal] = Field(None, gt=0)
    time_in_force: str = Field("DAY", pattern="^(DAY|GTC|IOC|FOK)$")


class CancelOrderCommand(BaseModel):
    """Command to cancel an existing order."""
    
    order_id: UUID
    user_id: UUID
    reason: str = "User requested"


class ModifyOrderCommand(BaseModel):
    """Command to modify an existing order."""
    
    order_id: UUID
    user_id: UUID
    new_quantity: Optional[Decimal] = Field(None, gt=0)
    new_price: Optional[Decimal] = Field(None, gt=0)
    new_stop_price: Optional[Decimal] = Field(None, gt=0)