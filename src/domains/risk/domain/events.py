"""Risk Engine domain events."""

from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.kernel.domain_event import DomainEvent


class RiskAlertTriggered(DomainEvent):
    """Event emitted when a risk alert is triggered."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        alert_id: str,
        user_id: UUID,
        challenge_id: Optional[UUID],
        metric_type: str,
        metric_value: str,
        severity: str,
        message: str,
        requires_action: bool,
    ):
        super().__init__(aggregate_id)
        self.alert_id = alert_id
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.metric_type = metric_type
        self.metric_value = metric_value
        self.severity = severity
        self.message = message
        self.requires_action = requires_action


class RiskAlertResolved(DomainEvent):
    """Event emitted when a risk alert is resolved."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        alert_id: str,
        user_id: UUID,
        challenge_id: Optional[UUID],
        metric_type: str,
        resolution_reason: str,
        alert_duration_seconds: int,
    ):
        super().__init__(aggregate_id)
        self.alert_id = alert_id
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.metric_type = metric_type
        self.resolution_reason = resolution_reason
        self.alert_duration_seconds = alert_duration_seconds


class RiskScoreCalculated(DomainEvent):
    """Event emitted when risk score is calculated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        risk_score: Decimal,
        risk_level: str,
        component_scores: Dict[str, Decimal],
        active_alerts_count: int,
        critical_alerts_count: int,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.component_scores = component_scores
        self.active_alerts_count = active_alerts_count
        self.critical_alerts_count = critical_alerts_count


class RiskThresholdViolated(DomainEvent):
    """Event emitted when a risk threshold is violated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        threshold_type: str,
        threshold_level: str,
        actual_value: str,
        severity: str,
        violation_percentage: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.threshold_type = threshold_type
        self.threshold_level = threshold_level
        self.actual_value = actual_value
        self.severity = severity
        self.violation_percentage = violation_percentage


class TradingHalted(DomainEvent):
    """Event emitted when trading is halted due to risk."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        reason: str,
        severity: str,
        halted_at: str,
        current_risk_score: Decimal,
        active_alerts_count: int,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.reason = reason
        self.severity = severity
        self.halted_at = halted_at
        self.current_risk_score = current_risk_score
        self.active_alerts_count = active_alerts_count


class TradingResumed(DomainEvent):
    """Event emitted when trading is resumed after halt."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        reason: str,
        resumed_at: str,
        halt_duration_seconds: int,
        current_risk_score: Decimal,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.reason = reason
        self.resumed_at = resumed_at
        self.halt_duration_seconds = halt_duration_seconds
        self.current_risk_score = current_risk_score


class EmergencyRiskEvent(DomainEvent):
    """Event emitted for emergency risk situations requiring immediate attention."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        event_type: str,
        description: str,
        risk_score: Decimal,
        requires_manual_intervention: bool,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.event_type = event_type
        self.description = description
        self.risk_score = risk_score
        self.requires_manual_intervention = requires_manual_intervention


class RiskProfileUpdated(DomainEvent):
    """Event emitted when risk profile is updated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        old_profile_name: str,
        new_profile_name: str,
        threshold_changes: List[str],
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.old_profile_name = old_profile_name
        self.new_profile_name = new_profile_name
        self.threshold_changes = threshold_changes


class RiskMetricCalculated(DomainEvent):
    """Event emitted when a specific risk metric is calculated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        metric_type: str,
        metric_value: str,
        metric_percentage: Optional[str],
        currency: str,
        calculation_timestamp: str,
        metadata: Dict,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.metric_type = metric_type
        self.metric_value = metric_value
        self.metric_percentage = metric_percentage
        self.currency = currency
        self.calculation_timestamp = calculation_timestamp
        self.metadata = metadata


class DrawdownLimitExceeded(DomainEvent):
    """Event emitted when drawdown limits are exceeded."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        drawdown_type: str,  # DAILY or TOTAL
        drawdown_amount: str,
        drawdown_percentage: str,
        limit_amount: str,
        limit_percentage: str,
        peak_balance: str,
        current_balance: str,
        severity: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.drawdown_type = drawdown_type
        self.drawdown_amount = drawdown_amount
        self.drawdown_percentage = drawdown_percentage
        self.limit_amount = limit_amount
        self.limit_percentage = limit_percentage
        self.peak_balance = peak_balance
        self.current_balance = current_balance
        self.severity = severity


class PositionRiskExceeded(DomainEvent):
    """Event emitted when position risk limits are exceeded."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        symbol: str,
        position_size: str,
        position_percentage: str,
        limit_percentage: str,
        account_balance: str,
        unrealized_pnl: str,
        severity: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.symbol = symbol
        self.position_size = position_size
        self.position_percentage = position_percentage
        self.limit_percentage = limit_percentage
        self.account_balance = account_balance
        self.unrealized_pnl = unrealized_pnl
        self.severity = severity


class TradingVelocityExceeded(DomainEvent):
    """Event emitted when trading velocity limits are exceeded."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        trades_per_hour: str,
        trades_per_day: int,
        limit_per_hour: str,
        limit_per_day: Optional[int],
        time_window_hours: int,
        severity: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.trades_per_hour = trades_per_hour
        self.trades_per_day = trades_per_day
        self.limit_per_hour = limit_per_hour
        self.limit_per_day = limit_per_day
        self.time_window_hours = time_window_hours
        self.severity = severity


class VolatilityThresholdExceeded(DomainEvent):
    """Event emitted when P&L volatility exceeds thresholds."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        volatility: str,
        volatility_percentage: str,
        threshold_percentage: str,
        annualized_volatility: str,
        time_period_days: int,
        severity: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.volatility = volatility
        self.volatility_percentage = volatility_percentage
        self.threshold_percentage = threshold_percentage
        self.annualized_volatility = annualized_volatility
        self.time_period_days = time_period_days
        self.severity = severity


class RiskEngineStatusChanged(DomainEvent):
    """Event emitted when risk engine status changes."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: Optional[UUID],
        old_status: str,
        new_status: str,
        reason: str,
        risk_score: Decimal,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.old_status = old_status
        self.new_status = new_status
        self.reason = reason
        self.risk_score = risk_score


class ChallengeRiskAssessment(DomainEvent):
    """Event emitted with comprehensive risk assessment for a challenge."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        risk_score: Decimal,
        risk_level: str,
        should_halt_trading: bool,
        should_fail_challenge: bool,
        critical_violations: List[str],
        recommendations: List[str],
        assessment_timestamp: str,
    ):
        super().__init__(aggregate_id)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.should_halt_trading = should_halt_trading
        self.should_fail_challenge = should_fail_challenge
        self.critical_violations = critical_violations
        self.recommendations = recommendations
        self.assessment_timestamp = assessment_timestamp