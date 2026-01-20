"""Evaluation domain value objects."""

from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from ....shared.exceptions.base import ValidationError
from ....shared.kernel.value_object import ValueObject
from ....shared.utils.money import Money


class ChallengeState(Enum):
    """Challenge state enumeration with transition rules."""
    
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    FUNDED = "FUNDED"
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in [ChallengeState.FAILED, ChallengeState.FUNDED]
    
    @property
    def allows_trading(self) -> bool:
        """Check if trading is allowed in this state."""
        return self == ChallengeState.ACTIVE
    
    @property
    def allows_funding(self) -> bool:
        """Check if funding is allowed from this state."""
        return self == ChallengeState.ACTIVE
    
    def can_transition_to(self, target_state: "ChallengeState") -> bool:
        """Check if transition to target state is allowed."""
        valid_transitions = {
            ChallengeState.PENDING: [ChallengeState.ACTIVE],
            ChallengeState.ACTIVE: [ChallengeState.FAILED, ChallengeState.FUNDED],
            ChallengeState.FAILED: [],  # Terminal
            ChallengeState.FUNDED: [],  # Terminal
        }
        
        return target_state in valid_transitions.get(self, [])


class ChallengeType(Enum):
    """Challenge type enumeration."""
    
    PHASE_1 = "PHASE_1"      # Initial evaluation phase
    PHASE_2 = "PHASE_2"      # Verification phase
    EXPRESS = "EXPRESS"       # Single phase challenge
    
    @property
    def requires_verification(self) -> bool:
        """Check if this challenge type requires verification phase."""
        return self == ChallengeType.PHASE_1
    
    @property
    def max_duration_days(self) -> int:
        """Get maximum duration for this challenge type."""
        durations = {
            ChallengeType.PHASE_1: 30,
            ChallengeType.PHASE_2: 60,
            ChallengeType.EXPRESS: 30,
        }
        return durations[self]


class RiskRule(ValueObject):
    """Risk rule definition."""
    
    def __init__(
        self,
        name: str,
        description: str,
        max_daily_loss: Optional[Money] = None,
        max_total_loss: Optional[Money] = None,
        max_daily_loss_percent: Optional[Decimal] = None,
        max_total_loss_percent: Optional[Decimal] = None,
        min_trading_days: Optional[int] = None,
        max_position_size: Optional[Money] = None,
        allowed_instruments: Optional[List[str]] = None,
        forbidden_strategies: Optional[List[str]] = None,
    ):
        if not name or not name.strip():
            raise ValidationError("Risk rule name cannot be empty")
        
        if not description or not description.strip():
            raise ValidationError("Risk rule description cannot be empty")
        
        self.name = name.strip()
        self.description = description.strip()
        self.max_daily_loss = max_daily_loss
        self.max_total_loss = max_total_loss
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_total_loss_percent = max_total_loss_percent
        self.min_trading_days = min_trading_days
        self.max_position_size = max_position_size
        self.allowed_instruments = allowed_instruments or []
        self.forbidden_strategies = forbidden_strategies or []
    
    def validate_daily_loss(self, daily_pnl: Money, account_balance: Money) -> bool:
        """Validate daily loss against rule."""
        if daily_pnl.amount >= 0:
            return True  # No loss, rule passes
        
        daily_loss = Money(abs(daily_pnl.amount), daily_pnl.currency)
        
        # Check absolute daily loss limit
        if self.max_daily_loss and daily_loss > self.max_daily_loss:
            return False
        
        # Check percentage daily loss limit
        if self.max_daily_loss_percent:
            loss_percent = (daily_loss.amount / account_balance.amount) * 100
            if loss_percent > self.max_daily_loss_percent:
                return False
        
        return True
    
    def validate_total_loss(self, total_pnl: Money, initial_balance: Money) -> bool:
        """Validate total loss against rule."""
        if total_pnl.amount >= 0:
            return True  # No loss, rule passes
        
        total_loss = Money(abs(total_pnl.amount), total_pnl.currency)
        
        # Check absolute total loss limit
        if self.max_total_loss and total_loss > self.max_total_loss:
            return False
        
        # Check percentage total loss limit
        if self.max_total_loss_percent:
            loss_percent = (total_loss.amount / initial_balance.amount) * 100
            if loss_percent > self.max_total_loss_percent:
                return False
        
        return True


class ProfitTarget(ValueObject):
    """Profit target definition."""
    
    def __init__(
        self,
        target_amount: Money,
        target_percent: Optional[Decimal] = None,
        consistency_rule: Optional[Decimal] = None,  # Max % of profit from single day
    ):
        if target_amount.amount <= 0:
            raise ValidationError("Profit target must be positive")
        
        self.target_amount = target_amount
        self.target_percent = target_percent
        self.consistency_rule = consistency_rule
    
    def is_achieved(self, current_profit: Money, daily_profits: List[Money]) -> bool:
        """Check if profit target is achieved."""
        # Check if target amount is reached
        if current_profit < self.target_amount:
            return False
        
        # Check consistency rule if specified
        if self.consistency_rule and daily_profits:
            max_daily_profit = max(daily_profits, key=lambda x: x.amount)
            if max_daily_profit.amount > 0:
                daily_percent = (max_daily_profit.amount / current_profit.amount) * 100
                if daily_percent > self.consistency_rule:
                    return False
        
        return True


class ChallengeParameters(ValueObject):
    """Challenge parameters configuration."""
    
    def __init__(
        self,
        challenge_type: ChallengeType,
        initial_balance: Money,
        profit_target: ProfitTarget,
        risk_rules: List[RiskRule],
        max_duration_days: Optional[int] = None,
        min_trading_days: int = 5,
        max_position_size_percent: Decimal = Decimal("10"),
        allowed_instruments: Optional[List[str]] = None,
        leverage_limit: Optional[Decimal] = None,
    ):
        if initial_balance.amount <= 0:
            raise ValidationError("Initial balance must be positive")
        
        if min_trading_days < 1:
            raise ValidationError("Minimum trading days must be at least 1")
        
        if max_position_size_percent <= 0 or max_position_size_percent > 100:
            raise ValidationError("Max position size percent must be between 0 and 100")
        
        self.challenge_type = challenge_type
        self.initial_balance = initial_balance
        self.profit_target = profit_target
        self.risk_rules = risk_rules
        self.max_duration_days = max_duration_days or challenge_type.max_duration_days
        self.min_trading_days = min_trading_days
        self.max_position_size_percent = max_position_size_percent
        self.allowed_instruments = allowed_instruments or []
        self.leverage_limit = leverage_limit
    
    @property
    def max_position_size(self) -> Money:
        """Calculate maximum position size."""
        max_size = self.initial_balance.amount * (self.max_position_size_percent / 100)
        return Money(max_size, self.initial_balance.currency)


class RiskViolation(ValueObject):
    """Risk violation record."""
    
    def __init__(
        self,
        rule_name: str,
        violation_type: str,
        description: str,
        severity: str,
        current_value: str,
        limit_value: str,
        timestamp: Optional[str] = None,
    ):
        if not rule_name or not rule_name.strip():
            raise ValidationError("Rule name cannot be empty")
        
        if not violation_type or not violation_type.strip():
            raise ValidationError("Violation type cannot be empty")
        
        if severity not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            raise ValidationError("Severity must be LOW, MEDIUM, HIGH, or CRITICAL")
        
        self.rule_name = rule_name.strip()
        self.violation_type = violation_type.strip()
        self.description = description.strip()
        self.severity = severity
        self.current_value = current_value
        self.limit_value = limit_value
        self.timestamp = timestamp
    
    @property
    def is_critical(self) -> bool:
        """Check if violation is critical (causes immediate failure)."""
        return self.severity == "CRITICAL"


class TradingMetrics(ValueObject):
    """Trading performance metrics."""
    
    def __init__(
        self,
        total_pnl: Money,
        daily_pnl: Money,
        trading_days: int,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        largest_win: Money,
        largest_loss: Money,
        current_drawdown: Money,
        max_drawdown: Money,
        daily_profits: List[Money],
    ):
        self.total_pnl = total_pnl
        self.daily_pnl = daily_pnl
        self.trading_days = trading_days
        self.total_trades = total_trades
        self.winning_trades = winning_trades
        self.losing_trades = losing_trades
        self.largest_win = largest_win
        self.largest_loss = largest_loss
        self.current_drawdown = current_drawdown
        self.max_drawdown = max_drawdown
        self.daily_profits = daily_profits
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(self.total_trades) * 100
    
    @property
    def profit_factor(self) -> Decimal:
        """Calculate profit factor."""
        if self.largest_loss.amount == 0:
            return Decimal("0")
        return self.largest_win.amount / abs(self.largest_loss.amount)
    
    @property
    def average_daily_profit(self) -> Money:
        """Calculate average daily profit."""
        if self.trading_days == 0:
            return Money.zero(self.total_pnl.currency)
        
        avg_amount = self.total_pnl.amount / self.trading_days
        return Money(avg_amount, self.total_pnl.currency)