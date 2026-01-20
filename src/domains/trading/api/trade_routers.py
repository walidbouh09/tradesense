"""Trading API routers for trade execution and position management."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ....infrastructure.database.connection import get_db_session
from ....infrastructure.security.auth import get_current_user
from ....shared.events.event_bus import get_event_bus
from ....shared.utils.money import Money
from ..application.trade_execution_service import (
    PnLCalculationService,
    PositionManagementService,
    TradeExecutionService,
    TradingMetricsService,
)
from ..domain.value_objects import Fill, Price, Quantity, Symbol
from ..infrastructure.trade_repositories import (
    DailyPnLRepository,
    PositionRepository,
    TradingAccountRepository,
    TradeRepository,
)
from .trade_schemas import (
    BulkPriceUpdateRequest,
    ClosePositionRequest,
    DailyPnLResponse,
    ErrorResponse,
    PnLCalculationResponse,
    PositionHistoryRequest,
    PositionResponse,
    PositionSummaryResponse,
    PriceUpdateRequest,
    TradeExecutionRequest,
    TradeHistoryRequest,
    TradeResponse,
    TradingAccountResponse,
    TradingMetricsResponse,
    TradingStatsRequest,
)

router = APIRouter(prefix="/trading", tags=["Trading"])


@router.post("/trades/execute", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
async def execute_trade(
    request: TradeExecutionRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Execute a trade from order fill."""
    try:
        # Get repositories and services
        trade_repo = TradeRepository(db)
        event_bus = get_event_bus()
        execution_service = TradeExecutionService(event_bus)
        
        # Check if trade already exists
        existing_trade = trade_repo.find_by_trade_id(request.trade_id)
        if existing_trade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Trade {request.trade_id} already exists"
            )
        
        # Create fill object
        fill = Fill(
            quantity=Quantity(request.quantity),
            price=Price(Money(request.price, request.currency)),
            fill_id=request.fill_id,
            timestamp=datetime.utcnow().isoformat(),
            commission=Money(request.commission or 0, request.currency),
        )
        
        # Create mock order (in practice, this would be loaded from order repository)
        from ..domain.entities import Order
        from ..domain.value_objects import OrderSide, OrderType, TimeInForce
        
        order = Order(
            user_id=request.user_id,
            symbol=Symbol(request.symbol),
            side=OrderSide(request.side),
            order_type=OrderType.MARKET,  # Simplified
            quantity=Quantity(request.quantity),
            time_in_force=TimeInForce.GTC,
            id=request.order_id,
        )
        
        # Execute trade
        trade = await execution_service.execute_trade(
            order=order,
            fill=fill,
            trade_id=request.trade_id,
            commission_amount=Money(request.commission or 0, request.currency),
        )
        
        # Save trade
        saved_trade = trade_repo.save(trade)
        db.commit()
        
        # Convert to response
        return TradeResponse(
            id=saved_trade.id,
            trade_id=str(saved_trade.trade_id),
            user_id=saved_trade.user_id,
            symbol=str(saved_trade.symbol),
            side=saved_trade.side.value,
            quantity=saved_trade.quantity.value,
            price=saved_trade.price.value.amount,
            gross_value=saved_trade.gross_value.amount,
            net_value=saved_trade.net_value.amount,
            commission=saved_trade.commission.amount.amount,
            currency=saved_trade.price.value.currency,
            order_id=saved_trade.order_id,
            fill_id=saved_trade.fill.fill_id,
            trade_type=saved_trade.trade_type.value,
            executed_at=saved_trade.executed_at,
            created_at=saved_trade.created_at,
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute trade: {str(e)}"
        )


@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(100, description="Maximum results"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get trade history with filters."""
    try:
        trade_repo = TradeRepository(db)
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Get trades based on filters
        if start_date and end_date:
            trades = trade_repo.find_by_user_and_date_range(user_id, start_date, end_date)
        elif symbol:
            trades = trade_repo.find_by_user_and_symbol(user_id, symbol, limit)
        else:
            trades = trade_repo.find_by_user_id(user_id)[:limit]
        
        # Convert to response
        return [
            TradeResponse(
                id=trade.id,
                trade_id=str(trade.trade_id),
                user_id=trade.user_id,
                symbol=str(trade.symbol),
                side=trade.side.value,
                quantity=trade.quantity.value,
                price=trade.price.value.amount,
                gross_value=trade.gross_value.amount,
                net_value=trade.net_value.amount,
                commission=trade.commission.amount.amount,
                currency=trade.price.value.currency,
                order_id=trade.order_id,
                fill_id=trade.fill.fill_id,
                trade_type=trade.trade_type.value,
                executed_at=trade.executed_at,
                created_at=trade.created_at,
            )
            for trade in trades
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trades: {str(e)}"
        )


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    include_closed: bool = Query(False, description="Include closed positions"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get positions with filters."""
    try:
        position_repo = PositionRepository(db)
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Get positions based on filters
        if symbol:
            positions = position_repo.find_by_user_and_symbol(user_id, symbol, include_closed)
        elif include_closed:
            # Get all positions for user
            positions = position_repo.find_by_user_id(user_id)
        else:
            # Get only open positions
            positions = position_repo.find_open_positions_by_user(user_id)
        
        # Convert to response
        return [
            PositionResponse(
                id=position.id,
                user_id=position.user_id,
                symbol=str(position.symbol),
                side=position.side.value,
                quantity=position.quantity.value,
                entry_price=position.entry_price.value.amount,
                entry_value=position.entry_value.amount,
                current_price=position.current_price.value.amount if position.current_price else None,
                realized_pnl=position.realized_pnl.amount,
                unrealized_pnl=position.unrealized_pnl.amount,
                total_pnl=position.total_pnl.amount,
                total_commission=position.total_commission.amount,
                currency=position.entry_price.value.currency,
                is_open=position.is_open,
                opened_at=position.opened_at,
                closed_at=position.closed_at,
                opening_trade_id=position.opening_trade_id,
                closing_trade_id=position.closing_trade_id,
                trade_count=len(position.trades),
            )
            for position in positions
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {str(e)}"
        )


@router.post("/positions/{position_id}/close", response_model=PositionResponse)
async def close_position(
    position_id: UUID,
    request: ClosePositionRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Close a position."""
    try:
        position_repo = PositionRepository(db)
        event_bus = get_event_bus()
        execution_service = TradeExecutionService(event_bus)
        
        # Find position
        position = position_repo.find_by_id(position_id)
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position {position_id} not found"
            )
        
        if not position.is_open:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Position is already closed"
            )
        
        # Create closing trade (simplified - in practice would come from order execution)
        from ..domain.trade import Trade
        from ..domain.value_objects import OrderSide, TradeId, TradeType
        from uuid import uuid4
        
        # Determine closing side (opposite of position)
        closing_side = OrderSide.SELL if position.side.value == "LONG" else OrderSide.BUY
        
        # Create closing fill
        closing_quantity = Quantity(request.quantity or position.quantity.value)
        closing_fill = Fill(
            quantity=closing_quantity,
            price=Price(Money(request.price, position.entry_price.value.currency)),
            fill_id=f"close_{position_id}",
            timestamp=datetime.utcnow().isoformat(),
        )
        
        # Create closing trade
        closing_trade = Trade(
            trade_id=TradeId(f"close_trade_{position_id}"),
            user_id=position.user_id,
            symbol=position.symbol,
            side=closing_side,
            quantity=closing_quantity,
            price=Price(Money(request.price, position.entry_price.value.currency)),
            order_id=uuid4(),
            fill=closing_fill,
            trade_type=TradeType.CLOSE,
            executed_at=datetime.utcnow(),
        )
        
        # Close position
        updated_position = await execution_service.close_position(position, closing_trade)
        
        # Save position
        saved_position = position_repo.save(updated_position)
        db.commit()
        
        # Convert to response
        return PositionResponse(
            id=saved_position.id,
            user_id=saved_position.user_id,
            symbol=str(saved_position.symbol),
            side=saved_position.side.value,
            quantity=saved_position.quantity.value,
            entry_price=saved_position.entry_price.value.amount,
            entry_value=saved_position.entry_value.amount,
            current_price=saved_position.current_price.value.amount if saved_position.current_price else None,
            realized_pnl=saved_position.realized_pnl.amount,
            unrealized_pnl=saved_position.unrealized_pnl.amount,
            total_pnl=saved_position.total_pnl.amount,
            total_commission=saved_position.total_commission.amount,
            currency=saved_position.entry_price.value.currency,
            is_open=saved_position.is_open,
            opened_at=saved_position.opened_at,
            closed_at=saved_position.closed_at,
            opening_trade_id=saved_position.opening_trade_id,
            closing_trade_id=saved_position.closing_trade_id,
            trade_count=len(saved_position.trades),
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close position: {str(e)}"
        )


@router.post("/positions/update-prices", response_model=List[PnLCalculationResponse])
async def update_position_prices(
    request: BulkPriceUpdateRequest,
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Update position prices and calculate P&L."""
    try:
        position_repo = PositionRepository(db)
        event_bus = get_event_bus()
        execution_service = TradeExecutionService(event_bus)
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Get open positions for user
        positions = position_repo.find_open_positions_by_user(user_id)
        
        # Create price lookup
        price_updates = {update.symbol: update for update in request.price_updates}
        
        results = []
        
        # Update prices for matching positions
        for position in positions:
            symbol_str = str(position.symbol)
            if symbol_str in price_updates:
                price_update = price_updates[symbol_str]
                new_price = Price(Money(price_update.price, price_update.currency))
                
                # Update position price
                updated_position = await execution_service.update_position_price(position, new_price)
                
                # Save position
                position_repo.save(updated_position)
                
                # Calculate P&L percentage
                pnl_percentage = (
                    updated_position.total_pnl.amount / updated_position.entry_value.amount * 100
                    if updated_position.entry_value.amount != 0 else 0
                )
                
                results.append(PnLCalculationResponse(
                    position_id=updated_position.id,
                    symbol=symbol_str,
                    unrealized_pnl=updated_position.unrealized_pnl.amount,
                    total_pnl=updated_position.total_pnl.amount,
                    pnl_percentage=pnl_percentage,
                    current_price=price_update.price,
                ))
        
        db.commit()
        return results
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update position prices: {str(e)}"
        )


@router.get("/account", response_model=TradingAccountResponse)
async def get_trading_account(
    user_id: Optional[UUID] = Query(None, description="User ID"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get trading account information."""
    try:
        account_repo = TradingAccountRepository(db)
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Find or create trading account
        account = account_repo.find_by_user_id(user_id)
        if not account:
            # Create new account
            from ..domain.trade import TradingAccount
            account = TradingAccount(user_id=user_id)
            account = account_repo.save(account)
            db.commit()
        
        # Convert to response
        return TradingAccountResponse(
            id=account.id,
            user_id=account.user_id,
            account_currency=account.account_currency,
            initial_balance=account.initial_balance.amount,
            current_balance=account.current_balance.amount,
            total_realized_pnl=account.total_realized_pnl.amount,
            total_unrealized_pnl=account.total_unrealized_pnl.amount,
            total_pnl=account.total_pnl.amount,
            daily_pnl=account.daily_pnl.amount,
            total_commission=account.total_commission.amount,
            total_trades=account.total_trades,
            winning_trades=account.winning_trades,
            losing_trades=account.losing_trades,
            win_rate=account.win_rate,
            largest_win=account.largest_win.amount,
            largest_loss=account.largest_loss.amount,
            trading_days=account.trading_days,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading account: {str(e)}"
        )


@router.get("/metrics", response_model=TradingMetricsResponse)
async def get_trading_metrics(
    user_id: Optional[UUID] = Query(None, description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get comprehensive trading metrics."""
    try:
        trade_repo = TradeRepository(db)
        position_repo = PositionRepository(db)
        metrics_service = TradingMetricsService()
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Get trades and positions
        if start_date and end_date:
            trades = trade_repo.find_by_user_and_date_range(user_id, start_date, end_date)
            positions = position_repo.find_positions_by_date_range(user_id, start_date, end_date)
        else:
            trades = trade_repo.find_by_user_id(user_id)
            positions = position_repo.find_by_user_id(user_id)
        
        # Calculate metrics
        closed_positions = [p for p in positions if not p.is_open]
        winning_positions = [p for p in closed_positions if p.realized_pnl.amount > 0]
        losing_positions = [p for p in closed_positions if p.realized_pnl.amount < 0]
        
        total_wins = sum(p.realized_pnl.amount for p in winning_positions)
        total_losses = sum(abs(p.realized_pnl.amount) for p in losing_positions)
        
        win_rate = metrics_service.calculate_win_rate(len(winning_positions), len(closed_positions))
        profit_factor = metrics_service.calculate_profit_factor(
            Money(total_wins, "USD"),
            Money(total_losses, "USD")
        )
        
        # Calculate equity curve for max drawdown
        equity_curve = []
        running_pnl = 0
        for position in sorted(closed_positions, key=lambda x: x.closed_at or datetime.min):
            running_pnl += position.realized_pnl.amount
            equity_curve.append(Money(running_pnl, "USD"))
        
        max_drawdown = metrics_service.calculate_max_drawdown(equity_curve)
        
        # Calculate averages
        avg_win = total_wins / len(winning_positions) if winning_positions else 0
        avg_loss = total_losses / len(losing_positions) if losing_positions else 0
        
        # Calculate trading days
        trading_days = len(set(t.executed_at.date() for t in trades)) if trades else 0
        avg_trades_per_day = len(trades) / trading_days if trading_days > 0 else 0
        
        return TradingMetricsResponse(
            user_id=user_id,
            total_trades=len(trades),
            winning_trades=len(winning_positions),
            losing_trades=len(losing_positions),
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_pnl=sum(p.realized_pnl.amount for p in closed_positions),
            total_commission=sum(t.commission.amount.amount for t in trades),
            largest_win=max((p.realized_pnl.amount for p in winning_positions), default=0),
            largest_loss=min((p.realized_pnl.amount for p in losing_positions), default=0),
            average_win=avg_win,
            average_loss=avg_loss,
            max_drawdown=max_drawdown.amount,
            sharpe_ratio=None,  # Would need returns data
            trading_days=trading_days,
            average_trades_per_day=avg_trades_per_day,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading metrics: {str(e)}"
        )


@router.get("/daily-pnl", response_model=List[DailyPnLResponse])
async def get_daily_pnl(
    user_id: Optional[UUID] = Query(None, description="User ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(30, description="Maximum results"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get daily P&L history."""
    try:
        daily_pnl_repo = DailyPnLRepository(db)
        
        # Use current user if no user_id specified
        if not user_id:
            user_id = UUID(current_user["user_id"])
        
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            from datetime import timedelta
            start_date = end_date - timedelta(days=limit)
        
        # Get daily P&L snapshots
        snapshots = daily_pnl_repo.find_by_user_and_date_range(user_id, start_date, end_date)
        
        # Convert to response
        return [
            DailyPnLResponse(
                user_id=snapshot.user_id,
                date=snapshot.date.date().isoformat(),
                daily_pnl=snapshot.daily_pnl,
                total_realized_pnl=snapshot.total_realized_pnl,
                total_unrealized_pnl=snapshot.total_unrealized_pnl,
                total_pnl=snapshot.total_pnl,
                current_balance=snapshot.current_balance,
                daily_trades=snapshot.daily_trades,
                daily_winning_trades=snapshot.daily_winning_trades,
                daily_losing_trades=snapshot.daily_losing_trades,
                daily_commission=snapshot.daily_commission,
                total_trades=snapshot.total_trades,
                winning_trades=snapshot.winning_trades,
                losing_trades=snapshot.losing_trades,
                trading_days=snapshot.trading_days,
            )
            for snapshot in snapshots
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get daily P&L: {str(e)}"
        )


@router.get("/health", response_model=dict)
async def health_check(db: Session = Depends(get_db_session)):
    """Health check endpoint."""
    try:
        # Simple database connectivity check
        db.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "service": "trading",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )