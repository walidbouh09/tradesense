"""Trading domain entities."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from ....shared.utils.money import Money
from .events import OrderCancelled, OrderFilled, OrderPlaced, OrderRejected
from .value_objects import (
    Fill,
    OrderSide,
    OrderStatus,
    OrderType,
    Price,
    Quantity,
    Symbol,
    TimeInForce,
)


class Order(AggregateRoot):
    """Order aggregate root."""
    
    def __init__(
        self,
        user_id: UUID,
        symbol: Symbol,
        side: OrderSide,
        order_type: OrderType,
        quantity: Quantity,
        price: Optional[Price] = None,
        stop_price: Optional[Price] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._user_id = user_id
        self._symbol = symbol
        self._side = side
        self._order_type = order_type
        self._quantity = quantity
        self._price = price
        self._stop_price = stop_price
        self._time_in_force = time_in_force
        
        self._status = OrderStatus.PENDING
        self._filled_quantity = Quantity(Decimal("0"))
        self._fills: List[Fill] = []
        self._rejection_reason: Optional[str] = None
        self._cancelled_reason: Optional[str] = None
        
        self._validate_order()
    
    def _validate_order(self) -> None:
        """Validate order parameters."""
        if self._order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not self._price:
            raise ValidationError("Limit orders require a price")
        
        if self._order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not self._stop_price:
            raise ValidationError("Stop orders require a stop price")
        
        if self._price and self._stop_price:
            if self._side == OrderSide.BUY and self._stop_price >= self._price:
                raise ValidationError("Buy stop price must be below limit price")
            elif self._side == OrderSide.SELL and self._stop_price <= self._price:
                raise ValidationError("Sell stop price must be above limit price")
    
    def submit(self) -> None:
        """Submit the order for execution."""
        if self._status != OrderStatus.PENDING:
            raise BusinessRuleViolationError("Only pending orders can be submitted")
        
        self._status = OrderStatus.SUBMITTED
        self._touch()
        
        # Emit domain event
        self.add_domain_event(
            OrderPlaced(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                side=self._side.value,
                order_type=self._order_type.value,
                quantity=str(self._quantity.value),
                price=str(self._price.value.amount) if self._price else None,
                stop_price=str(self._stop_price.value.amount) if self._stop_price else None,
                time_in_force=self._time_in_force.value,
            )
        )
    
    def fill(self, fill: Fill) -> None:
        """Process a fill for this order."""
        if self._status not in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            raise BusinessRuleViolationError("Only submitted orders can be filled")
        
        if self._filled_quantity + fill.quantity > self._quantity:
            raise BusinessRuleViolationError("Fill quantity exceeds remaining order quantity")
        
        self._fills.append(fill)
        self._filled_quantity = self._filled_quantity + fill.quantity
        
        # Update status
        if self._filled_quantity >= self._quantity:
            self._status = OrderStatus.FILLED
        else:
            self._status = OrderStatus.PARTIALLY_FILLED
        
        self._touch()
        
        # Emit domain event
        remaining_qty = self._quantity - self._filled_quantity
        self.add_domain_event(
            OrderFilled(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                side=self._side.value,
                filled_quantity=str(fill.quantity.value),
                fill_price=str(fill.price.value.amount),
                fill_id=fill.fill_id,
                remaining_quantity=str(remaining_qty.value),
                is_complete=self._status == OrderStatus.FILLED,
            )
        )
    
    def cancel(self, reason: str = "User requested") -> None:
        """Cancel the order."""
        if self._status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            raise BusinessRuleViolationError("Order cannot be cancelled in current status")
        
        cancelled_quantity = self._quantity - self._filled_quantity
        self._status = OrderStatus.CANCELLED
        self._cancelled_reason = reason
        self._touch()
        
        # Emit domain event
        self.add_domain_event(
            OrderCancelled(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                cancelled_quantity=str(cancelled_quantity.value),
                reason=reason,
            )
        )
    
    def reject(self, reason: str) -> None:
        """Reject the order."""
        if self._status != OrderStatus.SUBMITTED:
            raise BusinessRuleViolationError("Only submitted orders can be rejected")
        
        self._status = OrderStatus.REJECTED
        self._rejection_reason = reason
        self._touch()
        
        # Emit domain event
        self.add_domain_event(
            OrderRejected(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                rejection_reason=reason,
            )
        )
    
    # Properties
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def symbol(self) -> Symbol:
        return self._symbol
    
    @property
    def side(self) -> OrderSide:
        return self._side
    
    @property
    def order_type(self) -> OrderType:
        return self._order_type
    
    @property
    def quantity(self) -> Quantity:
        return self._quantity
    
    @property
    def price(self) -> Optional[Price]:
        return self._price
    
    @property
    def stop_price(self) -> Optional[Price]:
        return self._stop_price
    
    @property
    def time_in_force(self) -> TimeInForce:
        return self._time_in_force
    
    @property
    def status(self) -> OrderStatus:
        return self._status
    
    @property
    def filled_quantity(self) -> Quantity:
        return self._filled_quantity
    
    @property
    def remaining_quantity(self) -> Quantity:
        return self._quantity - self._filled_quantity
    
    @property
    def fills(self) -> List[Fill]:
        return self._fills.copy()
    
    @property
    def is_complete(self) -> bool:
        return self._status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
    
    @property
    def average_fill_price(self) -> Optional[Money]:
        """Calculate average fill price."""
        if not self._fills:
            return None
        
        total_value = Money.zero()
        total_quantity = Decimal("0")
        
        for fill in self._fills:
            total_value = total_value + fill.value
            total_quantity += fill.quantity.value
        
        if total_quantity == 0:
            return None
        
        return Money(total_value.amount / total_quantity)