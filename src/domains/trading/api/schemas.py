"""Trading API schemas (DTOs)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlaceOrderRequest(BaseModel):
    """Request schema for placing an order."""
    
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    side: str = Field(..., pattern="^(BUY|SELL)$", description="Order side")
    order_type: str = Field(..., pattern="^(MARKET|LIMIT|STOP|STOP_LIMIT)$", description="Order type")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="Limit price (required for LIMIT and STOP_LIMIT orders)")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price (required for STOP and STOP_LIMIT orders)")
    time_in_force: str = Field("DAY", pattern="^(DAY|GTC|IOC|FOK)$", description="Time in force")


class CancelOrderRequest(BaseModel):
    """Request schema for cancelling an order."""
    
    reason: str = Field("User requested", max_length=255, description="Cancellation reason")


class OrderResponse(BaseModel):
    """Response schema for order information."""
    
    id: UUID
    symbol: str
    side: str
    order_type: str
    quantity: str
    price: Optional[str] = None
    stop_price: Optional[str] = None
    time_in_force: str
    status: str
    filled_quantity: str
    remaining_quantity: str
    average_fill_price: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FillResponse(BaseModel):
    """Response schema for fill information."""
    
    fill_id: str
    quantity: str
    price: str
    timestamp: Optional[str] = None
    
    class Config:
        from_attributes = True


class OrderWithFillsResponse(OrderResponse):
    """Response schema for order with fills."""
    
    fills: List[FillResponse] = []


class PositionResponse(BaseModel):
    """Response schema for position information."""
    
    symbol: str
    quantity: str
    side: str  # LONG, SHORT, or FLAT
    unrealized_pnl: Optional[str] = None
    
    class Config:
        from_attributes = True


class PlaceOrderResponse(BaseModel):
    """Response schema for place order operation."""
    
    order_id: UUID
    message: str = "Order placed successfully"


class CancelOrderResponse(BaseModel):
    """Response schema for cancel order operation."""
    
    message: str = "Order cancelled successfully"


class OrderListResponse(BaseModel):
    """Response schema for order list."""
    
    orders: List[OrderResponse]
    total: int
    limit: int
    offset: int