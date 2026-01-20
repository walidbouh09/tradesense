"""Trading API routers."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer

from ....shared.exceptions.base import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from ..application.commands import CancelOrderCommand, PlaceOrderCommand
from ..application.handlers import (
    CancelOrderHandler,
    GetActiveOrdersHandler,
    GetOrderHandler,
    GetPositionHandler,
    GetUserOrdersHandler,
    PlaceOrderHandler,
)
from ..application.queries import (
    GetActiveOrdersQuery,
    GetOrderQuery,
    GetPositionQuery,
    GetUserOrdersQuery,
)
from .schemas import (
    CancelOrderRequest,
    CancelOrderResponse,
    OrderListResponse,
    OrderResponse,
    OrderWithFillsResponse,
    PlaceOrderRequest,
    PlaceOrderResponse,
    PositionResponse,
)

router = APIRouter(prefix="/trading", tags=["trading"])
security = HTTPBearer()


# Dependency to get current user ID (simplified for demo)
async def get_current_user_id(token: str = Depends(security)) -> UUID:
    """Get current user ID from token (simplified implementation)."""
    # In real implementation, decode JWT token and extract user ID
    # For demo purposes, return a fixed UUID
    return UUID("550e8400-e29b-41d4-a716-446655440000")


@router.post("/orders", response_model=PlaceOrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    request: PlaceOrderRequest,
    user_id: UUID = Depends(get_current_user_id),
    handler: PlaceOrderHandler = Depends(),
) -> PlaceOrderResponse:
    """Place a new order."""
    try:
        command = PlaceOrderCommand(
            user_id=user_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force,
        )
        
        order_id = await handler.handle(command)
        
        return PlaceOrderResponse(order_id=order_id)
    
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/orders/{order_id}", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: UUID,
    request: CancelOrderRequest,
    user_id: UUID = Depends(get_current_user_id),
    handler: CancelOrderHandler = Depends(),
) -> CancelOrderResponse:
    """Cancel an existing order."""
    try:
        command = CancelOrderCommand(
            order_id=order_id,
            user_id=user_id,
            reason=request.reason,
        )
        
        await handler.handle(command)
        
        return CancelOrderResponse()
    
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/orders/{order_id}", response_model=OrderWithFillsResponse)
async def get_order(
    order_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    handler: GetOrderHandler = Depends(),
) -> OrderWithFillsResponse:
    """Get a specific order with fills."""
    try:
        query = GetOrderQuery(order_id=order_id, user_id=user_id)
        order = await handler.handle(query)
        
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
        # Convert fills
        fills = [
            {
                "fill_id": fill.fill_id,
                "quantity": str(fill.quantity.value),
                "price": str(fill.price.value.amount),
                "timestamp": fill.timestamp,
            }
            for fill in order.fills
        ]
        
        return OrderWithFillsResponse(
            id=order.id,
            symbol=str(order.symbol),
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=str(order.quantity.value),
            price=str(order.price.value.amount) if order.price else None,
            stop_price=str(order.stop_price.value.amount) if order.stop_price else None,
            time_in_force=order.time_in_force.value,
            status=order.status.value,
            filled_quantity=str(order.filled_quantity.value),
            remaining_quantity=str(order.remaining_quantity.value),
            average_fill_price=str(order.average_fill_price.amount) if order.average_fill_price else None,
            created_at=order.created_at,
            updated_at=order.updated_at,
            fills=fills,
        )
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/orders", response_model=OrderListResponse)
async def get_user_orders(
    status: Optional[str] = Query(None, description="Filter by order status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Number of orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    user_id: UUID = Depends(get_current_user_id),
    handler: GetUserOrdersHandler = Depends(),
) -> OrderListResponse:
    """Get orders for the current user."""
    try:
        query = GetUserOrdersQuery(
            user_id=user_id,
            status=status,
            symbol=symbol,
            limit=limit,
            offset=offset,
        )
        
        orders = await handler.handle(query)
        
        # Convert to response format
        order_responses = [
            OrderResponse(
                id=order.id,
                symbol=str(order.symbol),
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=str(order.quantity.value),
                price=str(order.price.value.amount) if order.price else None,
                stop_price=str(order.stop_price.value.amount) if order.stop_price else None,
                time_in_force=order.time_in_force.value,
                status=order.status.value,
                filled_quantity=str(order.filled_quantity.value),
                remaining_quantity=str(order.remaining_quantity.value),
                average_fill_price=str(order.average_fill_price.amount) if order.average_fill_price else None,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
            for order in orders
        ]
        
        return OrderListResponse(
            orders=order_responses,
            total=len(order_responses),  # In real implementation, get actual total count
            limit=limit,
            offset=offset,
        )
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/orders/active", response_model=List[OrderResponse])
async def get_active_orders(
    user_id: UUID = Depends(get_current_user_id),
    handler: GetActiveOrdersHandler = Depends(),
) -> List[OrderResponse]:
    """Get active orders for the current user."""
    try:
        query = GetActiveOrdersQuery(user_id=user_id)
        orders = await handler.handle(query)
        
        return [
            OrderResponse(
                id=order.id,
                symbol=str(order.symbol),
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=str(order.quantity.value),
                price=str(order.price.value.amount) if order.price else None,
                stop_price=str(order.stop_price.value.amount) if order.stop_price else None,
                time_in_force=order.time_in_force.value,
                status=order.status.value,
                filled_quantity=str(order.filled_quantity.value),
                remaining_quantity=str(order.remaining_quantity.value),
                average_fill_price=str(order.average_fill_price.amount) if order.average_fill_price else None,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
            for order in orders
        ]
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    user_id: UUID = Depends(get_current_user_id),
    handler: GetPositionHandler = Depends(),
) -> PositionResponse:
    """Get position for a specific symbol."""
    try:
        query = GetPositionQuery(user_id=user_id, symbol=symbol)
        position_data = await handler.handle(query)
        
        return PositionResponse(**position_data)
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")