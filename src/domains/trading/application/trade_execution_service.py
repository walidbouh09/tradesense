"""Trading application services for trade execution and position management."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ....shared.events.event_bus import EventBus
from ....shared.exceptions.base import BusinessRuleViolationError
from ....shared.utils.money import Money
from ..domain.entities import Order
from ..domain.trade import Position, Trade, TradingAccount
from ..domain.value_objects import (
    Commission,
    Fill,
    OrderSide,
    PositionSide,
    Price,
    Quantity,
    Symbol,
    TradeId,
    TradeType,
)


class TradeExecutionService:
    """Service for executing trades and managing positions."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def execute_trade(
        self,
        order: Order,
        fill: Fill,
        trade_id: str,
        commission_amount: Optional[Money] = None,
    ) -> Trade:
        """Execute a trade from an order fill."""
        
        # Create commission
        commission = Commission(
            amount=commission_amount or Money.zero(fill.price.value.currency),
            commission_type="FIXED",
        )
        
        # Determine trade type (this would be determined by position management logic)
        trade_type = TradeType.OPEN  # Simplified - would be determined by existing positions
        
        # Create trade
        trade = Trade(
            trade_id=TradeId(trade_id),
            user_id=order.user_id,
            symbol=order.symbol,
            side=order.side,
            quantity=Quantity(fill.quantity.value),
            price=fill.price,
            order_id=order.id,
            fill=fill,
            trade_type=trade_type,
            commission=commission,
            executed_at=datetime.utcnow(),
        )
        
        # Publish domain events
        for event in trade.domain_events:
            await self.event_bus.publish(event)
        trade.clear_domain_events()
        
        return trade
    
    async def open_position(
        self,
        trade: Trade,
    ) -> Position:
        """Open a new position from a trade."""
        
        # Determine position side
        position_side = PositionSide.LONG if trade.side == OrderSide.BUY else PositionSide.SHORT
        
        # Create position
        position = Position(
            user_id=trade.user_id,
            symbol=trade.symbol,
            side=position_side,
            opening_trade=trade,
        )
        
        # Publish domain events
        for event in position.domain_events:
            await self.event_bus.publish(event)
        position.clear_domain_events()
        
        return position
    
    async def update_position(
        self,
        position: Position,
        trade: Trade,
    ) -> Position:
        """Update an existing position with a new trade."""
        
        # Update position
        position.update_quantity(trade)
        
        # Publish domain events
        for event in position.domain_events:
            await self.event_bus.publish(event)
        position.clear_domain_events()
        
        return position
    
    async def close_position(
        self,
        position: Position,
        closing_trade: Trade,
    ) -> Position:
        """Close a position with a closing trade."""
        
        # Close position
        realized_pnl = position.close_position(closing_trade)
        
        # Publish domain events
        for event in position.domain_events:
            await self.event_bus.publish(event)
        position.clear_domain_events()
        
        return position
    
    async def update_position_price(
        self,
        position: Position,
        current_price: Price,
    ) -> Position:
        """Update position with current market price."""
        
        # Update price and calculate unrealized P&L
        unrealized_pnl = position.update_market_price(current_price)
        
        # Publish domain events
        for event in position.domain_events:
            await self.event_bus.publish(event)
        position.clear_domain_events()
        
        return position


class PositionManagementService:
    """Service for managing trading positions and determining trade types."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    def determine_trade_type(
        self,
        user_id: UUID,
        symbol: Symbol,
        side: OrderSide,
        quantity: Quantity,
        existing_positions: List[Position],
    ) -> TradeType:
        """Determine the type of trade based on existing positions."""
        
        # Find existing position for this symbol
        existing_position = None
        for pos in existing_positions:
            if pos.symbol == symbol and pos.is_open:
                existing_position = pos
                break
        
        if not existing_position:
            # No existing position - this is an opening trade
            return TradeType.OPEN
        
        # Check if trade is in same direction as position
        position_is_long = existing_position.side == PositionSide.LONG
        trade_is_buy = side == OrderSide.BUY
        
        if (position_is_long and trade_is_buy) or (not position_is_long and not trade_is_buy):
            # Same direction - increasing position
            return TradeType.INCREASE
        else:
            # Opposite direction - reducing or closing position
            if quantity >= existing_position.quantity:
                return TradeType.CLOSE
            else:
                return TradeType.REDUCE
    
    def should_create_new_position(
        self,
        trade_type: TradeType,
        trade: Trade,
        existing_position: Optional[Position],
    ) -> bool:
        """Determine if a new position should be created."""
        
        if trade_type == TradeType.OPEN:
            return True
        
        if trade_type == TradeType.CLOSE and existing_position:
            # If closing trade is larger than position, create new position for remainder
            return trade.quantity > existing_position.quantity
        
        return False


class PnLCalculationService:
    """Service for calculating P&L and updating trading accounts."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def calculate_position_pnl(
        self,
        position: Position,
        current_price: Price,
    ) -> Money:
        """Calculate current P&L for a position."""
        
        if not position.is_open:
            return position.realized_pnl
        
        # Update position with current price
        unrealized_pnl = position.update_market_price(current_price)
        
        # Publish events
        for event in position.domain_events:
            await self.event_bus.publish(event)
        position.clear_domain_events()
        
        return position.total_pnl
    
    async def calculate_account_pnl(
        self,
        account: TradingAccount,
        positions: List[Position],
        current_prices: dict[str, Price],
    ) -> Money:
        """Calculate total P&L for a trading account."""
        
        total_unrealized = Money.zero(account.account_currency)
        
        # Calculate unrealized P&L for all open positions
        for position in positions:
            if position.is_open and str(position.symbol) in current_prices:
                current_price = current_prices[str(position.symbol)]
                await self.calculate_position_pnl(position, current_price)
                total_unrealized += position.unrealized_pnl
        
        # Update account with total unrealized P&L
        account.update_unrealized_pnl(total_unrealized)
        
        # Publish events
        for event in account.domain_events:
            await self.event_bus.publish(event)
        account.clear_domain_events()
        
        return account.total_pnl
    
    async def calculate_daily_pnl(
        self,
        account: TradingAccount,
        date: datetime,
    ) -> Money:
        """Calculate daily P&L for an account."""
        
        daily_pnl = account.calculate_daily_pnl(date)
        
        # Publish events
        for event in account.domain_events:
            await self.event_bus.publish(event)
        account.clear_domain_events()
        
        return daily_pnl


class TradingMetricsService:
    """Service for calculating trading metrics and statistics."""
    
    def calculate_win_rate(self, winning_trades: int, total_trades: int) -> Decimal:
        """Calculate win rate percentage."""
        if total_trades == 0:
            return Decimal("0")
        return Decimal(winning_trades) / Decimal(total_trades) * 100
    
    def calculate_profit_factor(
        self,
        total_wins: Money,
        total_losses: Money,
    ) -> Decimal:
        """Calculate profit factor (total wins / total losses)."""
        if total_losses.amount == 0:
            return Decimal("0") if total_wins.amount == 0 else Decimal("999")
        
        return abs(total_wins.amount / total_losses.amount)
    
    def calculate_sharpe_ratio(
        self,
        returns: List[Decimal],
        risk_free_rate: Decimal = Decimal("0"),
    ) -> Decimal:
        """Calculate Sharpe ratio for returns."""
        if not returns or len(returns) < 2:
            return Decimal("0")
        
        # Calculate mean return
        mean_return = sum(returns) / len(returns)
        
        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance.sqrt() if variance > 0 else Decimal("0")
        
        if std_dev == 0:
            return Decimal("0")
        
        return (mean_return - risk_free_rate) / std_dev
    
    def calculate_max_drawdown(self, equity_curve: List[Money]) -> Money:
        """Calculate maximum drawdown from equity curve."""
        if not equity_curve:
            return Money.zero()
        
        peak = equity_curve[0]
        max_drawdown = Money.zero(equity_curve[0].currency)
        
        for value in equity_curve:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def calculate_average_trade_duration(
        self,
        positions: List[Position],
    ) -> Optional[int]:
        """Calculate average trade duration in seconds."""
        closed_positions = [p for p in positions if not p.is_open and p.closed_at]
        
        if not closed_positions:
            return None
        
        total_duration = sum(
            int((p.closed_at - p.opened_at).total_seconds())
            for p in closed_positions
        )
        
        return total_duration // len(closed_positions)