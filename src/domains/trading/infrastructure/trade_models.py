"""Trading domain database models for trades and positions."""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, 
    Numeric, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ....infrastructure.database.base import BaseModel


class TradeModel(BaseModel):
    """Trade database model."""
    
    __tablename__ = "trades"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    trade_id = Column(String(100), nullable=False, unique=True, index=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    gross_value = Column(Numeric(20, 8), nullable=False)
    net_value = Column(Numeric(20, 8), nullable=False)
    commission = Column(Numeric(20, 8), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    
    # Order and fill references
    order_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    fill_id = Column(String(100), nullable=False)
    
    # Trade classification
    trade_type = Column(String(20), nullable=False)  # OPEN, CLOSE, INCREASE, REDUCE
    
    # Timestamps
    executed_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    positions = relationship("PositionTradeModel", back_populates="trade")


class PositionModel(BaseModel):
    """Position database model."""
    
    __tablename__ = "positions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # LONG, SHORT
    
    # Position details
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    entry_value = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    
    # P&L tracking
    realized_pnl = Column(Numeric(20, 8), nullable=False, default=0)
    unrealized_pnl = Column(Numeric(20, 8), nullable=False, default=0)
    total_commission = Column(Numeric(20, 8), nullable=False, default=0)
    
    # Position state
    is_open = Column(Boolean, nullable=False, default=True, index=True)
    opened_at = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True, index=True)
    
    # Trade references
    opening_trade_id = Column(PG_UUID(as_uuid=True), nullable=False)
    closing_trade_id = Column(PG_UUID(as_uuid=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    trades = relationship("PositionTradeModel", back_populates="position")


class PositionTradeModel(BaseModel):
    """Junction table linking positions to trades."""
    
    __tablename__ = "position_trades"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    position_id = Column(PG_UUID(as_uuid=True), ForeignKey("positions.id"), nullable=False)
    trade_id = Column(PG_UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False)
    trade_sequence = Column(Integer, nullable=False)  # Order of trades in position
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    position = relationship("PositionModel", back_populates="trades")
    trade = relationship("TradeModel", back_populates="positions")


class TradingAccountModel(BaseModel):
    """Trading account database model."""
    
    __tablename__ = "trading_accounts"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True)
    account_currency = Column(String(3), nullable=False, default="USD")
    
    # Balance tracking
    initial_balance = Column(Numeric(20, 8), nullable=False, default=0)
    current_balance = Column(Numeric(20, 8), nullable=False, default=0)
    
    # P&L tracking
    total_realized_pnl = Column(Numeric(20, 8), nullable=False, default=0)
    total_unrealized_pnl = Column(Numeric(20, 8), nullable=False, default=0)
    daily_pnl = Column(Numeric(20, 8), nullable=False, default=0)
    total_commission = Column(Numeric(20, 8), nullable=False, default=0)
    
    # Trade statistics
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    largest_win = Column(Numeric(20, 8), nullable=False, default=0)
    largest_loss = Column(Numeric(20, 8), nullable=False, default=0)
    
    # Time tracking
    trading_days = Column(Integer, nullable=False, default=0)
    last_daily_calculation = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DailyPnLModel(BaseModel):
    """Daily P&L snapshot model."""
    
    __tablename__ = "daily_pnl"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    trading_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    
    # Daily metrics
    daily_pnl = Column(Numeric(20, 8), nullable=False)
    total_realized_pnl = Column(Numeric(20, 8), nullable=False)
    total_unrealized_pnl = Column(Numeric(20, 8), nullable=False)
    total_pnl = Column(Numeric(20, 8), nullable=False)
    current_balance = Column(Numeric(20, 8), nullable=False)
    
    # Daily statistics
    daily_trades = Column(Integer, nullable=False, default=0)
    daily_winning_trades = Column(Integer, nullable=False, default=0)
    daily_losing_trades = Column(Integer, nullable=False, default=0)
    daily_commission = Column(Numeric(20, 8), nullable=False, default=0)
    
    # Cumulative statistics
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    trading_days = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    trading_account = relationship("TradingAccountModel")


class PriceUpdateModel(BaseModel):
    """Price update model for tracking market prices."""
    
    __tablename__ = "price_updates"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    price = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    
    # Price metadata
    bid = Column(Numeric(20, 8), nullable=True)
    ask = Column(Numeric(20, 8), nullable=True)
    volume = Column(Numeric(20, 8), nullable=True)
    
    # Source information
    source = Column(String(50), nullable=False, default="MARKET")
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CommissionRuleModel(BaseModel):
    """Commission rule model for calculating trade commissions."""
    
    __tablename__ = "commission_rules"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)  # Null for default rules
    symbol = Column(String(20), nullable=True, index=True)  # Null for all symbols
    
    # Commission structure
    commission_type = Column(String(20), nullable=False)  # FIXED, PERCENTAGE, TIERED
    fixed_amount = Column(Numeric(20, 8), nullable=True)
    percentage_rate = Column(Numeric(10, 6), nullable=True)  # e.g., 0.001 for 0.1%
    minimum_commission = Column(Numeric(20, 8), nullable=True)
    maximum_commission = Column(Numeric(20, 8), nullable=True)
    
    # Tiered structure (JSON)
    tier_structure = Column(JSON, nullable=True)
    
    # Rule metadata
    currency = Column(String(3), nullable=False, default="USD")
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=0)  # Higher priority rules override lower
    
    # Timestamps
    effective_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)