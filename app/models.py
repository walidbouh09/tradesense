"""
TradeSense AI - Comprehensive Database Models

Professional trading platform models with proper relationships,
validations, and business logic for prop trading operations.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint, Index, CheckConstraint, Numeric,
    Enum as SQLEnum, event
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy
db = SQLAlchemy()


# Enums for type safety
class UserStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class UserRole(PyEnum):
    TRADER = "trader"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"


class TradeStatus(PyEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIAL = "partial"


class TradeSide(PyEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(PyEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class ChallengeStatus(PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class NotificationStatus(PyEnum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class RiskLevel(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Base Model with common fields
class BaseModel(db.Model):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)


# User Management Models
class User(BaseModel):
    __tablename__ = 'users'

    # Basic Information
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))

    # Status and Role
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.TRADER, nullable=False)

    # Profile Information
    date_of_birth = Column(DateTime)
    country = Column(String(50))
    city = Column(String(100))
    timezone = Column(String(50), default='UTC')

    # Trading Profile
    experience_level = Column(String(20), default='beginner')  # beginner, intermediate, advanced
    risk_tolerance = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM)

    # Account Status
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)

    # KYC Information
    kyc_status = Column(String(20), default='pending')  # pending, verified, rejected
    kyc_documents = Column(JSON)

    # Preferences
    preferences = Column(JSON, default=dict)

    # Relationships
    portfolios = relationship('Portfolio', back_populates='user', cascade='all, delete-orphan')
    challenges = relationship('Challenge', back_populates='user', cascade='all, delete-orphan')
    trades = relationship('Trade', back_populates='user', cascade='all, delete-orphan')
    payments = relationship('Payment', back_populates='user', cascade='all, delete-orphan')
    notifications = relationship('Notification', back_populates='user', cascade='all, delete-orphan')
    risk_assessments = relationship('RiskAssessment', back_populates='user', cascade='all, delete-orphan')

    # Constraints and Indexes
    __table_args__ = (
        Index('idx_user_email_status', 'email', 'status'),
        Index('idx_user_role_status', 'role', 'status'),
    )

    def set_password(self, password: str) -> None:
        """Set password hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)

    @hybrid_property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    @validates('email')
    def validate_email(self, key, email):
        """Validate email format."""
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError('Invalid email format')
        return email.lower()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': str(self.id),
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role.value,
            'status': self.status.value,
            'is_verified': self.is_verified,
            'experience_level': self.experience_level,
            'country': self.country,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


# Portfolio and Trading Models
class Portfolio(BaseModel):
    __tablename__ = 'portfolios'

    # Basic Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Account Balance
    initial_balance = Column(Numeric(15, 2), nullable=False, default=0)
    current_balance = Column(Numeric(15, 2), nullable=False, default=0)
    available_balance = Column(Numeric(15, 2), nullable=False, default=0)
    margin_used = Column(Numeric(15, 2), default=0)

    # Performance Metrics
    total_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    max_drawdown = Column(Numeric(5, 4), default=0)  # Percentage
    win_rate = Column(Numeric(5, 4), default=0)  # Percentage
    sharpe_ratio = Column(Numeric(10, 6), default=0)

    # Trading Statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)

    # Risk Management
    max_daily_loss = Column(Numeric(15, 2))
    max_total_loss = Column(Numeric(15, 2))
    risk_score = Column(Numeric(5, 2), default=0)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_demo = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship('User', back_populates='portfolios')
    trades = relationship('Trade', back_populates='portfolio', cascade='all, delete-orphan')
    positions = relationship('Position', back_populates='portfolio', cascade='all, delete-orphan')

    # Constraints
    __table_args__ = (
        CheckConstraint('current_balance >= 0', name='check_positive_balance'),
        CheckConstraint('initial_balance > 0', name='check_positive_initial_balance'),
        Index('idx_portfolio_user_active', 'user_id', 'is_active'),
    )

    @hybrid_property
    def return_percentage(self) -> float:
        """Calculate portfolio return percentage."""
        if self.initial_balance == 0:
            return 0
        return float((self.current_balance - self.initial_balance) / self.initial_balance * 100)

    def update_balance(self, amount: Decimal, transaction_type: str = 'trade') -> None:
        """Update portfolio balance."""
        old_balance = self.current_balance
        self.current_balance += amount
        self.available_balance = self.current_balance - self.margin_used

        # Update P&L
        if transaction_type == 'trade':
            self.total_pnl += amount
            if amount > 0:
                self.realized_pnl += amount

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'current_balance': float(self.current_balance),
            'available_balance': float(self.available_balance),
            'total_pnl': float(self.total_pnl),
            'return_percentage': self.return_percentage,
            'total_trades': self.total_trades,
            'win_rate': float(self.win_rate) if self.win_rate else 0,
            'is_active': self.is_active,
            'is_demo': self.is_demo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Trade(BaseModel):
    __tablename__ = 'trades'

    # Basic Trade Information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey('challenges.id'), nullable=True)

    # Order Details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(SQLEnum(TradeSide), nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.PENDING, nullable=False)

    # Quantities and Prices
    quantity = Column(Numeric(15, 6), nullable=False)
    executed_quantity = Column(Numeric(15, 6), default=0)
    price = Column(Numeric(15, 6))  # Limit price for limit orders
    executed_price = Column(Numeric(15, 6))
    stop_price = Column(Numeric(15, 6))  # For stop orders

    # P&L and Costs
    pnl = Column(Numeric(15, 2), default=0)
    commission = Column(Numeric(10, 2), default=0)
    fees = Column(Numeric(10, 2), default=0)

    # Timestamps
    order_time = Column(DateTime(timezone=True), default=func.now())
    execution_time = Column(DateTime(timezone=True))

    # Risk Management
    risk_score = Column(Numeric(5, 2), default=0)
    stop_loss = Column(Numeric(15, 6))
    take_profit = Column(Numeric(15, 6))

    # Additional Information
    notes = Column(Text)
    metadata = Column(JSON)

    # Relationships
    user = relationship('User', back_populates='trades')
    portfolio = relationship('Portfolio', back_populates='trades')
    challenge = relationship('Challenge', back_populates='trades')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_positive_quantity'),
        CheckConstraint('executed_quantity >= 0', name='check_non_negative_executed_quantity'),
        Index('idx_trade_symbol_time', 'symbol', 'order_time'),
        Index('idx_trade_user_status', 'user_id', 'status'),
        Index('idx_trade_portfolio_time', 'portfolio_id', 'order_time'),
    )

    @hybrid_property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.side == TradeSide.BUY

    @hybrid_property
    def is_executed(self) -> bool:
        """Check if trade is executed."""
        return self.status == TradeStatus.EXECUTED

    @hybrid_property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.quantity == 0:
            return 0
        return float(self.executed_quantity / self.quantity * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'status': self.status.value,
            'quantity': float(self.quantity),
            'executed_quantity': float(self.executed_quantity),
            'price': float(self.price) if self.price else None,
            'executed_price': float(self.executed_price) if self.executed_price else None,
            'pnl': float(self.pnl),
            'commission': float(self.commission),
            'order_time': self.order_time.isoformat() if self.order_time else None,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None,
            'fill_percentage': self.fill_percentage
        }


class Position(BaseModel):
    __tablename__ = 'positions'

    # Position Details
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)

    # Quantities and Prices
    quantity = Column(Numeric(15, 6), nullable=False)
    average_price = Column(Numeric(15, 6), nullable=False)
    market_price = Column(Numeric(15, 6))

    # P&L
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)

    # Risk Management
    stop_loss = Column(Numeric(15, 6))
    take_profit = Column(Numeric(15, 6))

    # Status
    is_open = Column(Boolean, default=True, nullable=False)

    # Relationships
    portfolio = relationship('Portfolio', back_populates='positions')

    # Constraints
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'symbol', name='unique_portfolio_symbol'),
        CheckConstraint('quantity != 0', name='check_non_zero_quantity'),
        Index('idx_position_symbol_open', 'symbol', 'is_open'),
    )

    @hybrid_property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self.quantity > 0

    @hybrid_property
    def market_value(self) -> Decimal:
        """Calculate market value."""
        if self.market_price:
            return abs(self.quantity) * self.market_price
        return abs(self.quantity) * self.average_price

    def update_unrealized_pnl(self, current_price: Decimal) -> None:
        """Update unrealized P&L based on current price."""
        self.market_price = current_price
        price_diff = current_price - self.average_price
        self.unrealized_pnl = self.quantity * price_diff


# Challenge System Models
class Challenge(BaseModel):
    __tablename__ = 'challenges'

    # Basic Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)

    # Challenge Parameters
    initial_balance = Column(Numeric(15, 2), nullable=False)
    target_profit = Column(Numeric(15, 2), nullable=False)
    max_loss = Column(Numeric(15, 2), nullable=False)
    max_daily_loss = Column(Numeric(15, 2))

    # Timeline
    duration_days = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))

    # Current Status
    status = Column(SQLEnum(ChallengeStatus), default=ChallengeStatus.DRAFT, nullable=False)
    current_balance = Column(Numeric(15, 2), default=0)
    current_pnl = Column(Numeric(15, 2), default=0)
    max_drawdown = Column(Numeric(15, 2), default=0)

    # Performance Metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    win_rate = Column(Numeric(5, 4), default=0)
    best_trade = Column(Numeric(15, 2), default=0)
    worst_trade = Column(Numeric(15, 2), default=0)

    # Rules and Settings
    allowed_instruments = Column(JSON)  # List of allowed trading instruments
    trading_rules = Column(JSON)  # Custom trading rules
    risk_parameters = Column(JSON)  # Risk management parameters

    # Fees and Costs
    entry_fee = Column(Numeric(10, 2), default=0)
    profit_share = Column(Numeric(5, 4), default=0.8)  # 80% to trader, 20% to platform

    # Relationships
    user = relationship('User', back_populates='challenges')
    trades = relationship('Trade', back_populates='challenge')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('target_profit > 0', name='check_positive_target_profit'),
        CheckConstraint('max_loss > 0', name='check_positive_max_loss'),
        CheckConstraint('duration_days > 0', name='check_positive_duration'),
        CheckConstraint('profit_share >= 0 AND profit_share <= 1', name='check_valid_profit_share'),
        Index('idx_challenge_user_status', 'user_id', 'status'),
        Index('idx_challenge_status_dates', 'status', 'start_date', 'end_date'),
    )

    @hybrid_property
    def progress_percentage(self) -> float:
        """Calculate challenge progress percentage."""
        if self.target_profit == 0:
            return 0
        return float(self.current_pnl / self.target_profit * 100)

    @hybrid_property
    def is_active(self) -> bool:
        """Check if challenge is active."""
        return self.status == ChallengeStatus.ACTIVE

    @hybrid_property
    def days_remaining(self) -> int:
        """Calculate days remaining in challenge."""
        if not self.end_date:
            return 0
        remaining = (self.end_date.date() - datetime.now(timezone.utc).date()).days
        return max(0, remaining)

    def check_risk_violations(self) -> List[str]:
        """Check for risk rule violations."""
        violations = []

        # Check maximum loss
        if self.current_pnl <= -self.max_loss:
            violations.append("Maximum loss limit exceeded")

        # Check drawdown
        if self.max_drawdown >= self.max_loss:
            violations.append("Maximum drawdown exceeded")

        # Check daily loss (if applicable)
        if self.max_daily_loss:
            # This would need to be implemented with daily P&L tracking
            pass

        return violations

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'initial_balance': float(self.initial_balance),
            'target_profit': float(self.target_profit),
            'max_loss': float(self.max_loss),
            'current_balance': float(self.current_balance),
            'current_pnl': float(self.current_pnl),
            'progress_percentage': self.progress_percentage,
            'duration_days': self.duration_days,
            'days_remaining': self.days_remaining,
            'total_trades': self.total_trades,
            'win_rate': float(self.win_rate) if self.win_rate else 0,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Payment and Billing Models
class Payment(BaseModel):
    __tablename__ = 'payments'

    # Basic Information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey('challenges.id'), nullable=True)

    # Payment Details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    payment_type = Column(String(20), nullable=False)  # challenge_fee, payout, refund, etc.

    # Status and Processing
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(String(50))  # stripe, paypal, bank_transfer, etc.

    # External References
    external_id = Column(String(255))  # Stripe payment intent ID, etc.
    transaction_id = Column(String(255))

    # Timestamps
    processed_at = Column(DateTime(timezone=True))

    # Additional Information
    description = Column(Text)
    metadata = Column(JSON)

    # Relationships
    user = relationship('User', back_populates='payments')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_amount'),
        Index('idx_payment_user_status', 'user_id', 'status'),
        Index('idx_payment_external_id', 'external_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'amount': float(self.amount),
            'currency': self.currency,
            'payment_type': self.payment_type,
            'status': self.status.value,
            'payment_method': self.payment_method,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


# Notification System
class Notification(BaseModel):
    __tablename__ = 'notifications'

    # Basic Information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Notification Type and Priority
    type = Column(String(50), nullable=False)  # trade, challenge, payment, system, etc.
    priority = Column(String(10), default='normal')  # low, normal, high, urgent

    # Status
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.UNREAD, nullable=False)
    read_at = Column(DateTime(timezone=True))

    # Additional Data
    action_url = Column(String(500))  # URL for notification action
    metadata = Column(JSON)

    # Relationships
    user = relationship('User', back_populates='notifications')

    # Constraints and Indexes
    __table_args__ = (
        Index('idx_notification_user_status', 'user_id', 'status'),
        Index('idx_notification_type_created', 'type', 'created_at'),
    )

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.status = NotificationStatus.READ
        self.read_at = func.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'priority': self.priority,
            'status': self.status.value,
            'action_url': self.action_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }


# Risk Management Models
class RiskAssessment(BaseModel):
    __tablename__ = 'risk_assessments'

    # Basic Information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), nullable=True)

    # Risk Metrics
    risk_score = Column(Numeric(5, 2), nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)

    # Assessment Details
    assessment_type = Column(String(50), nullable=False)  # daily, weekly, trade, challenge
    factors = Column(JSON)  # Risk factors and their weights
    recommendations = Column(JSON)  # Risk management recommendations

    # Timestamps
    assessment_date = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationships
    user = relationship('User', back_populates='risk_assessments')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('risk_score >= 0 AND risk_score <= 100', name='check_valid_risk_score'),
        Index('idx_risk_assessment_user_date', 'user_id', 'assessment_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'risk_score': float(self.risk_score),
            'risk_level': self.risk_level.value,
            'assessment_type': self.assessment_type,
            'factors': self.factors,
            'recommendations': self.recommendations,
            'assessment_date': self.assessment_date.isoformat() if self.assessment_date else None
        }


# Market Data Models
class MarketData(BaseModel):
    __tablename__ = 'market_data'

    # Symbol and Timeframe
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # OHLCV Data
    open_price = Column(Numeric(15, 6), nullable=False)
    high_price = Column(Numeric(15, 6), nullable=False)
    low_price = Column(Numeric(15, 6), nullable=False)
    close_price = Column(Numeric(15, 6), nullable=False)
    volume = Column(Numeric(20, 6), default=0)

    # Additional Data
    spread = Column(Numeric(10, 6))
    tick_volume = Column(Integer)

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('symbol', 'timeframe', 'timestamp', name='unique_market_data_point'),
        CheckConstraint('high_price >= low_price', name='check_high_low_prices'),
        CheckConstraint('high_price >= open_price', name='check_high_open_prices'),
        CheckConstraint('high_price >= close_price', name='check_high_close_prices'),
        CheckConstraint('low_price <= open_price', name='check_low_open_prices'),
        CheckConstraint('low_price <= close_price', name='check_low_close_prices'),
        Index('idx_market_data_symbol_time', 'symbol', 'timeframe', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'open': float(self.open_price),
            'high': float(self.high_price),
            'low': float(self.low_price),
            'close': float(self.close_price),
            'volume': float(self.volume) if self.volume else 0
        }


# Event handlers for automatic updates
@event.listens_for(Trade, 'after_insert')
def update_portfolio_on_trade_insert(mapper, connection, target):
    """Update portfolio statistics when a new trade is inserted."""
    if target.status == TradeStatus.EXECUTED:
        # Update portfolio trade count
        connection.execute(
            "UPDATE portfolios SET total_trades = total_trades + 1 WHERE id = %s",
            (str(target.portfolio_id),)
        )


@event.listens_for(User, 'before_insert')
def set_user_defaults(mapper, connection, target):
    """Set default values for new users."""
    if not target.preferences:
        target.preferences = {
            'notifications': {'email': True, 'push': True},
            'trading': {'auto_stop_loss': False, 'default_risk_level': 'medium'},
            'ui': {'theme': 'light', 'language': 'en'}
        }


# Utility functions
def init_db(app):
    """Initialize database with Flask
