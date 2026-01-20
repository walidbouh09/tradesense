"""Trading domain repositories."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from ....infrastructure.database.base import BaseRepository
from ....shared.utils.money import Money
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
from .trade_models import (
    DailyPnLModel,
    PositionModel,
    PositionTradeModel,
    TradingAccountModel,
    TradeModel,
)


class TradeRepository(BaseRepository[Trade, TradeModel]):
    """Repository for trade aggregate."""
    
    def __init__(self, session: Session):
        super().__init__(session, TradeModel)
    
    def find_by_trade_id(self, trade_id: str) -> Optional[Trade]:
        """Find trade by trade ID."""
        model = self.session.query(TradeModel).filter(
            TradeModel.trade_id == trade_id
        ).first()
        
        return self._to_entity(model) if model else None
    
    def find_by_user_and_symbol(
        self,
        user_id: UUID,
        symbol: str,
        limit: int = 100,
    ) -> List[Trade]:
        """Find trades by user and symbol."""
        models = self.session.query(TradeModel).filter(
            and_(
                TradeModel.user_id == user_id,
                TradeModel.symbol == symbol,
            )
        ).order_by(desc(TradeModel.executed_at)).limit(limit).all()
        
        return [self._to_entity(model) for model in models]
    
    def find_by_user_and_date_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Trade]:
        """Find trades by user within date range."""
        models = self.session.query(TradeModel).filter(
            and_(
                TradeModel.user_id == user_id,
                TradeModel.executed_at >= start_date,
                TradeModel.executed_at <= end_date,
            )
        ).order_by(desc(TradeModel.executed_at)).all()
        
        return [self._to_entity(model) for model in models]
    
    def save(self, entity: Trade) -> Trade:
        """Save trade entity."""
        model = self._find_or_create_model(entity.id)
        
        # Update fields
        model.trade_id = str(entity.trade_id)
        model.user_id = entity.user_id
        model.symbol = str(entity.symbol)
        model.side = entity.side.value
        model.quantity = entity.quantity.value
        model.price = entity.price.value.amount
        model.gross_value = entity.gross_value.amount
        model.net_value = entity.net_value.amount
        model.commission = entity.commission.amount.amount
        model.currency = entity.price.value.currency
        model.order_id = entity.order_id
        model.fill_id = entity.fill.fill_id
        model.trade_type = entity.trade_type.value
        model.executed_at = entity.executed_at
        
        self.session.add(model)
        self.session.flush()
        
        return self._to_entity(model)
    
    def _to_entity(self, model: TradeModel) -> Trade:
        """Convert model to entity."""
        # Reconstruct Fill
        fill = Fill(
            quantity=Quantity(model.quantity),
            price=Price(Money(model.price, model.currency)),
            fill_id=model.fill_id,
            timestamp=model.executed_at.isoformat(),
        )
        
        # Reconstruct Commission
        commission = Commission(
            amount=Money(model.commission, model.currency),
            commission_type="FIXED",
        )
        
        # Create entity
        entity = Trade(
            trade_id=TradeId(model.trade_id),
            user_id=model.user_id,
            symbol=Symbol(model.symbol),
            side=OrderSide(model.side),
            quantity=Quantity(model.quantity),
            price=Price(Money(model.price, model.currency)),
            order_id=model.order_id,
            fill=fill,
            trade_type=TradeType(model.trade_type),
            commission=commission,
            executed_at=model.executed_at,
            id=model.id,
        )
        
        # Clear domain events (already persisted)
        entity.clear_domain_events()
        
        return entity


class PositionRepository(BaseRepository[Position, PositionModel]):
    """Repository for position aggregate."""
    
    def __init__(self, session: Session):
        super().__init__(session, PositionModel)
    
    def find_open_positions_by_user(self, user_id: UUID) -> List[Position]:
        """Find all open positions for a user."""
        models = self.session.query(PositionModel).filter(
            and_(
                PositionModel.user_id == user_id,
                PositionModel.is_open == True,
            )
        ).all()
        
        return [self._to_entity(model) for model in models]
    
    def find_by_user_and_symbol(
        self,
        user_id: UUID,
        symbol: str,
        include_closed: bool = False,
    ) -> List[Position]:
        """Find positions by user and symbol."""
        query = self.session.query(PositionModel).filter(
            and_(
                PositionModel.user_id == user_id,
                PositionModel.symbol == symbol,
            )
        )
        
        if not include_closed:
            query = query.filter(PositionModel.is_open == True)
        
        models = query.order_by(desc(PositionModel.opened_at)).all()
        return [self._to_entity(model) for model in models]
    
    def find_positions_by_date_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Position]:
        """Find positions opened within date range."""
        models = self.session.query(PositionModel).filter(
            and_(
                PositionModel.user_id == user_id,
                PositionModel.opened_at >= start_date,
                PositionModel.opened_at <= end_date,
            )
        ).order_by(desc(PositionModel.opened_at)).all()
        
        return [self._to_entity(model) for model in models]
    
    def save(self, entity: Position) -> Position:
        """Save position entity."""
        model = self._find_or_create_model(entity.id)
        
        # Update fields
        model.user_id = entity.user_id
        model.symbol = str(entity.symbol)
        model.side = entity.side.value
        model.quantity = entity.quantity.value
        model.entry_price = entity.entry_price.value.amount
        model.entry_value = entity.entry_value.amount
        model.currency = entity.entry_price.value.currency
        model.realized_pnl = entity.realized_pnl.amount
        model.unrealized_pnl = entity.unrealized_pnl.amount
        model.total_commission = entity.total_commission.amount
        model.is_open = entity.is_open
        model.opened_at = entity.opened_at
        model.closed_at = entity.closed_at
        model.opening_trade_id = entity.opening_trade_id
        model.closing_trade_id = entity.closing_trade_id
        
        if entity.current_price:
            model.current_price = entity.current_price.value.amount
        
        self.session.add(model)
        
        # Handle position-trade relationships
        self._sync_position_trades(model, entity.trades)
        
        self.session.flush()
        
        return self._to_entity(model)
    
    def _sync_position_trades(self, model: PositionModel, trade_ids: List[UUID]) -> None:
        """Synchronize position-trade relationships."""
        # Get existing relationships
        existing = {pt.trade_id: pt for pt in model.trades}
        
        # Add new relationships
        for i, trade_id in enumerate(trade_ids):
            if trade_id not in existing:
                pt_model = PositionTradeModel(
                    position_id=model.id,
                    trade_id=trade_id,
                    trade_sequence=i,
                )
                self.session.add(pt_model)
    
    def _to_entity(self, model: PositionModel) -> Position:
        """Convert model to entity."""
        # This is a simplified reconstruction - in practice, you'd need
        # to reconstruct the opening trade from the trade repository
        
        # Create a mock opening trade for entity creation
        # In practice, this would be loaded from TradeRepository
        from ..domain.trade import Trade
        from uuid import uuid4
        
        # Create minimal trade data for position reconstruction
        opening_trade_data = {
            'trade_id': TradeId(f"trade_{model.opening_trade_id}"),
            'user_id': model.user_id,
            'symbol': Symbol(model.symbol),
            'side': OrderSide.BUY if model.side == PositionSide.LONG.value else OrderSide.SELL,
            'quantity': Quantity(model.quantity),
            'price': Price(Money(model.entry_price, model.currency)),
            'order_id': uuid4(),  # Mock order ID
            'fill': Fill(
                quantity=Quantity(model.quantity),
                price=Price(Money(model.entry_price, model.currency)),
                fill_id=f"fill_{model.opening_trade_id}",
            ),
            'commission': Commission(Money.zero(model.currency)),
            'executed_at': model.opened_at,
            'id': model.opening_trade_id,
        }
        
        # Create position entity
        entity = Position(
            user_id=model.user_id,
            symbol=Symbol(model.symbol),
            side=PositionSide(model.side),
            opening_trade=None,  # Would be properly reconstructed in practice
            id=model.id,
        )
        
        # Set internal state directly (not ideal, but necessary for reconstruction)
        entity._quantity = Quantity(model.quantity)
        entity._entry_price = Price(Money(model.entry_price, model.currency))
        entity._entry_value = Money(model.entry_value, model.currency)
        entity._realized_pnl = Money(model.realized_pnl, model.currency)
        entity._unrealized_pnl = Money(model.unrealized_pnl, model.currency)
        entity._total_commission = Money(model.total_commission, model.currency)
        entity._is_open = model.is_open
        entity._opened_at = model.opened_at
        entity._closed_at = model.closed_at
        entity._opening_trade_id = model.opening_trade_id
        entity._closing_trade_id = model.closing_trade_id
        
        if model.current_price:
            entity._current_price = Price(Money(model.current_price, model.currency))
        
        # Reconstruct trade list
        entity._trades = [pt.trade_id for pt in sorted(model.trades, key=lambda x: x.trade_sequence)]
        
        # Clear domain events
        entity.clear_domain_events()
        
        return entity


class TradingAccountRepository(BaseRepository[TradingAccount, TradingAccountModel]):
    """Repository for trading account aggregate."""
    
    def __init__(self, session: Session):
        super().__init__(session, TradingAccountModel)
    
    def find_by_user_id(self, user_id: UUID) -> Optional[TradingAccount]:
        """Find trading account by user ID."""
        model = self.session.query(TradingAccountModel).filter(
            TradingAccountModel.user_id == user_id
        ).first()
        
        return self._to_entity(model) if model else None
    
    def save(self, entity: TradingAccount) -> TradingAccount:
        """Save trading account entity."""
        model = self._find_or_create_model(entity.id)
        
        # Update fields
        model.user_id = entity.user_id
        model.account_currency = entity.account_currency
        model.initial_balance = entity.initial_balance.amount
        model.current_balance = entity.current_balance.amount
        model.total_realized_pnl = entity.total_realized_pnl.amount
        model.total_unrealized_pnl = entity.total_unrealized_pnl.amount
        model.daily_pnl = entity.daily_pnl.amount
        model.total_commission = entity.total_commission.amount
        model.total_trades = entity.total_trades
        model.winning_trades = entity.winning_trades
        model.losing_trades = entity.losing_trades
        model.largest_win = entity.largest_win.amount
        model.largest_loss = entity.largest_loss.amount
        model.trading_days = entity.trading_days
        model.last_daily_calculation = entity._last_daily_calculation
        
        self.session.add(model)
        self.session.flush()
        
        return self._to_entity(model)
    
    def _to_entity(self, model: TradingAccountModel) -> TradingAccount:
        """Convert model to entity."""
        entity = TradingAccount(
            user_id=model.user_id,
            account_currency=model.account_currency,
            initial_balance=Money(model.initial_balance, model.account_currency),
            id=model.id,
        )
        
        # Set internal state
        entity._total_realized_pnl = Money(model.total_realized_pnl, model.account_currency)
        entity._total_unrealized_pnl = Money(model.total_unrealized_pnl, model.account_currency)
        entity._daily_pnl = Money(model.daily_pnl, model.account_currency)
        entity._total_commission = Money(model.total_commission, model.account_currency)
        entity._total_trades = model.total_trades
        entity._winning_trades = model.winning_trades
        entity._losing_trades = model.losing_trades
        entity._largest_win = Money(model.largest_win, model.account_currency)
        entity._largest_loss = Money(model.largest_loss, model.account_currency)
        entity._trading_days = model.trading_days
        entity._last_daily_calculation = model.last_daily_calculation
        
        # Clear domain events
        entity.clear_domain_events()
        
        return entity


class DailyPnLRepository(BaseRepository[None, DailyPnLModel]):
    """Repository for daily P&L snapshots."""
    
    def __init__(self, session: Session):
        super().__init__(session, DailyPnLModel)
    
    def save_daily_snapshot(
        self,
        user_id: UUID,
        trading_account_id: UUID,
        date: datetime,
        daily_pnl: Money,
        total_realized_pnl: Money,
        total_unrealized_pnl: Money,
        current_balance: Money,
        daily_trades: int,
        daily_winning_trades: int,
        daily_losing_trades: int,
        daily_commission: Money,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        trading_days: int,
    ) -> DailyPnLModel:
        """Save daily P&L snapshot."""
        
        model = DailyPnLModel(
            user_id=user_id,
            trading_account_id=trading_account_id,
            date=date,
            daily_pnl=daily_pnl.amount,
            total_realized_pnl=total_realized_pnl.amount,
            total_unrealized_pnl=total_unrealized_pnl.amount,
            total_pnl=(total_realized_pnl + total_unrealized_pnl).amount,
            current_balance=current_balance.amount,
            daily_trades=daily_trades,
            daily_winning_trades=daily_winning_trades,
            daily_losing_trades=daily_losing_trades,
            daily_commission=daily_commission.amount,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            trading_days=trading_days,
        )
        
        self.session.add(model)
        self.session.flush()
        
        return model
    
    def find_by_user_and_date_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> List[DailyPnLModel]:
        """Find daily P&L snapshots by user and date range."""
        return self.session.query(DailyPnLModel).filter(
            and_(
                DailyPnLModel.user_id == user_id,
                DailyPnLModel.date >= start_date,
                DailyPnLModel.date <= end_date,
            )
        ).order_by(DailyPnLModel.date).all()
    
    def get_latest_snapshot(self, user_id: UUID) -> Optional[DailyPnLModel]:
        """Get the latest daily P&L snapshot for a user."""
        return self.session.query(DailyPnLModel).filter(
            DailyPnLModel.user_id == user_id
        ).order_by(desc(DailyPnLModel.date)).first()