"""Trading API schemas for trades and positions."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TradeExecutionRequest(BaseModel):
    """Request to execute a trade."""
    trade_id: str = Field(..., description="Unique trade identifier")
    user_id: UUID = Field(..., description="User ID")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Order side (BUY/SELL)")
    quantity: Decimal = Field(..., description="Trade quantity")
    price: Decimal = Field(..., description="Execution price")
    order_id: UUID = Field(..., description="Source order ID")
    fill_id: str = Field(..., description="Fill identifier")
    commission: Optional[Decimal] = Field(None, description="Commission amount")
    currency: str = Field("USD", description="Currency")


class TradeResponse(BaseModel):
    """Trade response schema."""
    id: UUID = Field(..., description="Trade ID")
    trade_id: str = Field(..., description="Trade identifier")
    user_id: UUID = Field(..., description="User ID")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Order side")
    quantity: Decimal = Field(..., description="Trade quantity")
    price: Decimal = Field(..., description="Execution price")
    gross_value: Decimal = Field(..., description="Gross trade value")
    net_value: Decimal = Field(..., description="Net trade value after commission")
    commission: Decimal = Field(..., description="Commission paid")
    currency: str = Field(..., description="Currency")
    order_id: UUID = Field(..., description="Source order ID")
    fill_id: str = Field(..., description="Fill identifier")
    trade_type: str = Field(..., description="Trade type")
    executed_at: datetime = Field(..., description="Execution timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")


class PositionResponse(BaseModel):
    """Position response schema."""
    id: UUID = Field(..., description="Position ID")
    user_id: UUID = Field(..., description="User ID")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Position side (LONG/SHORT)")
    quantity: Decimal = Field(..., description="Position quantity")
    entry_price: Decimal = Field(..., description="Average entry price")
    entry_value: Decimal = Field(..., description="Entry value")
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    realized_pnl: Decimal = Field(..., description="Realized P&L")
    unrealized_pnl: Decimal = Field(..., description="Unrealized P&L")
    total_pnl: Decimal = Field(..., description="Total P&L")
    total_commission: Decimal = Field(..., description="Total commission paid")
    currency: str = Field(..., description="Currency")
    is_open: bool = Field(..., description="Whether position is open")
    opened_at: datetime = Field(..., description="Position open timestamp")
    closed_at: Optional[datetime] = Field(None, description="Position close timestamp")
    opening_trade_id: UUID = Field(..., description="Opening trade ID")
    closing_trade_id: Optional[UUID] = Field(None, description="Closing trade ID")
    trade_count: int = Field(..., description="Number of trades in position")


class TradingAccountResponse(BaseModel):
    """Trading account response schema."""
    id: UUID = Field(..., description="Account ID")
    user_id: UUID = Field(..., description="User ID")
    account_currency: str = Field(..., description="Account currency")
    initial_balance: Decimal = Field(..., description="Initial balance")
    current_balance: Decimal = Field(..., description="Current balance")
    total_realized_pnl: Decimal = Field(..., description="Total realized P&L")
    total_unrealized_pnl: Decimal = Field(..., description="Total unrealized P&L")
    total_pnl: Decimal = Field(..., description="Total P&L")
    daily_pnl: Decimal = Field(..., description="Daily P&L")
    total_commission: Decimal = Field(..., description="Total commission paid")
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    largest_win: Decimal = Field(..., description="Largest winning trade")
    largest_loss: Decimal = Field(..., description="Largest losing trade")
    trading_days: int = Field(..., description="Number of trading days")


class PriceUpdateRequest(BaseModel):
    """Request to update position prices."""
    symbol: str = Field(..., description="Trading symbol")
    price: Decimal = Field(..., description="Current market price")
    currency: str = Field("USD", description="Currency")


class PnLCalculationResponse(BaseModel):
    """P&L calculation response."""
    position_id: UUID = Field(..., description="Position ID")
    symbol: str = Field(..., description="Trading symbol")
    unrealized_pnl: Decimal = Field(..., description="Unrealized P&L")
    total_pnl: Decimal = Field(..., description="Total P&L")
    pnl_percentage: Decimal = Field(..., description="P&L percentage")
    current_price: Decimal = Field(..., description="Current price used")


class DailyPnLResponse(BaseModel):
    """Daily P&L response schema."""
    user_id: UUID = Field(..., description="User ID")
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    daily_pnl: Decimal = Field(..., description="Daily P&L")
    total_realized_pnl: Decimal = Field(..., description="Total realized P&L")
    total_unrealized_pnl: Decimal = Field(..., description="Total unrealized P&L")
    total_pnl: Decimal = Field(..., description="Total P&L")
    current_balance: Decimal = Field(..., description="Current balance")
    daily_trades: int = Field(..., description="Trades executed today")
    daily_winning_trades: int = Field(..., description="Winning trades today")
    daily_losing_trades: int = Field(..., description="Losing trades today")
    daily_commission: Decimal = Field(..., description="Commission paid today")
    total_trades: int = Field(..., description="Total trades")
    winning_trades: int = Field(..., description="Total winning trades")
    losing_trades: int = Field(..., description="Total losing trades")
    trading_days: int = Field(..., description="Total trading days")


class TradingMetricsResponse(BaseModel):
    """Trading metrics response schema."""
    user_id: UUID = Field(..., description="User ID")
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    profit_factor: Decimal = Field(..., description="Profit factor")
    total_pnl: Decimal = Field(..., description="Total P&L")
    total_commission: Decimal = Field(..., description="Total commission")
    largest_win: Decimal = Field(..., description="Largest winning trade")
    largest_loss: Decimal = Field(..., description="Largest losing trade")
    average_win: Decimal = Field(..., description="Average winning trade")
    average_loss: Decimal = Field(..., description="Average losing trade")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    trading_days: int = Field(..., description="Number of trading days")
    average_trades_per_day: Decimal = Field(..., description="Average trades per day")


class PositionSummaryResponse(BaseModel):
    """Position summary response."""
    user_id: UUID = Field(..., description="User ID")
    open_positions: int = Field(..., description="Number of open positions")
    closed_positions: int = Field(..., description="Number of closed positions")
    total_unrealized_pnl: Decimal = Field(..., description="Total unrealized P&L")
    total_realized_pnl: Decimal = Field(..., description="Total realized P&L")
    largest_position_value: Decimal = Field(..., description="Largest position value")
    positions_by_symbol: dict = Field(..., description="Positions grouped by symbol")


class TradeHistoryRequest(BaseModel):
    """Request for trade history."""
    user_id: Optional[UUID] = Field(None, description="User ID filter")
    symbol: Optional[str] = Field(None, description="Symbol filter")
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    trade_type: Optional[str] = Field(None, description="Trade type filter")
    limit: int = Field(100, description="Maximum number of results")
    offset: int = Field(0, description="Results offset for pagination")


class PositionHistoryRequest(BaseModel):
    """Request for position history."""
    user_id: Optional[UUID] = Field(None, description="User ID filter")
    symbol: Optional[str] = Field(None, description="Symbol filter")
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    include_closed: bool = Field(True, description="Include closed positions")
    limit: int = Field(100, description="Maximum number of results")
    offset: int = Field(0, description="Results offset for pagination")


class ClosePositionRequest(BaseModel):
    """Request to close a position."""
    position_id: UUID = Field(..., description="Position ID to close")
    price: Decimal = Field(..., description="Closing price")
    quantity: Optional[Decimal] = Field(None, description="Quantity to close (partial close)")
    reason: str = Field("Manual close", description="Reason for closing")


class BulkPriceUpdateRequest(BaseModel):
    """Request for bulk price updates."""
    price_updates: List[PriceUpdateRequest] = Field(..., description="List of price updates")


class TradingStatsRequest(BaseModel):
    """Request for trading statistics."""
    user_id: UUID = Field(..., description="User ID")
    start_date: Optional[datetime] = Field(None, description="Start date for statistics")
    end_date: Optional[datetime] = Field(None, description="End date for statistics")
    symbol: Optional[str] = Field(None, description="Symbol filter")
    include_unrealized: bool = Field(True, description="Include unrealized P&L")


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")