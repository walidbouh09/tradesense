"""
Challenge Engine - Core Business Logic

Handles TRADE_EXECUTED events, enforces state machine rules, updates equity safely.
All operations are synchronous and transaction-safe.

Flow for each trade:
1. Reject trade if challenge not ACTIVE
2. Handle daily equity reset
3. Update current_equity & max_equity_ever
4. Evaluate rules
5. Update status if changed
6. Emit CHALLENGE_STATUS_CHANGED event
7. Commit DB transaction
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from core.event_bus import event_bus
from .model import Challenge, ChallengeStatus
from .rules import ChallengeRulesEngine, RuleEvaluationResult


class TradeExecutedEvent:
    """
    Domain event representing a trade execution.

    This is the input event that triggers challenge evaluation.
    """
    def __init__(
        self,
        challenge_id: UUID,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        realized_pnl: Decimal,
        executed_at: datetime,
    ):
        self.challenge_id = challenge_id
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.realized_pnl = realized_pnl
        self.executed_at = executed_at


class ChallengeStatusChangedEvent:
    """
    Domain event emitted when challenge status changes.

    This captures all status transitions for audit and analytics.
    """
    def __init__(
        self,
        challenge_id: UUID,
        old_status: str,
        new_status: str,
        reason: Optional[str],
        changed_at: datetime,
    ):
        self.challenge_id = challenge_id
        self.old_status = old_status
        self.new_status = new_status
        self.reason = reason
        self.changed_at = changed_at


class ChallengeEngine:
    """
    Core challenge evaluation engine.

    Handles trade execution events and enforces all challenge rules.
    All state changes happen within a single database transaction.
    """

    def __init__(self):
        """
        Initialize Challenge Engine.

        Uses global event bus for emitting domain events.
        No external dependencies required.
        """
        pass  # Uses global event_bus

    def handle_trade_executed(self, event: TradeExecutedEvent, session: Session) -> None:
        """
        Handle a trade execution event.

        This is the main entry point for challenge evaluation.
        All operations happen within the provided database session (transaction).

        Args:
            event: The trade execution event
            session: SQLAlchemy session for database operations

        Raises:
            ValueError: If trade cannot be processed (invalid state, etc.)
        """
        # Load challenge for update (pessimistic locking)
        challenge = session.query(Challenge).filter(
            Challenge.id == event.challenge_id
        ).with_for_update().first()

        if challenge is None:
            raise ValueError(f"Challenge {event.challenge_id} not found")

        # Step 1: Reject trade if challenge not ACTIVE
        self._validate_trade_allowed(challenge, event)

        # Step 2: Handle daily equity reset if date changed
        self._handle_daily_reset(challenge, event.executed_at)

        # Step 3: Update equity safely
        self._update_equity(challenge, event)

        # Step 4: Evaluate rules against new state
        rule_result = self._evaluate_rules(challenge)

        # Step 5: Update status if rules triggered change
        status_changed = self._update_status_if_changed(challenge, rule_result, event.executed_at)

        # Step 6: Emit domain events
        self._emit_events(challenge, status_changed, event)

        # Step 7: Transaction committed by caller

    def _validate_trade_allowed(self, challenge: Challenge, event: TradeExecutedEvent) -> None:
        """
        Validate that trade is allowed for current challenge state.

        Invariant: Only ACTIVE challenges accept trades.
        PENDING challenges transition to ACTIVE on first trade.
        Terminal states (FAILED/FUNDED) reject all trades.
        """
        if challenge.status == ChallengeStatus.FAILED:
            raise ValueError(f"Trade rejected: Challenge {challenge.id} already FAILED")

        if challenge.status == ChallengeStatus.FUNDED:
            raise ValueError(f"Trade rejected: Challenge {challenge.id} already FUNDED")

        if challenge.status == ChallengeStatus.PENDING:
            # First trade activates the challenge
            challenge.status = ChallengeStatus.ACTIVE
            challenge.started_at = event.executed_at

        # ACTIVE challenges are allowed to continue trading

    def _handle_daily_reset(self, challenge: Challenge, executed_at: datetime) -> None:
        """
        Handle daily equity reset if trading date changed.

        Invariant: Daily tracking resets at UTC midnight.
        This ensures drawdown calculations use correct daily baseline.
        """
        trade_date = executed_at.date()

        if trade_date != challenge.current_date:
            # Date changed - reset daily tracking
            challenge.current_date = trade_date
            challenge.daily_start_equity = challenge.current_equity
            challenge.daily_max_equity = challenge.current_equity
            challenge.daily_min_equity = challenge.current_equity

    def _update_equity(self, challenge: Challenge, event: TradeExecutedEvent) -> None:
        """
        Update challenge equity after trade execution.

        Invariants:
        - current_equity = previous_equity + realized_pnl
        - current_equity never goes below zero (floor at zero)
        - max_equity_ever tracks all-time peak
        - daily_min/max_equity updated for monitoring

        Emits EQUITY_UPDATED event for real-time UI updates.
        Event emitted AFTER equity state is fully consistent.
        """
        # Store previous equity for event payload
        previous_equity = challenge.current_equity

        # Calculate new equity
        new_equity = challenge.current_equity + event.realized_pnl

        # Floor equity at zero (cannot go negative)
        if new_equity < 0:
            new_equity = Decimal('0')

        # Update current equity
        challenge.current_equity = new_equity

        # Update all-time maximum
        if challenge.current_equity > challenge.max_equity_ever:
            challenge.max_equity_ever = challenge.current_equity

        # Update daily tracking
        if challenge.current_equity > challenge.daily_max_equity:
            challenge.daily_max_equity = challenge.current_equity
        if challenge.current_equity < challenge.daily_min_equity:
            challenge.daily_min_equity = challenge.current_equity

        # Update performance tracking
        challenge.total_trades += 1
        challenge.total_pnl += event.realized_pnl
        challenge.last_trade_at = event.executed_at

        # Emit real-time equity update event
        # This happens AFTER all equity state is consistent
        event_bus.emit('EQUITY_UPDATED', {
            'challenge_id': str(challenge.id),
            'user_id': str(challenge.user_id),
            'previous_equity': str(previous_equity),
            'current_equity': str(challenge.current_equity),
            'max_equity_ever': str(challenge.max_equity_ever),
            'daily_start_equity': str(challenge.daily_start_equity),
            'daily_max_equity': str(challenge.daily_max_equity),
            'daily_min_equity': str(challenge.daily_min_equity),
            'total_pnl': str(challenge.total_pnl),
            'total_trades': challenge.total_trades,
            'last_trade_at': challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
            'trade_pnl': str(event.realized_pnl),
            'trade_symbol': event.symbol,
            'executed_at': event.executed_at.isoformat(),
        })

    def _evaluate_rules(self, challenge: Challenge) -> RuleEvaluationResult:
        """
        Evaluate challenge rules against current state.

        Uses pure business logic (ChallengeRulesEngine) for deterministic evaluation.
        Emits risk alerts for monitoring when thresholds are approached.
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status=challenge.status,
            current_equity=challenge.current_equity,
            max_equity_ever=challenge.max_equity_ever,
            daily_start_equity=challenge.daily_start_equity,
            initial_balance=challenge.initial_balance,
            max_daily_drawdown_percent=challenge.max_daily_drawdown_percent,
            max_total_drawdown_percent=challenge.max_total_drawdown_percent,
            profit_target_percent=challenge.profit_target_percent,
        )

        # Emit risk alerts for monitoring (not part of core decision logic)
        self._emit_risk_alerts_if_needed(challenge, result)

        return result

    def _update_status_if_changed(
        self,
        challenge: Challenge,
        rule_result: RuleEvaluationResult,
        executed_at: datetime
    ) -> bool:
        """
        Update challenge status if rules triggered a change.

        Invariants:
        - Only ACTIVE challenges can transition to FAILED/FUNDED
        - Terminal states are final (no further transitions)
        - Status changes are timestamped
        """
        if rule_result.new_status == challenge.status:
            return False  # No change

        # Validate state transition
        self._validate_status_transition(challenge.status, rule_result.new_status)

        # Update status
        old_status = challenge.status
        challenge.status = rule_result.new_status

        # Set terminal state timestamps
        if rule_result.new_status in (ChallengeStatus.FAILED, ChallengeStatus.FUNDED):
            challenge.ended_at = executed_at
            if rule_result.new_status == ChallengeStatus.FUNDED:
                challenge.funded_at = executed_at

        # Record failure reason
        if rule_result.new_status == ChallengeStatus.FAILED:
            challenge.failure_reason = rule_result.reason

        # Update version for optimistic locking
        challenge.version += 1

        return True  # Status changed

    def _emit_risk_alerts_if_needed(self, challenge: Challenge, rule_result: RuleEvaluationResult) -> None:
        """
        Emit risk alerts for monitoring when rule thresholds are approached.

        Risk alerts are NOT part of core decision logic - they are for monitoring only.
        Alerts are emitted when equity approaches but doesn't exceed rule limits.

        Why here: Risk evaluation provides complete context for alert generation.
        """
        # Calculate current risk metrics
        daily_drawdown_pct = ChallengeRulesEngine.calculate_daily_drawdown_percentage(
            challenge.current_equity, challenge.daily_start_equity
        )
        total_drawdown_pct = ChallengeRulesEngine.calculate_total_drawdown_percentage(
            challenge.current_equity, challenge.max_equity_ever
        )

        # Alert thresholds (more conservative than rule limits)
        daily_alert_threshold = challenge.max_daily_drawdown_percent * Decimal('0.8')  # 80% of limit
        total_alert_threshold = challenge.max_total_drawdown_percent * Decimal('0.8')  # 80% of limit

        # Emit daily drawdown alert
        if daily_drawdown_pct >= daily_alert_threshold:
            event_bus.emit('RISK_ALERT', {
                'challenge_id': str(challenge.id),
                'user_id': str(challenge.user_id),
                'alert_type': 'HIGH_DAILY_DRAWDOWN',
                'severity': 'MEDIUM',
                'title': 'High Daily Drawdown Warning',
                'message': f'Daily drawdown at {daily_drawdown_pct:.1f}% (limit: {challenge.max_daily_drawdown_percent:.1f}%)',
                'current_equity': str(challenge.current_equity),
                'daily_start_equity': str(challenge.daily_start_equity),
                'drawdown_percentage': str(daily_drawdown_pct),
                'threshold_percentage': str(challenge.max_daily_drawdown_percent),
                'alert_timestamp': challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
            })

        # Emit total drawdown alert
        if total_drawdown_pct >= total_alert_threshold:
            event_bus.emit('RISK_ALERT', {
                'challenge_id': str(challenge.id),
                'user_id': str(challenge.user_id),
                'alert_type': 'HIGH_TOTAL_DRAWDOWN',
                'severity': 'HIGH',
                'title': 'High Total Drawdown Warning',
                'message': f'Total drawdown at {total_drawdown_pct:.1f}% (limit: {challenge.max_total_drawdown_percent:.1f}%)',
                'current_equity': str(challenge.current_equity),
                'max_equity_ever': str(challenge.max_equity_ever),
                'drawdown_percentage': str(total_drawdown_pct),
                'threshold_percentage': str(challenge.max_total_drawdown_percent),
                'alert_timestamp': challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
            })

    def _validate_status_transition(self, old_status: str, new_status: str) -> None:
        """
        Validate state machine transitions.

        Allowed transitions:
        PENDING → ACTIVE
        ACTIVE → FAILED
        ACTIVE → FUNDED

        Terminal states (FAILED/FUNDED) cannot transition.
        """
        valid_transitions = {
            ChallengeStatus.PENDING: {ChallengeStatus.ACTIVE},
            ChallengeStatus.ACTIVE: {ChallengeStatus.FAILED, ChallengeStatus.FUNDED},
            ChallengeStatus.FAILED: set(),  # Terminal
            ChallengeStatus.FUNDED: set(),  # Terminal
        }

        if new_status not in valid_transitions.get(old_status, set()):
            raise ValueError(f"Invalid status transition: {old_status} → {new_status}")

    def _emit_events(
        self,
        challenge: Challenge,
        status_changed: bool,
        trade_event: TradeExecutedEvent
    ) -> None:
        """
        Emit domain events for audit and analytics.

        Events emitted:
        - CHALLENGE_STATUS_CHANGED: When status transitions occur
        """
        if status_changed:
            # Determine old status (before this trade)
            old_status = self._determine_old_status(challenge, trade_event)

            event = ChallengeStatusChangedEvent(
                challenge_id=challenge.id,
                old_status=old_status,
                new_status=challenge.status,
                reason=getattr(challenge, 'failure_reason', None),
                changed_at=trade_event.executed_at,
            )

            event_bus.emit("CHALLENGE_STATUS_CHANGED", event)

    def _determine_old_status(self, challenge: Challenge, trade_event: TradeExecutedEvent) -> str:
        """
        Determine the old status before this trade execution.

        This is needed for accurate event emission.
        """
        # If this was the first trade (PENDING → ACTIVE), old status was PENDING
        if challenge.total_trades == 1:
            return ChallengeStatus.PENDING

        # Otherwise, old status was ACTIVE (since only ACTIVE challenges reach this point)
        return ChallengeStatus.ACTIVE