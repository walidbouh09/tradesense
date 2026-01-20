"""Evaluation domain events."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.kernel.events import DomainEvent


class ChallengeStarted(DomainEvent):
    """Event emitted when a challenge is started."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        challenge_type: str,
        initial_balance: str,
        profit_target: str,
        max_duration_days: int,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            challenge_type=challenge_type,
            initial_balance=initial_balance,
            profit_target=profit_target,
            max_duration_days=max_duration_days,
            **kwargs,
        )


class ChallengeStateChanged(DomainEvent):
    """Event emitted when challenge state changes."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        old_state: str,
        new_state: str,
        reason: str,
        changed_by: Optional[UUID] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
            changed_by=changed_by,
            **kwargs,
        )


class ChallengeFailed(DomainEvent):
    """Event emitted when a challenge fails."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        failure_reason: str,
        risk_violations: List[Dict],
        final_balance: str,
        trading_days: int,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            failure_reason=failure_reason,
            risk_violations=risk_violations,
            final_balance=final_balance,
            trading_days=trading_days,
            **kwargs,
        )


class ChallengePassed(DomainEvent):
    """Event emitted when a challenge is passed."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        challenge_type: str,
        final_balance: str,
        total_profit: str,
        trading_days: int,
        performance_metrics: Dict,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            challenge_type=challenge_type,
            final_balance=final_balance,
            total_profit=total_profit,
            trading_days=trading_days,
            performance_metrics=performance_metrics,
            **kwargs,
        )


class TraderFunded(DomainEvent):
    """Event emitted when a trader receives funding."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        funded_amount: str,
        profit_split_percent: int,
        funding_date: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            funded_amount=funded_amount,
            profit_split_percent=profit_split_percent,
            funding_date=funding_date,
            **kwargs,
        )


class RiskViolationDetected(DomainEvent):
    """Event emitted when a risk violation is detected."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        rule_name: str,
        violation_type: str,
        severity: str,
        description: str,
        current_value: str,
        limit_value: str,
        auto_failed: bool,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            rule_name=rule_name,
            violation_type=violation_type,
            severity=severity,
            description=description,
            current_value=current_value,
            limit_value=limit_value,
            auto_failed=auto_failed,
            **kwargs,
        )


class TradingMetricsUpdated(DomainEvent):
    """Event emitted when trading metrics are updated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        total_pnl: str,
        daily_pnl: str,
        trading_days: int,
        total_trades: int,
        current_balance: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            trading_days=trading_days,
            total_trades=total_trades,
            current_balance=current_balance,
            **kwargs,
        )


class ChallengeExpired(DomainEvent):
    """Event emitted when a challenge expires due to time limit."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        started_at: str,
        expired_at: str,
        max_duration_days: int,
        final_state: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            started_at=started_at,
            expired_at=expired_at,
            max_duration_days=max_duration_days,
            final_state=final_state,
            **kwargs,
        )


class ChallengeRulesUpdated(DomainEvent):
    """Event emitted when challenge rules are updated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        updated_rules: List[str],
        updated_by: UUID,
        reason: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            trader_id=trader_id,
            updated_rules=updated_rules,
            updated_by=updated_by,
            reason=reason,
            **kwargs,
        )