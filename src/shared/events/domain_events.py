"""Domain event definitions for TradeSense AI."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from ..kernel.events import DomainEvent


# Trading Domain Events

class TradingPositionOpenedEvent(DomainEvent):
    """Event fired when a trading position is opened."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        size: Decimal,
        entry_price: Decimal,
        side: str,  # "long" or "short"
        leverage: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.position_id = position_id
        self.user_id = user_id
        self.symbol = symbol
        self.size = size
        self.entry_price = entry_price
        self.side = side
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.take_profit = take_profit


class TradingPositionClosedEvent(DomainEvent):
    """Event fired when a trading position is closed."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        size: Decimal,
        exit_price: Decimal,
        realized_pnl: Decimal,
        close_reason: str,  # "manual", "stop_loss", "take_profit", "margin_call"
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.position_id = position_id
        self.user_id = user_id
        self.symbol = symbol
        self.size = size
        self.exit_price = exit_price
        self.realized_pnl = realized_pnl
        self.close_reason = close_reason


class TradingTradeExecutedEvent(DomainEvent):
    """Event fired when a trade is executed."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trade_id: UUID,
        user_id: UUID,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        side: str,  # "buy" or "sell"
        order_type: str,  # "market", "limit", "stop"
        commission: Decimal,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.trade_id = trade_id
        self.user_id = user_id
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.side = side
        self.order_type = order_type
        self.commission = commission


class TradingPnLUpdatedEvent(DomainEvent):
    """Event fired when PnL is updated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        current_balance: Decimal,
        daily_pnl: Decimal,
        total_pnl: Decimal,
        unrealized_pnl: Decimal,
        equity: Decimal,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.current_balance = current_balance
        self.daily_pnl = daily_pnl
        self.total_pnl = total_pnl
        self.unrealized_pnl = unrealized_pnl
        self.equity = equity


# Risk Domain Events

class RiskLimitBreachedEvent(DomainEvent):
    """Event fired when a risk limit is breached."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        limit_type: str,  # "daily_loss", "total_loss", "position_size"
        current_value: Decimal,
        limit_value: Decimal,
        severity: str,  # "warning", "critical"
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.limit_type = limit_type
        self.current_value = current_value
        self.limit_value = limit_value
        self.severity = severity


class RiskAlertTriggeredEvent(DomainEvent):
    """Event fired when a risk alert is triggered."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        alert_type: str,
        message: str,
        risk_score: Decimal,
        threshold: Decimal,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.alert_type = alert_type
        self.message = message
        self.risk_score = risk_score
        self.threshold = threshold


class RiskTradingHaltedEvent(DomainEvent):
    """Event fired when trading is halted due to risk."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        halt_reason: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.halt_reason = halt_reason


class RiskTradingResumedEvent(DomainEvent):
    """Event fired when trading is resumed after halt."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        resume_reason: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.resume_reason = resume_reason


# Challenge Domain Events

class ChallengeStartedEvent(DomainEvent):
    """Event fired when a challenge is started."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        challenge_id: UUID,
        user_id: UUID,
        challenge_type: str,  # "PHASE_1", "PHASE_2", "FUNDED"
        initial_balance: Decimal,
        target_profit: Decimal,
        max_loss: Decimal,
        duration_days: int,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.challenge_type = challenge_type
        self.initial_balance = initial_balance
        self.target_profit = target_profit
        self.max_loss = max_loss
        self.duration_days = duration_days


class ChallengeCompletedEvent(DomainEvent):
    """Event fired when a challenge is completed successfully."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        challenge_id: UUID,
        user_id: UUID,
        challenge_type: str,
        final_balance: Decimal,
        profit_achieved: Decimal,
        completion_time_days: int,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.challenge_type = challenge_type
        self.final_balance = final_balance
        self.profit_achieved = profit_achieved
        self.completion_time_days = completion_time_days


class ChallengeFailedEvent(DomainEvent):
    """Event fired when a challenge fails."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        challenge_id: UUID,
        user_id: UUID,
        challenge_type: str,
        failure_reason: str,
        final_balance: Decimal,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.challenge_type = challenge_type
        self.failure_reason = failure_reason
        self.final_balance = final_balance


class ChallengePhaseAdvancedEvent(DomainEvent):
    """Event fired when a challenge advances to next phase."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        challenge_id: UUID,
        user_id: UUID,
        from_phase: str,
        to_phase: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.challenge_id = challenge_id
        self.user_id = user_id
        self.from_phase = from_phase
        self.to_phase = to_phase


# Auth Domain Events

class AuthUserRegisteredEvent(DomainEvent):
    """Event fired when a user registers."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        email: str,
        username: str,
        registration_ip: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.email = email
        self.username = username
        self.registration_ip = registration_ip


class AuthUserLoggedInEvent(DomainEvent):
    """Event fired when a user logs in."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        session_id: UUID,
        ip_address: str,
        user_agent: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.session_id = session_id
        self.ip_address = ip_address
        self.user_agent = user_agent


class AuthUserLoggedOutEvent(DomainEvent):
    """Event fired when a user logs out."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        session_id: UUID,
        logout_reason: str,  # "manual", "timeout", "forced"
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.session_id = session_id
        self.logout_reason = logout_reason


class AuthSessionExpiredEvent(DomainEvent):
    """Event fired when a user session expires."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        session_id: UUID,
        expiry_reason: str,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.session_id = session_id
        self.expiry_reason = expiry_reason


# Evaluation Domain Events

class EvaluationRuleViolatedEvent(DomainEvent):
    """Event fired when an evaluation rule is violated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        rule_name: str,
        rule_description: str,
        violation_details: Dict[str, Any],
        severity: str,  # "warning", "critical", "fatal"
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.rule_name = rule_name
        self.rule_description = rule_description
        self.violation_details = violation_details
        self.severity = severity


class EvaluationMetricCalculatedEvent(DomainEvent):
    """Event fired when an evaluation metric is calculated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        metric_name: str,
        metric_value: Decimal,
        calculation_timestamp: datetime,
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.calculation_timestamp = calculation_timestamp


class EvaluationReportGeneratedEvent(DomainEvent):
    """Event fired when an evaluation report is generated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        user_id: UUID,
        challenge_id: UUID,
        report_type: str,  # "daily", "weekly", "final"
        report_data: Dict[str, Any],
        **kwargs: Any,
    ):
        super().__init__(aggregate_id, **kwargs)
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.report_type = report_type
        self.report_data = report_data


# Event Type Registry
EVENT_TYPE_REGISTRY = {
    # Trading Events
    "Trading.Position.Opened.v1": TradingPositionOpenedEvent,
    "Trading.Position.Closed.v1": TradingPositionClosedEvent,
    "Trading.Trade.Executed.v1": TradingTradeExecutedEvent,
    "Trading.PnL.Updated.v1": TradingPnLUpdatedEvent,
    
    # Risk Events
    "Risk.Limit.Breached.v1": RiskLimitBreachedEvent,
    "Risk.Alert.Triggered.v1": RiskAlertTriggeredEvent,
    "Risk.Trading.Halted.v1": RiskTradingHaltedEvent,
    "Risk.Trading.Resumed.v1": RiskTradingResumedEvent,
    
    # Challenge Events
    "Challenge.Started.v1": ChallengeStartedEvent,
    "Challenge.Completed.v1": ChallengeCompletedEvent,
    "Challenge.Failed.v1": ChallengeFailedEvent,
    "Challenge.Phase.Advanced.v1": ChallengePhaseAdvancedEvent,
    
    # Auth Events
    "Auth.User.Registered.v1": AuthUserRegisteredEvent,
    "Auth.User.LoggedIn.v1": AuthUserLoggedInEvent,
    "Auth.User.LoggedOut.v1": AuthUserLoggedOutEvent,
    "Auth.Session.Expired.v1": AuthSessionExpiredEvent,
    
    # Evaluation Events
    "Evaluation.Rule.Violated.v1": EvaluationRuleViolatedEvent,
    "Evaluation.Metric.Calculated.v1": EvaluationMetricCalculatedEvent,
    "Evaluation.Report.Generated.v1": EvaluationReportGeneratedEvent,
}


def create_event_from_dict(event_data: Dict[str, Any]) -> DomainEvent:
    """Create domain event from dictionary data."""
    event_type = event_data.get("event_type")
    if not event_type:
        raise ValueError("Event type is required")
    
    event_class = EVENT_TYPE_REGISTRY.get(event_type)
    if not event_class:
        raise ValueError(f"Unknown event type: {event_type}")
    
    # Extract common fields
    aggregate_id = UUID(event_data["aggregate_id"])
    event_id = UUID(event_data.get("event_id", ""))
    occurred_at = datetime.fromisoformat(event_data["occurred_at"])
    
    # Remove common fields from data
    event_specific_data = {
        k: v for k, v in event_data.items()
        if k not in ["event_type", "aggregate_id", "event_id", "occurred_at"]
    }
    
    # Create event instance
    return event_class(
        aggregate_id=aggregate_id,
        event_id=event_id,
        occurred_at=occurred_at,
        **event_specific_data,
    )