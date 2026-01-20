"""Trading application queries."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GetOrderQuery(BaseModel):
    """Query to get a specific order."""
    
    order_id: UUID
    user_id: UUID


class GetUserOrdersQuery(BaseModel):
    """Query to get orders for a user."""
    
    user_id: UUID
    status: Optional[str] = None
    symbol: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class GetActiveOrdersQuery(BaseModel):
    """Query to get active orders for a user."""
    
    user_id: UUID


class GetPositionQuery(BaseModel):
    """Query to get position for a symbol."""
    
    user_id: UUID
    symbol: str = Field(..., min_length=1, max_length=20)