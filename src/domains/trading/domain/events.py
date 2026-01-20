"""Trading domain events."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from ....shared.kernel.events import DomainEvent


class OrderPlaced(DomainEvent):
    """Event emitted when an order is placed."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = "DAY",
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force


class OrderFilled(DomainEvent):
    """Event emitted when an order is filled (partially or completely)."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        side: str,
        filled_quantity: str,
        fill_price: str,
        fill_id: str,
        remaining_quantity: str,
        is_complete: bool,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.filled_quantity = filled_quantity
        self.fill_price = fill_price
        self.fill_id = fill_id
        self.remaining_quantity = remaining_quantity
        self.is_complete = is_complete


class OrderCancelled(DomainEvent):
    """Event emitted when an order is cancelled."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        cancelled_quantity: str,
        reason: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.cancelled_quantity = cancelled_quantity
        self.reason = reason


class OrderRejected(DomainEvent):
    """Event emitted when an order is rejected."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        rejection_reason: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.rejection_reason = rejection_reason


class TradeExecuted(DomainEvent):
    """Event emitted when a trade is executed."""

    def __init__(
        self,
        aggregate_id: UUID,
        trade_id: str,
        user_id: UUID,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        gross_value: str,
        net_value: str,
        commission: str,
        order_id: UUID,
        fill_id: str,
        trade_type: str,
        executed_at: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.trade_id = trade_id
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.gross_value = gross_value
        self.net_value = net_value
        self.commission = commission
        self.order_id = order_id
        self.fill_id = fill_id
        self.trade_type = trade_type
        self.executed_at = executed_at


class PositionOpened(DomainEvent):
    """Event emitted when a new position is opened."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        side: str,
        quantity: str,
        entry_price: str,
        entry_value: str,
        opening_trade_id: UUID,
        opened_at: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_value = entry_value
        self.opening_trade_id = opening_trade_id
        self.opened_at = opened_at


class PositionClosed(DomainEvent):
    """Event emitted when a position is closed."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        side: str,
        quantity: str,
        entry_price: str,
        exit_price: str,
        realized_pnl: str,
        total_commission: str,
        closing_trade_id: UUID,
        closed_at: str,
        duration_seconds: int,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.realized_pnl = realized_pnl
        self.total_commission = total_commission
        self.closing_trade_id = closing_trade_id
        self.closed_at = closed_at
        self.duration_seconds = duration_seconds


class PositionUpdated(DomainEvent):
    """Event emitted when a position is updated (increased/reduced)."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        trade_id: UUID,
        trade_type: str,
        new_quantity: str,
        new_entry_price: str,
        realized_pnl: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.trade_id = trade_id
        self.trade_type = trade_type
        self.new_quantity = new_quantity
        self.new_entry_price = new_entry_price
        self.realized_pnl = realized_pnl


class PnLCalculated(DomainEvent):
    """Event emitted when P&L is calculated for a position."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        symbol: str,
        position_side: str,
        quantity: str,
        entry_price: str,
        current_price: str,
        unrealized_pnl: str,
        realized_pnl: str,
        total_pnl: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.symbol = symbol
        self.position_side = position_side
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = current_price
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        self.total_pnl = total_pnl


class DailyPnLCalculated(DomainEvent):
    """Event emitted when daily P&L is calculated for an account."""

    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        date: str,
        daily_pnl: str,
        total_realized_pnl: str,
        total_unrealized_pnl: str,
        total_pnl: str,
        current_balance: str,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        trading_days: int,
    ) -> None:
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.date = date
        self.daily_pnl = daily_pnl
        self.total_realized_pnl = total_realized_pnl
        self.total_unrealized_pnl = total_unrealized_pnl
        self.total_pnl = total_pnl
        self.current_balance = current_balance
        self.total_trades = total_trades
        self.winning_trades = winning_trades
        self.losing_trades = losing_trades
        self.trading_days = trading_days


class TradeClosed(DomainEvent):
    """Event emitted when a trade is closed (for audit purposes)."""

    def __init__(
        self,
        aggregate_id: UUID,
        trade_id: str,
        user_id: UUID,
        symbol: str,
        realized_pnl: str,
        closed_at: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.trade_id = trade_id
        self.user_id = user_id
        self.symbol = symbol
        self.realized_pnl = realized_pnl
        self.closed_at = closed_at
