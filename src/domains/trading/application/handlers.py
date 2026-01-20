"""Trading application command and query handlers."""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ....shared.events.event_bus import EventBus
from ....shared.exceptions.base import EntityNotFoundError, ValidationError
from ....shared.utils.money import Money
from ..domain.entities import Order
from ..domain.repositories import OrderRepository
from ..domain.services import OrderValidationService, PositionCalculator
from ..domain.value_objects import (
    OrderSide,
    OrderStatus,
    OrderType,
    Price,
    Quantity,
    Symbol,
    TimeInForce,
)
from .commands import CancelOrderCommand, ModifyOrderCommand, PlaceOrderCommand
from .queries import (
    GetActiveOrdersQuery,
    GetOrderQuery,
    GetPositionQuery,
    GetUserOrdersQuery,
)


class PlaceOrderHandler:
    """Handler for placing orders."""
    
    def __init__(
        self,
        order_repository: OrderRepository,
        event_bus: EventBus,
        validation_service: OrderValidationService,
    ) -> None:
        self._order_repository = order_repository
        self._event_bus = event_bus
        self._validation_service = validation_service
    
    async def handle(self, command: PlaceOrderCommand) -> UUID:
        """Handle place order command."""
        # Convert command to domain objects
        symbol = Symbol(command.symbol)
        side = OrderSide(command.side)
        order_type = OrderType(command.order_type)
        quantity = Quantity(command.quantity)
        time_in_force = TimeInForce(command.time_in_force)
        
        price = None
        if command.price is not None:
            price = Price(Money(command.price))
        
        stop_price = None
        if command.stop_price is not None:
            stop_price = Price(Money(command.stop_price))
        
        # Domain validation
        self._validation_service.validate_order_size(quantity, symbol)
        
        # Create order
        order = Order(
            user_id=command.user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )
        
        # Submit order (triggers domain events)
        order.submit()
        
        # Persist order
        await self._order_repository.save(order)
        
        # Publish domain events
        for event in order.domain_events:
            await self._event_bus.publish(event)
        order.clear_domain_events()
        
        return order.id


class CancelOrderHandler:
    """Handler for cancelling orders."""
    
    def __init__(
        self,
        order_repository: OrderRepository,
        event_bus: EventBus,
    ) -> None:
        self._order_repository = order_repository
        self._event_bus = event_bus
    
    async def handle(self, command: CancelOrderCommand) -> None:
        """Handle cancel order command."""
        # Get order
        order = await self._order_repository.get_by_id(command.order_id)
        if not order:
            raise EntityNotFoundError("Order", str(command.order_id))
        
        # Verify ownership
        if order.user_id != command.user_id:
            raise ValidationError("User does not own this order")
        
        # Cancel order (triggers domain events)
        order.cancel(command.reason)
        
        # Persist changes
        await self._order_repository.save(order)
        
        # Publish domain events
        for event in order.domain_events:
            await self._event_bus.publish(event)
        order.clear_domain_events()


class GetOrderHandler:
    """Handler for getting a specific order."""
    
    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository
    
    async def handle(self, query: GetOrderQuery) -> Optional[Order]:
        """Handle get order query."""
        order = await self._order_repository.get_by_id(query.order_id)
        
        if order and order.user_id != query.user_id:
            # Don't reveal existence of orders not owned by user
            return None
        
        return order


class GetUserOrdersHandler:
    """Handler for getting user orders."""
    
    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository
    
    async def handle(self, query: GetUserOrdersQuery) -> List[Order]:
        """Handle get user orders query."""
        status = OrderStatus(query.status) if query.status else None
        
        return await self._order_repository.find_by_user_id(
            user_id=query.user_id,
            status=status,
            limit=query.limit,
            offset=query.offset,
        )


class GetActiveOrdersHandler:
    """Handler for getting active orders."""
    
    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository
    
    async def handle(self, query: GetActiveOrdersQuery) -> List[Order]:
        """Handle get active orders query."""
        return await self._order_repository.find_active_orders(query.user_id)


class GetPositionHandler:
    """Handler for getting position information."""
    
    def __init__(
        self,
        order_repository: OrderRepository,
        position_calculator: PositionCalculator,
    ) -> None:
        self._order_repository = order_repository
        self._position_calculator = position_calculator
    
    async def handle(self, query: GetPositionQuery) -> dict:
        """Handle get position query."""
        symbol = Symbol(query.symbol)
        
        # Get all filled orders for this user and symbol
        orders = await self._order_repository.find_by_user_id(
            user_id=query.user_id,
            status=OrderStatus.FILLED,
        )
        
        # Filter by symbol
        symbol_orders = [order for order in orders if order.symbol == symbol]
        
        # Calculate position
        net_position = self._position_calculator.calculate_net_position(
            symbol_orders, symbol
        )
        
        return {
            "symbol": str(symbol),
            "quantity": str(net_position.value),
            "side": "LONG" if net_position.value > 0 else "FLAT",
        }