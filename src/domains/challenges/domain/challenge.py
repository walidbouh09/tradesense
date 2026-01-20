"""
Challenge Aggregate Root - Core Domain Logic

Responsibilities:
- Hold challenge state (ACTIVE/FAILED/FUNDED)
- Apply trade PnL synchronously
- Track equity, daily reset, max equity
- Evaluate rules deterministically
- Emit domain events on state change

State Machine:
PENDING → ACTIVE → (FAILED | FUNDED)
Terminal states: FAILED, FUNDED
"""

from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

from shared.kernel.entity import AggregateRoot
from shared.kernel.events import DomainEvent

from .enums import ChallengeStatus
from .value_objects import ChallengeId, Money, Percentage, PnL
from .events import TradeExecuted, ChallengeStatusChanged, ChallengeFailed, ChallengeFunded
from .rules import RiskRuleEvaluator, RiskEvaluationResult
from .exceptions import (
    InvalidChallengeStateException,
    ConcurrentTradeException,
    InvalidTradeDataException,
    ChallengeInvariantViolationException,
)


class ChallengeParameters:
    """Challenge configuration parameters."""

    def __init__(
        self,
        initial_balance: Money,
        max_daily_drawdown_percent: Percentage,
        max_total_drawdown_percent: Percentage,
        profit_target_percent: Percentage,
        challenge_type: str,
    ):
        self.initial_balance = initial_balance
        self.max_daily_drawdown_percent = max_daily_drawdown_percent
        self.max_total_drawdown_percent = max_total_drawdown_percent
        self.profit_target_percent = profit_target_percent
        self.challenge_type = challenge_type


class Challenge(AggregateRoot):
    """
    Challenge Aggregate Root.

    Core invariants:
    - Equity never goes below zero
    - Daily drawdown resets at UTC midnight
    - State transitions are immutable
    - All calculations use Decimal precision
    """

    def __init__(
        self,
        challenge_id: ChallengeId,
        trader_id: str,
        parameters: ChallengeParameters,
        created_at: datetime,
    ):
        super().__init__(challenge_id.value)

        # Identity
        self.challenge_id = challenge_id
        self.trader_id = trader_id
        self.parameters = parameters

        # Status - starts PENDING, transitions to ACTIVE on first trade
        self.status = ChallengeStatus.PENDING

        # Equity tracking
        self.current_equity = parameters.initial_balance
        self.max_equity = parameters.initial_balance  # All-time high

        # Daily tracking (resets at UTC midnight)
        self.daily_start_equity = parameters.initial_balance
        self.daily_max_equity = parameters.initial_balance
        self.daily_min_equity = parameters.initial_balance
        self.current_date = created_at.date()

        # Performance tracking
        self.total_trades = 0
        self.total_pnl = PnL(Money(Decimal('0'), parameters.initial_balance.currency))

        # Timestamps
        self._created_at = created_at  # Override Entity's created_at
        self.started_at: Optional[datetime] = None  # When first trade occurs
        self.completed_at: Optional[datetime] = None  # When FAILED or FUNDED
        self.last_trade_at: Optional[datetime] = None

        # Version for optimistic locking
        self.version = 0

    @property
    def created_at(self) -> datetime:
        """Get the challenge creation timestamp."""
        return self._created_at

    def check_version(self, expected_version: int) -> None:
        """
        Check optimistic locking version.

        Raises exception if versions don't match, indicating concurrent modification.
        """
        if self.version != expected_version:
            raise ChallengeInvariantViolationException(
                f"Version mismatch: expected {expected_version}, got {self.version}. "
                f"Concurrent modification detected.",
                str(self.challenge_id.value)
            )

    def on_trade_executed(self, event: TradeExecuted) -> None:
        """
        Process a trade execution.

        This is the main entry point for challenge state changes.
        Follows the exact sequence: update_equity → check_daily_reset → evaluate_risk_rules → enforce_state_machine

        Guards:
        - Challenge must be PENDING or ACTIVE (not terminal)
        - Trade timestamp must be after last trade (prevents concurrent trades)
        - P&L must not cause extreme negative equity
        """
        # Guard 1: Challenge must be in valid state for trade processing
        self._guard_valid_trade_state(event)

        # Guard 2: Prevent concurrent trades (same millisecond)
        self._guard_concurrent_trade(event)

        # Guard 3: Validate trade data doesn't cause extreme negative equity
        self._guard_extreme_negative_pnl(event)

        # State transition: PENDING → ACTIVE on first trade
        if self.status == ChallengeStatus.PENDING:
            self._activate_challenge(event.executed_at)

        # Core processing sequence
        self._update_equity(event.realized_pnl, event.executed_at)
        self._check_daily_reset(event.executed_at)
        evaluation_result = self._evaluate_risk_rules()

        # Apply rule evaluation result
        if evaluation_result.status != self.status:
            self._change_status(evaluation_result.status, evaluation_result.rule_triggered, event.executed_at)

    def _guard_valid_trade_state(self, event: TradeExecuted) -> None:
        """
        Guard: Trade can only be processed on PENDING or ACTIVE challenges.

        Why: Terminal states (FAILED/FUNDED) are immutable. No further trades allowed.
        """
        if self.status.is_terminal():
            raise InvalidChallengeStateException(
                f"Cannot process trade on {self.status.value} challenge. "
                f"Challenge completed at {self.completed_at}",
                str(self.challenge_id.value)
            )

        if self.status not in {ChallengeStatus.PENDING, ChallengeStatus.ACTIVE}:
            raise ChallengeInvariantViolationException(
                f"Challenge in unexpected state: {self.status.value}",
                str(self.challenge_id.value)
            )

    def _guard_concurrent_trade(self, event: TradeExecuted) -> None:
        """
        Guard: Prevent trades with identical timestamps.

        Why: Concurrent trades at same millisecond could cause race conditions
        in equity calculations and state transitions.
        """
        if (self.last_trade_at is not None and
            event.executed_at == self.last_trade_at):
            raise ConcurrentTradeException(
                f"Concurrent trade detected at {event.executed_at}. "
                f"Previous trade: {self.last_trade_at}",
                str(self.challenge_id.value)
            )

    def _guard_extreme_negative_pnl(self, event: TradeExecuted) -> None:
        """
        Guard: P&L must not cause equity to go below zero.

        Note: While equity flooring is handled in _update_equity,
        this guard prevents extreme negative P&L that might indicate
        data corruption or invalid trade processing.
        """
        if self.status == ChallengeStatus.ACTIVE:
            # Calculate what equity would be after this trade
            projected_equity = self.current_equity + event.realized_pnl.amount

            # Allow equity to go to zero, but not below
            if projected_equity.amount < 0:
                raise InvalidTradeDataException(
                    f"Trade would cause equity to go negative: "
                    f"Current: ${self.current_equity.amount}, "
                    f"P&L: ${event.realized_pnl.amount.amount}, "
                    f"Projected: ${projected_equity.amount}",
                    str(self.challenge_id.value)
                )

    def _activate_challenge(self, executed_at: datetime) -> None:
        """Activate challenge on first trade."""
        self.status = ChallengeStatus.ACTIVE
        self.started_at = executed_at
        self.add_domain_event(ChallengeStatusChanged(
            aggregate_id=self.challenge_id.value,
            trader_id=self.trader_id,
            old_status=ChallengeStatus.PENDING,
            new_status=ChallengeStatus.ACTIVE,
            changed_at=executed_at,
            version=self.version,
        ))

    def _update_equity(self, realized_pnl: PnL, executed_at: datetime) -> None:
        """
        Update equity with realized P&L.

        Invariants:
        - Equity = previous equity + realized P&L
        - Equity never goes below zero (floor at zero)
        - Max equity tracks all-time high
        """
        # Calculate new equity
        new_equity = self.current_equity + realized_pnl.amount

        # Floor equity at zero (cannot go negative)
        if new_equity.amount < 0:
            new_equity = Money(Decimal('0'), new_equity.currency)

        # Update equity
        self.current_equity = new_equity

        # Update max equity (all-time high water mark)
        if self.current_equity > self.max_equity:
            self.max_equity = self.current_equity

        # Update total P&L
        self.total_pnl = self.total_pnl + realized_pnl

        # Update trade count and timestamp
        self.total_trades += 1
        self.last_trade_at = executed_at

    def _check_daily_reset(self, executed_at: datetime) -> None:
        """
        Check if daily tracking needs to reset at UTC midnight.

        Invariants:
        - Daily values reset when date changes
        - Daily start equity = equity at start of new day
        - Daily max/min reset for new day tracking
        """
        trade_date = executed_at.date()

        if trade_date != self.current_date:
            # Date changed - reset daily tracking
            self.current_date = trade_date
            self.daily_start_equity = self.current_equity
            self.daily_max_equity = self.current_equity
            self.daily_min_equity = self.current_equity
        else:
            # Same day - update daily min/max
            if self.current_equity > self.daily_max_equity:
                self.daily_max_equity = self.current_equity
            if self.current_equity < self.daily_min_equity:
                self.daily_min_equity = self.current_equity

    def _evaluate_risk_rules(self) -> RiskEvaluationResult:
        """
        Evaluate risk rules using extracted rule evaluator.

        Delegates to RiskRuleEvaluator for deterministic evaluation.
        """
        return RiskRuleEvaluator.evaluate_rules(
            current_equity=self.current_equity,
            max_equity=self.max_equity,
            daily_start_equity=self.daily_start_equity,
            initial_balance=self.parameters.initial_balance,
            max_daily_drawdown_percent=self.parameters.max_daily_drawdown_percent,
            max_total_drawdown_percent=self.parameters.max_total_drawdown_percent,
            profit_target_percent=self.parameters.profit_target_percent,
        )


    def _change_status(
        self,
        new_status: ChallengeStatus,
        rule_triggered: Optional[str],
        changed_at: datetime
    ) -> None:
        """
        Change challenge status with proper state machine enforcement.

        Invariants:
        - Only valid transitions allowed
        - Terminal states set completed_at
        - Domain events emitted for all changes
        """
        if not self.status.can_transition_to(new_status):
            raise ValueError(f"Invalid status transition: {self.status.value} → {new_status.value}")

        old_status = self.status
        self.status = new_status

        if new_status.is_terminal():
            self.completed_at = changed_at

        # Increment version for optimistic locking
        self.version += 1

        # Emit status change event
        self.add_domain_event(ChallengeStatusChanged(
            aggregate_id=self.challenge_id.value,
            trader_id=self.trader_id,
            old_status=old_status,
            new_status=new_status,
            changed_at=changed_at,
            rule_triggered=rule_triggered,
            version=self.version,
        ))

        # Emit terminal state events
        if new_status == ChallengeStatus.FAILED:
            self.add_domain_event(ChallengeFailed(
                aggregate_id=self.challenge_id.value,
                trader_id=self.trader_id,
                failure_reason=rule_triggered or "RULE_VIOLATION",
                final_equity=self.current_equity,
                total_trades=self.total_trades,
                completed_at=changed_at,
                version=self.version,
            ))
        elif new_status == ChallengeStatus.FUNDED:
            self.add_domain_event(ChallengeFunded(
                aggregate_id=self.challenge_id.value,
                trader_id=self.trader_id,
                final_equity=self.current_equity,
                profit_achieved=self.current_equity - self.parameters.initial_balance,
                total_trades=self.total_trades,
                funded_at=changed_at,
                version=self.version,
            ))

    # Public query methods for external access
    def is_active(self) -> bool:
        """Check if challenge is currently active."""
        return self.status == ChallengeStatus.ACTIVE

    def is_terminal(self) -> bool:
        """Check if challenge is in terminal state."""
        return self.status.is_terminal()

    def get_daily_drawdown_percentage(self) -> Percentage:
        """Get current daily drawdown percentage."""
        return self._calculate_daily_drawdown_percentage()

    def get_total_drawdown_percentage(self) -> Percentage:
        """Get current total drawdown percentage."""
        return self._calculate_total_drawdown_percentage()

    def get_profit_percentage(self) -> Percentage:
        """Get current profit percentage."""
        return self._calculate_profit_percentage()


class RiskEvaluationResult:
    """Result of risk rule evaluation."""

    def __init__(
        self,
        status: ChallengeStatus,
        rule_triggered: Optional[str],
        computed_metrics: dict,
    ):
        self.status = status
        self.rule_triggered = rule_triggered
        self.computed_metrics = computed_metrics