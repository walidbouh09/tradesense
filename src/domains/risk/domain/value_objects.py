"""Risk Engine value objects and metrics definitions."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.exceptions.base import ValidationError
from ....shared.kernel.value_object import ValueObject
from ....shared.utils.money import Money


class RiskLevel(Enum):
    """Risk level enumeration."""
    MINIMAL = "MINIMAL"      # 0-20% risk score
    LOW = "LOW"              # 21-40% risk score
    MEDIUM = "MEDIUM"        # 41-60% risk score
    HIGH = "HIGH"            # 61-80% risk score
    EXTREME = "EXTREME"      # 81-100% risk score


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "INFO"            # Informational alert
    WARNING = "WARNING"      # Warning level
    CRITICAL = "CRITICAL"    # Critical alert requiring attention
    EMERGENCY = "EMERGENCY"  # Emergency requiring immediate action


class RiskMetricType(Enum):
    """Types of risk metrics."""
    # Drawdown Metrics
    DAILY_DRAWDOWN = "DAILY_DRAWDOWN"
    TOTAL_DRAWDOWN = "TOTAL_DRAWDOWN"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    DRAWDOWN_DURATION = "DRAWDOWN_DURATION"
    
    # P&L Metrics
    DAILY_PNL = "DAILY_PNL"
    TOTAL_PNL = "TOTAL_PNL"
    UNREALIZED_PNL = "UNREALIZED_PNL"
    PNL_VOLATILITY = "PNL_VOLATILITY"
    
    # Position Metrics
    POSITION_SIZE = "POSITION_SIZE"
    POSITION_CONCENTRATION = "POSITION_CONCENTRATION"
    LEVERAGE = "LEVERAGE"
    EXPOSURE = "EXPOSURE"
    
    # Trading Activity Metrics
    TRADE_FREQUENCY = "TRADE_FREQUENCY"
    WIN_RATE = "WIN_RATE"
    PROFIT_FACTOR = "PROFIT_FACTOR"
    AVERAGE_TRADE_SIZE = "AVERAGE_TRADE_SIZE"
    
    # Time-based Metrics
    TRADING_VELOCITY = "TRADING_VELOCITY"
    HOLDING_PERIOD = "HOLDING_PERIOD"
    TRADING_HOURS = "TRADING_HOURS"
    
    # Correlation Metrics
    SYMBOL_CORRELATION = "SYMBOL_CORRELATION"
    SECTOR_EXPOSURE = "SECTOR_EXPOSURE"


class ThresholdType(Enum):
    """Threshold comparison types."""
    ABSOLUTE = "ABSOLUTE"        # Absolute value threshold
    PERCENTAGE = "PERCENTAGE"    # Percentage threshold
    RATIO = "RATIO"             # Ratio threshold
    STANDARD_DEVIATION = "STD_DEV"  # Standard deviation threshold


class RiskThreshold(ValueObject):
    """Risk threshold definition."""
    
    def __init__(
        self,
        metric_type: RiskMetricType,
        threshold_type: ThresholdType,
        warning_level: Decimal,
        critical_level: Decimal,
        emergency_level: Optional[Decimal] = None,
        currency: str = "USD",
        description: Optional[str] = None,
    ):
        self.metric_type = metric_type
        self.threshold_type = threshold_type
        self.warning_level = warning_level
        self.critical_level = critical_level
        self.emergency_level = emergency_level
        self.currency = currency
        self.description = description or f"{metric_type.value} threshold"
        
        # Validate threshold levels
        if warning_level >= critical_level:
            raise ValidationError("Warning level must be less than critical level")
        
        if emergency_level and critical_level >= emergency_level:
            raise ValidationError("Critical level must be less than emergency level")
    
    def evaluate_level(self, value: Decimal) -> AlertSeverity:
        """Evaluate alert severity based on value."""
        if self.emergency_level and abs(value) >= abs(self.emergency_level):
            return AlertSeverity.EMERGENCY
        elif abs(value) >= abs(self.critical_level):
            return AlertSeverity.CRITICAL
        elif abs(value) >= abs(self.warning_level):
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO
    
    def is_violated(self, value: Decimal) -> bool:
        """Check if threshold is violated."""
        return abs(value) >= abs(self.warning_level)


class RiskMetric(ValueObject):
    """Individual risk metric calculation."""
    
    def __init__(
        self,
        metric_type: RiskMetricType,
        value: Decimal,
        currency: str = "USD",
        percentage: Optional[Decimal] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ):
        self.metric_type = metric_type
        self.value = value
        self.currency = currency
        self.percentage = percentage
        self.timestamp = timestamp or datetime.utcnow()
        self.metadata = metadata or {}
    
    def __str__(self) -> str:
        if self.percentage:
            return f"{self.metric_type.value}: {self.value} ({self.percentage}%)"
        return f"{self.metric_type.value}: {self.value}"


class DrawdownMetric(RiskMetric):
    """Specialized drawdown metric."""
    
    def __init__(
        self,
        drawdown_amount: Money,
        drawdown_percentage: Decimal,
        peak_balance: Money,
        current_balance: Money,
        drawdown_start: Optional[datetime] = None,
        is_daily: bool = False,
    ):
        metric_type = RiskMetricType.DAILY_DRAWDOWN if is_daily else RiskMetricType.TOTAL_DRAWDOWN
        
        super().__init__(
            metric_type=metric_type,
            value=drawdown_amount.amount,
            currency=drawdown_amount.currency,
            percentage=drawdown_percentage,
            metadata={
                "peak_balance": str(peak_balance.amount),
                "current_balance": str(current_balance.amount),
                "drawdown_start": drawdown_start.isoformat() if drawdown_start else None,
                "is_daily": is_daily,
            }
        )
        
        self.drawdown_amount = drawdown_amount
        self.drawdown_percentage = drawdown_percentage
        self.peak_balance = peak_balance
        self.current_balance = current_balance
        self.drawdown_start = drawdown_start
        self.is_daily = is_daily
    
    @property
    def duration_hours(self) -> Optional[float]:
        """Calculate drawdown duration in hours."""
        if not self.drawdown_start:
            return None
        return (self.timestamp - self.drawdown_start).total_seconds() / 3600


class PositionRiskMetric(RiskMetric):
    """Position-specific risk metric."""
    
    def __init__(
        self,
        symbol: str,
        position_size: Money,
        account_balance: Money,
        leverage: Decimal,
        unrealized_pnl: Money,
        timestamp: Optional[datetime] = None,
    ):
        # Calculate position size as percentage of account
        size_percentage = (position_size.amount / account_balance.amount * 100) if account_balance.amount > 0 else Decimal("0")
        
        super().__init__(
            metric_type=RiskMetricType.POSITION_SIZE,
            value=position_size.amount,
            currency=position_size.currency,
            percentage=size_percentage,
            timestamp=timestamp,
            metadata={
                "symbol": symbol,
                "account_balance": str(account_balance.amount),
                "leverage": str(leverage),
                "unrealized_pnl": str(unrealized_pnl.amount),
            }
        )
        
        self.symbol = symbol
        self.position_size = position_size
        self.account_balance = account_balance
        self.leverage = leverage
        self.unrealized_pnl = unrealized_pnl


class TradingVelocityMetric(RiskMetric):
    """Trading velocity and frequency metric."""
    
    def __init__(
        self,
        trades_per_hour: Decimal,
        trades_per_day: int,
        average_trade_size: Money,
        total_volume: Money,
        time_window_hours: int = 24,
        timestamp: Optional[datetime] = None,
    ):
        super().__init__(
            metric_type=RiskMetricType.TRADING_VELOCITY,
            value=trades_per_hour,
            timestamp=timestamp,
            metadata={
                "trades_per_day": trades_per_day,
                "average_trade_size": str(average_trade_size.amount),
                "total_volume": str(total_volume.amount),
                "time_window_hours": time_window_hours,
            }
        )
        
        self.trades_per_hour = trades_per_hour
        self.trades_per_day = trades_per_day
        self.average_trade_size = average_trade_size
        self.total_volume = total_volume
        self.time_window_hours = time_window_hours


class VolatilityMetric(RiskMetric):
    """P&L volatility metric."""
    
    def __init__(
        self,
        volatility: Decimal,
        returns: List[Decimal],
        time_period_days: int,
        annualized_volatility: Optional[Decimal] = None,
        timestamp: Optional[datetime] = None,
    ):
        super().__init__(
            metric_type=RiskMetricType.PNL_VOLATILITY,
            value=volatility,
            percentage=volatility * 100,  # Convert to percentage
            timestamp=timestamp,
            metadata={
                "returns_count": len(returns),
                "time_period_days": time_period_days,
                "annualized_volatility": str(annualized_volatility) if annualized_volatility else None,
                "min_return": str(min(returns)) if returns else None,
                "max_return": str(max(returns)) if returns else None,
            }
        )
        
        self.volatility = volatility
        self.returns = returns
        self.time_period_days = time_period_days
        self.annualized_volatility = annualized_volatility


class RiskAlert(ValueObject):
    """Risk alert generated when thresholds are violated."""
    
    def __init__(
        self,
        alert_id: str,
        user_id: UUID,
        metric: RiskMetric,
        threshold: RiskThreshold,
        severity: AlertSeverity,
        message: str,
        triggered_at: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ):
        self.alert_id = alert_id
        self.user_id = user_id
        self.metric = metric
        self.threshold = threshold
        self.severity = severity
        self.message = message
        self.triggered_at = triggered_at or datetime.utcnow()
        self.metadata = metadata or {}
    
    @property
    def is_critical(self) -> bool:
        """Check if alert is critical or emergency."""
        return self.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
    
    @property
    def requires_immediate_action(self) -> bool:
        """Check if alert requires immediate action."""
        return self.severity == AlertSeverity.EMERGENCY


class RiskProfile(ValueObject):
    """Risk profile configuration for a trader/challenge."""
    
    def __init__(
        self,
        user_id: UUID,
        challenge_id: Optional[UUID],
        thresholds: List[RiskThreshold],
        max_daily_trades: Optional[int] = None,
        max_position_size_percent: Optional[Decimal] = None,
        max_leverage: Optional[Decimal] = None,
        allowed_symbols: Optional[List[str]] = None,
        forbidden_symbols: Optional[List[str]] = None,
        trading_hours_start: Optional[str] = None,
        trading_hours_end: Optional[str] = None,
        profile_name: str = "Default",
        is_active: bool = True,
    ):
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.thresholds = thresholds
        self.max_daily_trades = max_daily_trades
        self.max_position_size_percent = max_position_size_percent
        self.max_leverage = max_leverage
        self.allowed_symbols = allowed_symbols or []
        self.forbidden_symbols = forbidden_symbols or []
        self.trading_hours_start = trading_hours_start
        self.trading_hours_end = trading_hours_end
        self.profile_name = profile_name
        self.is_active = is_active
    
    def get_threshold(self, metric_type: RiskMetricType) -> Optional[RiskThreshold]:
        """Get threshold for specific metric type."""
        for threshold in self.thresholds:
            if threshold.metric_type == metric_type:
                return threshold
        return None
    
    def is_symbol_allowed(self, symbol: str) -> bool:
        """Check if symbol is allowed for trading."""
        if self.forbidden_symbols and symbol in self.forbidden_symbols:
            return False
        
        if self.allowed_symbols:
            return symbol in self.allowed_symbols
        
        return True  # Allow all if no restrictions
    
    def is_within_trading_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is within allowed trading hours."""
        if not self.trading_hours_start or not self.trading_hours_end:
            return True  # No restrictions
        
        current_time = timestamp.time()
        start_time = datetime.strptime(self.trading_hours_start, "%H:%M").time()
        end_time = datetime.strptime(self.trading_hours_end, "%H:%M").time()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Overnight trading hours
            return current_time >= start_time or current_time <= end_time


class RiskScore(ValueObject):
    """Overall risk score calculation."""
    
    def __init__(
        self,
        user_id: UUID,
        overall_score: Decimal,
        risk_level: RiskLevel,
        component_scores: Dict[RiskMetricType, Decimal],
        active_alerts: List[RiskAlert],
        calculation_timestamp: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ):
        if not (0 <= overall_score <= 100):
            raise ValidationError("Risk score must be between 0 and 100")
        
        self.user_id = user_id
        self.overall_score = overall_score
        self.risk_level = risk_level
        self.component_scores = component_scores
        self.active_alerts = active_alerts
        self.calculation_timestamp = calculation_timestamp or datetime.utcnow()
        self.metadata = metadata or {}
    
    @classmethod
    def calculate_risk_level(cls, score: Decimal) -> RiskLevel:
        """Calculate risk level from score."""
        if score >= 81:
            return RiskLevel.EXTREME
        elif score >= 61:
            return RiskLevel.HIGH
        elif score >= 41:
            return RiskLevel.MEDIUM
        elif score >= 21:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL
    
    @property
    def critical_alerts_count(self) -> int:
        """Count of critical and emergency alerts."""
        return len([alert for alert in self.active_alerts if alert.is_critical])
    
    @property
    def emergency_alerts_count(self) -> int:
        """Count of emergency alerts."""
        return len([alert for alert in self.active_alerts if alert.severity == AlertSeverity.EMERGENCY])


class RiskLimits(ValueObject):
    """Risk limits and constraints."""
    
    def __init__(
        self,
        max_daily_loss: Optional[Money] = None,
        max_total_loss: Optional[Money] = None,
        max_daily_loss_percent: Optional[Decimal] = None,
        max_total_loss_percent: Optional[Decimal] = None,
        max_position_size: Optional[Money] = None,
        max_position_size_percent: Optional[Decimal] = None,
        max_leverage: Optional[Decimal] = None,
        max_correlation_exposure: Optional[Decimal] = None,
        max_trades_per_day: Optional[int] = None,
        max_trades_per_hour: Optional[int] = None,
        currency: str = "USD",
    ):
        self.max_daily_loss = max_daily_loss
        self.max_total_loss = max_total_loss
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_total_loss_percent = max_total_loss_percent
        self.max_position_size = max_position_size
        self.max_position_size_percent = max_position_size_percent
        self.max_leverage = max_leverage
        self.max_correlation_exposure = max_correlation_exposure
        self.max_trades_per_day = max_trades_per_day
        self.max_trades_per_hour = max_trades_per_hour
        self.currency = currency
    
    def is_daily_loss_exceeded(self, daily_pnl: Money) -> bool:
        """Check if daily loss limit is exceeded."""
        if daily_pnl.amount >= 0:
            return False
        
        daily_loss = abs(daily_pnl.amount)
        
        if self.max_daily_loss and daily_loss > self.max_daily_loss.amount:
            return True
        
        return False
    
    def is_position_size_exceeded(self, position_size: Money, account_balance: Money) -> bool:
        """Check if position size limit is exceeded."""
        if self.max_position_size and position_size.amount > self.max_position_size.amount:
            return True
        
        if self.max_position_size_percent and account_balance.amount > 0:
            size_percent = position_size.amount / account_balance.amount * 100
            if size_percent > self.max_position_size_percent:
                return True
        
        return False