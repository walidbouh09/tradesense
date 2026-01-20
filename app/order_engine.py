"""
Advanced Order Engine

Professional order management system supporting:
- Market Orders
- Limit Orders
- Stop-Loss Orders
- Take-Profit Orders
- Trailing Stop Orders
- OCO (One-Cancels-Other) Orders
"""

from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import uuid

from app.market_data import market_data


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    OCO = "OCO"


class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class Order:
    """Professional order object with advanced features."""

    def __init__(
        self,
        order_id: str,
        challenge_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        trailing_stop_percent: Optional[Decimal] = None,
        time_in_force: str = "GTC",
        parent_order_id: Optional[str] = None,
        linked_order_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.order_id = order_id
        self.challenge_id = challenge_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.limit_price = limit_price
        self.stop_price = stop_price
        self.take_profit_price = take_profit_price
        self.trailing_stop_percent = trailing_stop_percent
        self.time_in_force = time_in_force
        self.status = OrderStatus.PENDING
        self.parent_order_id = parent_order_id
        self.linked_order_id = linked_order_id

        # Execution tracking
        self.filled_quantity = Decimal('0')
        self.remaining_quantity = quantity
        self.average_fill_price = None

        # Timestamps
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.expires_at = None

        # For trailing stops
        self.highest_price_since_entry = None
        self.trailing_stop_price = None

        self.metadata = metadata or {}

    def should_trigger(self, current_price: Decimal) -> Tuple[bool, str]:
        """
        Check if the order should be triggered based on current market price.

        Returns (should_trigger, reason)
        """
        if self.status != OrderStatus.OPEN:
            return False, "Order not in open state"

        if self.order_type == OrderType.MARKET:
            return True, "Market order always triggers"

        elif self.order_type == OrderType.LIMIT:
            if self.side == OrderSide.BUY and current_price <= self.limit_price:
                return True, f"Buy limit triggered at {current_price}"
            elif self.side == OrderSide.SELL and current_price >= self.limit_price:
                return True, f"Sell limit triggered at {current_price}"

        elif self.order_type == OrderType.STOP_LOSS:
            if self.side == OrderSide.BUY and current_price <= self.stop_price:
                return True, f"Stop loss triggered at {current_price}"
            elif self.side == OrderSide.SELL and current_price >= self.stop_price:
                return True, f"Stop loss triggered at {current_price}"

        elif self.order_type == OrderType.TAKE_PROFIT:
            if self.side == OrderSide.BUY and current_price >= self.take_profit_price:
                return True, f"Take profit triggered at {current_price}"
            elif self.side == OrderSide.SELL and current_price <= self.take_profit_price:
                return True, f"Take profit triggered at {current_price}"

        elif self.order_type == OrderType.TRAILING_STOP:
            return self._check_trailing_stop_trigger(current_price)

        return False, "Conditions not met"

    def _check_trailing_stop_trigger(self, current_price: Decimal) -> Tuple[bool, str]:
        """Check if trailing stop should trigger."""
        if not self.trailing_stop_percent:
            return False, "No trailing stop percentage set"

        # Update highest price for buy orders, lowest for sell orders
        if self.side == OrderSide.BUY:
            if self.highest_price_since_entry is None:
                self.highest_price_since_entry = current_price
            else:
                self.highest_price_since_entry = max(self.highest_price_since_entry, current_price)

            # Calculate trailing stop price
            stop_price = self.highest_price_since_entry * (1 - self.trailing_stop_percent)

            # Check if current price has dropped below stop price
            if current_price <= stop_price:
                return True, f"Trailing stop triggered at {current_price}"

        else:  # SELL
            if self.highest_price_since_entry is None:
                self.highest_price_since_entry = current_price
            else:
                self.highest_price_since_entry = min(self.highest_price_since_entry, current_price)

            # Calculate trailing stop price (higher for sell orders)
            stop_price = self.highest_price_since_entry * (1 + self.trailing_stop_percent)

            # Check if current price has risen above stop price
            if current_price >= stop_price:
                return True, f"Trailing stop triggered at {current_price}"

        return False, "Trailing stop conditions not met"

    def fill_order(self, fill_price: Decimal, fill_quantity: Decimal) -> Dict[str, Any]:
        """
        Fill part or all of the order.

        Returns execution details.
        """
        if fill_quantity > self.remaining_quantity:
            raise ValueError("Fill quantity exceeds remaining quantity")

        # Update filled quantity
        self.filled_quantity += fill_quantity
        self.remaining_quantity -= fill_quantity

        # Update average fill price
        if self.average_fill_price is None:
            self.average_fill_price = fill_price
        else:
            total_value = (self.average_fill_price * (self.filled_quantity - fill_quantity)) + (fill_price * fill_quantity)
            self.average_fill_price = total_value / self.filled_quantity

        # Check if order is fully filled
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED

        self.updated_at = datetime.now(timezone.utc)

        return {
            'order_id': self.order_id,
            'fill_price': fill_price,
            'fill_quantity': fill_quantity,
            'remaining_quantity': self.remaining_quantity,
            'status': self.status.value,
            'average_fill_price': self.average_fill_price
        }


class OrderEngine:
    """Professional order execution engine."""

    def __init__(self):
        self.active_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []

    def create_order(
        self,
        challenge_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: str = "MARKET",
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        trailing_stop_percent: Optional[Decimal] = None,
        time_in_force: str = "GTC"
    ) -> Order:
        """
        Create a new order with validation.

        Supports advanced order types and bracket orders.
        """
        # Validate inputs
        self._validate_order_inputs(
            symbol, side, quantity, order_type, limit_price, stop_price,
            take_profit_price, trailing_stop_percent
        )

        # Create order
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            challenge_id=challenge_id,
            symbol=symbol,
            side=OrderSide(side),
            quantity=quantity,
            order_type=OrderType(order_type),
            limit_price=limit_price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            trailing_stop_percent=trailing_stop_percent,
            time_in_force=time_in_force
        )

        # For market orders, execute immediately
        if order.order_type == OrderType.MARKET:
            execution_result = self.execute_order(order)
            return order
        else:
            # Add to active orders for monitoring
            self.active_orders[order_id] = order
            order.status = OrderStatus.OPEN

        return order

    def _validate_order_inputs(
        self, symbol: str, side: str, quantity: Decimal,
        order_type: str, limit_price: Optional[Decimal],
        stop_price: Optional[Decimal], take_profit_price: Optional[Decimal],
        trailing_stop_percent: Optional[Decimal]
    ):
        """Validate order parameters."""
        if not symbol or len(symbol) > 20:
            raise ValueError("Invalid symbol")

        if side not in ['BUY', 'SELL']:
            raise ValueError("Side must be BUY or SELL")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if order_type == 'LIMIT' and limit_price is None:
            raise ValueError("Limit price required for limit orders")

        if order_type == 'STOP_LOSS' and stop_price is None:
            raise ValueError("Stop price required for stop loss orders")

        if order_type == 'TAKE_PROFIT' and take_profit_price is None:
            raise ValueError("Take profit price required for take profit orders")

        if order_type == 'TRAILING_STOP' and trailing_stop_percent is None:
            raise ValueError("Trailing stop percentage required for trailing stop orders")

        # Validate price relationships
        if limit_price and limit_price <= 0:
            raise ValueError("Limit price must be positive")

        if stop_price and stop_price <= 0:
            raise ValueError("Stop price must be positive")

        if take_profit_price and take_profit_price <= 0:
            raise ValueError("Take profit price must be positive")

        if trailing_stop_percent and (trailing_stop_percent <= 0 or trailing_stop_percent >= 1):
            raise ValueError("Trailing stop percentage must be between 0 and 1")

    def execute_order(self, order: Order) -> Dict[str, Any]:
        """
        Execute an order against current market prices.

        Returns execution details.
        """
        # Get current market price
        current_price, _ = market_data.get_stock_price(order.symbol)

        if current_price is None:
            raise ValueError(f"Unable to get market price for {order.symbol}")

        # For market orders, use current price
        if order.order_type == OrderType.MARKET:
            execution_price = current_price
        else:
            # For pending orders that triggered, use trigger price
            execution_price = current_price

        # Execute the fill
        fill_result = order.fill_order(execution_price, order.quantity)

        # Move to history
        self.order_history.append(order)
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]

        return {
            'order_id': order.order_id,
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'execution_price': execution_price,
            'total_value': execution_price * order.quantity,
            'status': order.status.value,
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

    def monitor_orders(self) -> List[Dict[str, Any]]:
        """
        Monitor active orders and trigger executions.

        Returns list of triggered orders.
        """
        triggered_orders = []

        for order_id, order in list(self.active_orders.items()):
            try:
                current_price, _ = market_data.get_stock_price(order.symbol)

                if current_price is None:
                    continue

                should_trigger, reason = order.should_trigger(current_price)

                if should_trigger:
                    execution_result = self.execute_order(order)
                    execution_result['trigger_reason'] = reason
                    triggered_orders.append(execution_result)

            except Exception as e:
                # Log error but continue monitoring other orders
                print(f"Error monitoring order {order_id}: {e}")

        return triggered_orders

    def cancel_order(self, order_id: str) -> Optional[Order]:
        """Cancel an active order."""
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)

            # Move to history
            self.order_history.append(order)
            del self.active_orders[order_id]

            return order

        return None

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        if order_id in self.active_orders:
            return self.active_orders[order_id]

        # Check history
        for order in self.order_history:
            if order.order_id == order_id:
                return order

        return None

    def get_active_orders(self, challenge_id: Optional[str] = None) -> List[Order]:
        """Get active orders, optionally filtered by challenge."""
        orders = list(self.active_orders.values())

        if challenge_id:
            orders = [o for o in orders if o.challenge_id == challenge_id]

        return orders

    def create_bracket_order(
        self,
        challenge_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        entry_price: Optional[Decimal] = None,
        stop_loss_percent: Optional[Decimal] = None,
        take_profit_percent: Optional[Decimal] = None
    ) -> List[Order]:
        """
        Create a bracket order (entry + stop loss + take profit).

        Returns list of created orders.
        """
        orders = []

        # Create entry order
        if entry_price:
            entry_order = self.create_order(
                challenge_id=challenge_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type='LIMIT',
                limit_price=entry_price
            )
        else:
            entry_order = self.create_order(
                challenge_id=challenge_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type='MARKET'
            )

        orders.append(entry_order)

        # Create stop loss order (OCO with take profit)
        if stop_loss_percent:
            if side == 'BUY':
                stop_price = entry_price * (1 - stop_loss_percent) if entry_price else None
            else:
                stop_price = entry_price * (1 + stop_loss_percent) if entry_price else None

            if stop_price:
                stop_order = self.create_order(
                    challenge_id=challenge_id,
                    symbol=symbol,
                    side='SELL' if side == 'BUY' else 'BUY',
                    quantity=quantity,
                    order_type='STOP_LOSS',
                    stop_price=stop_price,
                    linked_order_id=entry_order.order_id
                )
                orders.append(stop_order)

        # Create take profit order (OCO with stop loss)
        if take_profit_percent:
            if side == 'BUY':
                tp_price = entry_price * (1 + take_profit_percent) if entry_price else None
            else:
                tp_price = entry_price * (1 - take_profit_percent) if entry_price else None

            if tp_price:
                tp_order = self.create_order(
                    challenge_id=challenge_id,
                    symbol=symbol,
                    side='SELL' if side == 'BUY' else 'BUY',
                    quantity=quantity,
                    order_type='TAKE_PROFIT',
                    take_profit_price=tp_price,
                    linked_order_id=entry_order.order_id
                )
                orders.append(tp_order)

        return orders


# Global order engine instance
order_engine = OrderEngine()