"""Trading domain - Trade entity and related aggregates."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from ....shared.utils.money import Money
from .events import (
    TradeExecuted,
    TradeClosed,
    PositionOpened,
    PositionClosed,
    PositionUpdated,
    PnLCalculated,
    DailyPnLCalculated,
)
from .value_objects import (
    Commission,
    Fill,
    OrderSide,
    PnL,
    PnLType,
    PositionSide,
    Price,
    Quantity,
    Symbol,
    TradeId,
    TradeType,
)


class Trade(AggregateRoot):
    """Trade aggregate representing a single trade execution."""
    
    def __init__(
        self,
        trade_id: TradeId,
        user_id: UUID,
        symbol: Symbol,
        side: OrderSide,
        quantity: Quantity,
        price: Price,
        order_id: UUID,
        fill: Fill,
        trade_type: TradeType = TradeType.OPEN,
        commission: Optional[Commission] = None,
        executed_at: Optional[datetime] = None,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._trade_id = trade_id
        self._user_id = user_id
        self._symbol = symbol
        self._side = side
        self._quantity = quantity
        self._price = price
        self._order_id = order_id
        self._fill = fill
        self._trade_type = trade_type
        self._commission = commission or Commission(Money.zero(price.value.currency))
        self._executed_at = executed_at or datetime.utcnow()
        
        # Calculate trade value
        self._gross_value = Money(
            self._price.value.amount * self._quantity.value,
            self._price.value.currency
        )
        self._net_value = self._gross_value - self._commission.amount
        
        # Validate trade
        self._validate_trade()
        
        # Mark as executed
        self._is_executed = True
        self._touch()
        
        # Emit trade executed event
        self.add_domain_event(
            TradeExecuted(
                aggregate_id=self.id,
                trade_id=str(self._trade_id),
                user_id=self._user_id,
                symbol=str(self._symbol),
                side=self._side.value,
                quantity=str(self._quantity.value),
                price=str(self._price.value.amount),
                gross_value=str(self._gross_value.amount),
                net_value=str(self._net_value.amount),
                commission=str(self._commission.amount.amount),
                order_id=self._order_id,
                fill_id=self._fill.fill_id,
                trade_type=self._trade_type.value,
                executed_at=self._executed_at.isoformat(),
            )
        )
    
    def _validate_trade(self) -> None:
        """Validate trade parameters."""
        if self._quantity.value <= 0:
            raise ValidationError("Trade quantity must be positive")
        
        if self._price.value.amount <= 0:
            raise ValidationError("Trade price must be positive")
        
        if self._commission.amount.amount < 0:
            raise ValidationError("Commission cannot be negative")
    
    def calculate_pnl_against(self, exit_price: Price) -> PnL:
        """Calculate unrealized P&L against a given price."""
        if self._side == OrderSide.BUY:
            # Long position: profit when price goes up
            pnl_amount = (exit_price.value.amount - self._price.value.amount) * self._quantity.value
        else:
            # Short position: profit when price goes down
            pnl_amount = (self._price.value.amount - exit_price.value.amount) * self._quantity.value
        
        # Subtract commission
        pnl_amount -= self._commission.amount.amount
        
        return PnL(
            amount=Money(pnl_amount, self._price.value.currency),
            pnl_type=PnLType.UNREALIZED,
            currency=self._price.value.currency,
        )
    
    # Properties
    @property
    def trade_id(self) -> TradeId:
        return self._trade_id
    
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
    def quantity(self) -> Quantity:
        return self._quantity
    
    @property
    def price(self) -> Price:
        return self._price
    
    @property
    def order_id(self) -> UUID:
        return self._order_id
    
    @property
    def fill(self) -> Fill:
        return self._fill
    
    @property
    def trade_type(self) -> TradeType:
        return self._trade_type
    
    @property
    def commission(self) -> Commission:
        return self._commission
    
    @property
    def executed_at(self) -> datetime:
        return self._executed_at
    
    @property
    def gross_value(self) -> Money:
        return self._gross_value
    
    @property
    def net_value(self) -> Money:
        return self._net_value
    
    @property
    def is_executed(self) -> bool:
        return self._is_executed


class Position(AggregateRoot):
    """Position aggregate representing an open trading position."""
    
    def __init__(
        self,
        user_id: UUID,
        symbol: Symbol,
        side: PositionSide,
        opening_trade: Trade,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._user_id = user_id
        self._symbol = symbol
        self._side = side
        self._quantity = opening_trade.quantity
        self._entry_price = opening_trade.price
        self._entry_value = opening_trade.net_value
        self._total_commission = opening_trade.commission.amount
        
        # Position state
        self._is_open = True
        self._opened_at = opening_trade.executed_at
        self._closed_at: Optional[datetime] = None
        
        # Trade tracking
        self._opening_trade_id = opening_trade.id
        self._trades: List[UUID] = [opening_trade.id]
        self._closing_trade_id: Optional[UUID] = None
        
        # P&L tracking
        self._realized_pnl = Money.zero(opening_trade.price.value.currency)
        self._unrealized_pnl = Money.zero(opening_trade.price.value.currency)
        self._current_price: Optional[Price] = None
        
        self._touch()
        
        # Emit position opened event
        self.add_domain_event(
            PositionOpened(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                side=self._side.value,
                quantity=str(self._quantity.value),
                entry_price=str(self._entry_price.value.amount),
                entry_value=str(self._entry_value.amount),
                opening_trade_id=self._opening_trade_id,
                opened_at=self._opened_at.isoformat(),
            )
        )
    
    def update_quantity(self, trade: Trade) -> None:
        """Update position quantity based on a new trade."""
        if not self._is_open:
            raise BusinessRuleViolationError("Cannot update closed position")
        
        if trade.symbol != self._symbol:
            raise BusinessRuleViolationError("Trade symbol must match position symbol")
        
        # Determine if this increases or reduces the position
        if self._is_same_direction(trade):
            # Increase position
            old_quantity = self._quantity
            old_value = self._entry_value
            
            # Calculate new weighted average entry price
            new_total_value = old_value + trade.net_value
            new_total_quantity = self._quantity + trade.quantity
            
            self._quantity = new_total_quantity
            self._entry_value = new_total_value
            self._entry_price = Price(Money(
                new_total_value.amount / new_total_quantity.value,
                self._entry_price.value.currency
            ))
            self._total_commission += trade.commission.amount
            
            trade_type = TradeType.INCREASE
        else:
            # Reduce position
            if trade.quantity >= self._quantity:
                # Close entire position
                self._close_position(trade)
                return
            else:
                # Partial close - calculate realized P&L
                close_ratio = trade.quantity.value / self._quantity.value
                realized_pnl = self._calculate_partial_close_pnl(trade, close_ratio)
                
                self._realized_pnl += realized_pnl.amount
                self._quantity = self._quantity - trade.quantity
                self._total_commission += trade.commission.amount
                
                trade_type = TradeType.REDUCE
        
        # Add trade to position
        self._trades.append(trade.id)
        self._touch()
        
        # Emit position updated event
        self.add_domain_event(
            PositionUpdated(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                trade_id=trade.id,
                trade_type=trade_type.value,
                new_quantity=str(self._quantity.value),
                new_entry_price=str(self._entry_price.value.amount),
                realized_pnl=str(self._realized_pnl.amount),
            )
        )
    
    def close_position(self, closing_trade: Trade) -> PnL:
        """Close the entire position with a closing trade."""
        if not self._is_open:
            raise BusinessRuleViolationError("Position is already closed")
        
        return self._close_position(closing_trade)
    
    def _close_position(self, closing_trade: Trade) -> PnL:
        """Internal method to close position."""
        # Calculate final realized P&L
        final_pnl = self._calculate_close_pnl(closing_trade)
        
        self._realized_pnl += final_pnl.amount
        self._is_open = False
        self._closed_at = closing_trade.executed_at
        self._closing_trade_id = closing_trade.id
        self._trades.append(closing_trade.id)
        self._total_commission += closing_trade.commission.amount
        
        self._touch()
        
        # Emit position closed event
        self.add_domain_event(
            PositionClosed(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                side=self._side.value,
                quantity=str(self._quantity.value),
                entry_price=str(self._entry_price.value.amount),
                exit_price=str(closing_trade.price.value.amount),
                realized_pnl=str(self._realized_pnl.amount),
                total_commission=str(self._total_commission.amount),
                closing_trade_id=self._closing_trade_id,
                closed_at=self._closed_at.isoformat(),
                duration_seconds=int((self._closed_at - self._opened_at).total_seconds()),
            )
        )
        
        return PnL(
            amount=self._realized_pnl,
            pnl_type=PnLType.REALIZED,
            currency=self._realized_pnl.currency,
        )
    
    def update_market_price(self, current_price: Price) -> PnL:
        """Update current market price and calculate unrealized P&L."""
        if not self._is_open:
            raise BusinessRuleViolationError("Cannot update price for closed position")
        
        self._current_price = current_price
        
        # Calculate unrealized P&L
        if self._side == PositionSide.LONG:
            pnl_amount = (current_price.value.amount - self._entry_price.value.amount) * self._quantity.value
        else:  # SHORT
            pnl_amount = (self._entry_price.value.amount - current_price.value.amount) * self._quantity.value
        
        self._unrealized_pnl = Money(pnl_amount, current_price.value.currency)
        
        unrealized_pnl = PnL(
            amount=self._unrealized_pnl,
            pnl_type=PnLType.UNREALIZED,
            currency=self._unrealized_pnl.currency,
        )
        
        # Emit P&L calculated event
        self.add_domain_event(
            PnLCalculated(
                aggregate_id=self.id,
                user_id=self._user_id,
                symbol=str(self._symbol),
                position_side=self._side.value,
                quantity=str(self._quantity.value),
                entry_price=str(self._entry_price.value.amount),
                current_price=str(current_price.value.amount),
                unrealized_pnl=str(self._unrealized_pnl.amount),
                realized_pnl=str(self._realized_pnl.amount),
                total_pnl=str((self._realized_pnl + self._unrealized_pnl).amount),
            )
        )
        
        return unrealized_pnl
    
    def _is_same_direction(self, trade: Trade) -> bool:
        """Check if trade is in same direction as position."""
        if self._side == PositionSide.LONG:
            return trade.side == OrderSide.BUY
        else:  # SHORT
            return trade.side == OrderSide.SELL
    
    def _calculate_close_pnl(self, closing_trade: Trade) -> PnL:
        """Calculate P&L for closing the entire position."""
        if self._side == PositionSide.LONG:
            # Long position: bought low, selling high
            pnl_amount = (closing_trade.price.value.amount - self._entry_price.value.amount) * self._quantity.value
        else:  # SHORT
            # Short position: sold high, buying low
            pnl_amount = (self._entry_price.value.amount - closing_trade.price.value.amount) * self._quantity.value
        
        return PnL(
            amount=Money(pnl_amount, closing_trade.price.value.currency),
            pnl_type=PnLType.REALIZED,
            currency=closing_trade.price.value.currency,
        )
    
    def _calculate_partial_close_pnl(self, trade: Trade, close_ratio: Decimal) -> PnL:
        """Calculate P&L for partial position close."""
        if self._side == PositionSide.LONG:
            pnl_amount = (trade.price.value.amount - self._entry_price.value.amount) * trade.quantity.value
        else:  # SHORT
            pnl_amount = (self._entry_price.value.amount - trade.price.value.amount) * trade.quantity.value
        
        return PnL(
            amount=Money(pnl_amount, trade.price.value.currency),
            pnl_type=PnLType.REALIZED,
            currency=trade.price.value.currency,
        )
    
    # Properties
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def symbol(self) -> Symbol:
        return self._symbol
    
    @property
    def side(self) -> PositionSide:
        return self._side
    
    @property
    def quantity(self) -> Quantity:
        return self._quantity
    
    @property
    def entry_price(self) -> Price:
        return self._entry_price
    
    @property
    def entry_value(self) -> Money:
        return self._entry_value
    
    @property
    def current_price(self) -> Optional[Price]:
        return self._current_price
    
    @property
    def is_open(self) -> bool:
        return self._is_open
    
    @property
    def opened_at(self) -> datetime:
        return self._opened_at
    
    @property
    def closed_at(self) -> Optional[datetime]:
        return self._closed_at
    
    @property
    def realized_pnl(self) -> Money:
        return self._realized_pnl
    
    @property
    def unrealized_pnl(self) -> Money:
        return self._unrealized_pnl
    
    @property
    def total_pnl(self) -> Money:
        return self._realized_pnl + self._unrealized_pnl
    
    @property
    def total_commission(self) -> Money:
        return self._total_commission
    
    @property
    def trades(self) -> List[UUID]:
        return self._trades.copy()
    
    @property
    def opening_trade_id(self) -> UUID:
        return self._opening_trade_id
    
    @property
    def closing_trade_id(self) -> Optional[UUID]:
        return self._closing_trade_id


class TradingAccount(AggregateRoot):
    """Trading account aggregate for tracking overall P&L and positions."""
    
    def __init__(
        self,
        user_id: UUID,
        account_currency: str = "USD",
        initial_balance: Optional[Money] = None,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._user_id = user_id
        self._account_currency = account_currency
        self._initial_balance = initial_balance or Money.zero(account_currency)
        
        # P&L tracking
        self._total_realized_pnl = Money.zero(account_currency)
        self._total_unrealized_pnl = Money.zero(account_currency)
        self._daily_pnl = Money.zero(account_currency)
        self._total_commission = Money.zero(account_currency)
        
        # Position tracking
        self._open_positions: List[UUID] = []
        self._closed_positions: List[UUID] = []
        
        # Trade statistics
        self._total_trades = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._largest_win = Money.zero(account_currency)
        self._largest_loss = Money.zero(account_currency)
        
        # Daily tracking
        self._last_daily_calculation: Optional[datetime] = None
        self._trading_days = 0
        
        self._touch()
    
    def record_trade(self, trade: Trade) -> None:
        """Record a trade execution."""
        self._total_trades += 1
        self._total_commission += trade.commission.amount
        self._touch()
    
    def record_position_opened(self, position: Position) -> None:
        """Record a new position opening."""
        self._open_positions.append(position.id)
        self._touch()
    
    def record_position_closed(self, position: Position, realized_pnl: PnL) -> None:
        """Record a position closing."""
        if position.id in self._open_positions:
            self._open_positions.remove(position.id)
        
        self._closed_positions.append(position.id)
        self._total_realized_pnl += realized_pnl.amount
        
        # Update trade statistics
        if realized_pnl.is_profit:
            self._winning_trades += 1
            if realized_pnl.amount > self._largest_win:
                self._largest_win = realized_pnl.amount
        else:
            self._losing_trades += 1
            if realized_pnl.amount < self._largest_loss:
                self._largest_loss = realized_pnl.amount
        
        self._touch()
    
    def update_unrealized_pnl(self, total_unrealized: Money) -> None:
        """Update total unrealized P&L from all open positions."""
        self._total_unrealized_pnl = total_unrealized
        self._touch()
    
    def calculate_daily_pnl(self, date: datetime) -> Money:
        """Calculate daily P&L and emit event."""
        # This would typically be called by a service that aggregates
        # all P&L changes for the day
        
        current_total_pnl = self._total_realized_pnl + self._total_unrealized_pnl
        
        if self._last_daily_calculation:
            # Calculate change since last calculation
            # This is simplified - in practice, you'd track daily snapshots
            self._daily_pnl = current_total_pnl  # Simplified
        else:
            self._daily_pnl = current_total_pnl
        
        self._last_daily_calculation = date
        self._trading_days += 1
        self._touch()
        
        # Emit daily P&L event
        self.add_domain_event(
            DailyPnLCalculated(
                aggregate_id=self.id,
                user_id=self._user_id,
                date=date.date().isoformat(),
                daily_pnl=str(self._daily_pnl.amount),
                total_realized_pnl=str(self._total_realized_pnl.amount),
                total_unrealized_pnl=str(self._total_unrealized_pnl.amount),
                total_pnl=str(current_total_pnl.amount),
                current_balance=str(self.current_balance.amount),
                total_trades=self._total_trades,
                winning_trades=self._winning_trades,
                losing_trades=self._losing_trades,
                trading_days=self._trading_days,
            )
        )
        
        return self._daily_pnl
    
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def account_currency(self) -> str:
        return self._account_currency
    
    @property
    def initial_balance(self) -> Money:
        return self._initial_balance
    
    @property
    def current_balance(self) -> Money:
        return self._initial_balance + self._total_realized_pnl + self._total_unrealized_pnl
    
    @property
    def total_realized_pnl(self) -> Money:
        return self._total_realized_pnl
    
    @property
    def total_unrealized_pnl(self) -> Money:
        return self._total_unrealized_pnl
    
    @property
    def total_pnl(self) -> Money:
        return self._total_realized_pnl + self._total_unrealized_pnl
    
    @property
    def daily_pnl(self) -> Money:
        return self._daily_pnl
    
    @property
    def total_commission(self) -> Money:
        return self._total_commission
    
    @property
    def open_positions(self) -> List[UUID]:
        return self._open_positions.copy()
    
    @property
    def closed_positions(self) -> List[UUID]:
        return self._closed_positions.copy()
    
    @property
    def total_trades(self) -> int:
        return self._total_trades
    
    @property
    def winning_trades(self) -> int:
        return self._winning_trades
    
    @property
    def losing_trades(self) -> int:
        return self._losing_trades
    
    @property
    def win_rate(self) -> Decimal:
        if self._total_trades == 0:
            return Decimal("0")
        return Decimal(self._winning_trades) / Decimal(self._total_trades) * 100
    
    @property
    def largest_win(self) -> Money:
        return self._largest_win
    
    @property
    def largest_loss(self) -> Money:
        return self._largest_loss
    
    @property
    def trading_days(self) -> int:
        return self._trading_days