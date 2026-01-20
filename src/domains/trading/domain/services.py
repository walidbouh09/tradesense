"""Trading domain services."""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError
from ....shared.utils.money import Money
from .entities import Order
from .value_objects import OrderSide, Price, Quantity, Symbol


class PositionCalculator:
    """Domain service for position calculations."""
    
    @staticmethod
    def calculate_net_position(orders: List[Order], symbol: Symbol) -> Quantity:
        """Calculate net position for a symbol from filled orders."""
        net_quantity = Decimal("0")
        
        for order in orders:
            if order.symbol != symbol or not order.filled_quantity.value:
                continue
            
            if order.side == OrderSide.BUY:
                net_quantity += order.filled_quantity.value
            else:  # SELL
                net_quantity -= order.filled_quantity.value
        
        # Return absolute value as Quantity (positions are always positive)
        return Quantity(abs(net_quantity)) if net_quantity != 0 else Quantity(Decimal("0"))
    
    @staticmethod
    def calculate_unrealized_pnl(
        orders: List[Order],
        symbol: Symbol,
        current_price: Price,
    ) -> Money:
        """Calculate unrealized P&L for a symbol."""
        net_quantity = Decimal("0")
        weighted_avg_price = Decimal("0")
        total_cost = Decimal("0")
        
        for order in orders:
            if order.symbol != symbol or not order.filled_quantity.value:
                continue
            
            fill_value = Decimal("0")
            for fill in order.fills:
                fill_value += fill.quantity.value * fill.price.value.amount
            
            if order.side == OrderSide.BUY:
                net_quantity += order.filled_quantity.value
                total_cost += fill_value
            else:  # SELL
                net_quantity -= order.filled_quantity.value
                total_cost -= fill_value
        
        if net_quantity == 0:
            return Money.zero()
        
        # Calculate weighted average entry price
        avg_entry_price = total_cost / abs(net_quantity)
        
        # Calculate unrealized P&L
        price_diff = current_price.value.amount - avg_entry_price
        if net_quantity < 0:  # Short position
            price_diff = -price_diff
        
        unrealized_pnl = price_diff * abs(net_quantity)
        return Money(unrealized_pnl)


class OrderValidationService:
    """Domain service for order validation."""
    
    @staticmethod
    def validate_order_size(
        quantity: Quantity,
        symbol: Symbol,
        min_quantity: Optional[Quantity] = None,
        max_quantity: Optional[Quantity] = None,
    ) -> None:
        """Validate order size constraints."""
        if min_quantity and quantity < min_quantity:
            raise BusinessRuleViolationError(
                f"Order quantity {quantity} below minimum {min_quantity} for {symbol}"
            )
        
        if max_quantity and quantity > max_quantity:
            raise BusinessRuleViolationError(
                f"Order quantity {quantity} exceeds maximum {max_quantity} for {symbol}"
            )
    
    @staticmethod
    def validate_price_increment(
        price: Price,
        symbol: Symbol,
        tick_size: Money,
    ) -> None:
        """Validate price follows tick size rules."""
        remainder = price.value.amount % tick_size.amount
        if remainder != 0:
            raise BusinessRuleViolationError(
                f"Price {price} does not conform to tick size {tick_size} for {symbol}"
            )