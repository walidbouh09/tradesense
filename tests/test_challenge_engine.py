"""
Exhaustive Unit Tests for Challenge Engine

These tests validate the core domain logic and are designed to be readable
by both developers and risk team members.

Test Scenarios:
1. Normal profitable trading keeps challenge ACTIVE
2. Daily drawdown limit breach causes FAILURE
3. Total drawdown limit breach causes FAILURE
4. Profit target achievement causes FUNDING
5. Attempting trades after FAILURE raises exceptions
6. Daily equity reset occurs at UTC midnight
7. Concurrent trades with identical timestamps are rejected
8. Extreme negative P&L is handled safely (equity floor at zero)
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from domains.challenges.domain.challenge import Challenge, ChallengeParameters
from domains.challenges.domain.enums import ChallengeStatus
from domains.challenges.domain.value_objects import ChallengeId, Money, Percentage, PnL
from domains.challenges.domain.events import TradeExecuted
from domains.challenges.domain.exceptions import (
    InvalidChallengeStateException,
    ConcurrentTradeException,
    InvalidTradeDataException,
)


class TestNormalTradingScenarios:
    """Test normal trading scenarios that keep challenge ACTIVE."""

    def test_profitable_trading_keeps_challenge_active(self):
        """GIVEN a new challenge
        WHEN profitable trades are executed
        THEN challenge remains ACTIVE and equity increases
        """
        # Setup
        challenge = self._create_standard_challenge()

        # Execute profitable trades
        trade1 = self._create_trade_event(pnl=Money(Decimal('200'), 'USD'))
        challenge.on_trade_executed(trade1)

        trade2 = self._create_trade_event(pnl=Money(Decimal('150'), 'USD'))
        challenge.on_trade_executed(trade2)

        # Verify
        assert challenge.status == ChallengeStatus.ACTIVE
        assert challenge.current_equity.amount == Decimal('10350')  # 10000 + 200 + 150
        assert challenge.total_trades == 2
        assert challenge.is_active()

    def test_small_losses_keep_challenge_active(self):
        """GIVEN an active challenge
        WHEN small losses occur within limits
        THEN challenge remains ACTIVE
        """
        # Setup - start with active challenge
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Execute small losses within daily limit (5%)
        loss_trade = self._create_trade_event(pnl=Money(Decimal('-400'), 'USD'))
        challenge.on_trade_executed(loss_trade)

        # Verify still active (daily drawdown = 4% < 5% limit)
        assert challenge.status == ChallengeStatus.ACTIVE
        assert challenge.current_equity.amount == Decimal('9600')  # 10000 + 400 - 400

    def test_mixed_trades_within_limits_stay_active(self):
        """GIVEN an active challenge
        WHEN mix of profits and losses stay within all limits
        THEN challenge remains ACTIVE
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Mix of trades: +300, -200, +100, -150
        trades_pnl = [300, -200, 100, -150]
        expected_equity = Decimal('10000')

        for pnl_amount in trades_pnl:
            trade = self._create_trade_event(pnl=Money(Decimal(str(pnl_amount)), 'USD'))
            challenge.on_trade_executed(trade)
            expected_equity += Decimal(str(pnl_amount))

        assert challenge.status == ChallengeStatus.ACTIVE
        assert challenge.current_equity.amount == expected_equity
        assert challenge.total_trades == 5  # 4 trades + activation trade


class TestFailureScenarios:
    """Test scenarios that cause challenge FAILURE."""

    def test_daily_drawdown_breach_causes_failure(self):
        """GIVEN an active challenge
        WHEN daily loss exceeds 5% limit
        THEN challenge immediately FAILS
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Execute trade that causes >5% daily drawdown
        large_loss = self._create_trade_event(pnl=Money(Decimal('-600'), 'USD'))  # 6% loss
        challenge.on_trade_executed(large_loss)

        # Verify failure
        assert challenge.status == ChallengeStatus.FAILED
        assert challenge.current_equity.amount == Decimal('9400')  # 10000 - 600
        assert challenge.is_terminal()

        # Verify domain events emitted
        events = challenge.domain_events
        assert len(events) >= 3  # StatusChanged, TradeExecuted, ChallengeFailed
        assert any(e.__class__.__name__ == 'ChallengeFailed' for e in events)

    def test_total_drawdown_breach_causes_failure(self):
        """GIVEN an active challenge with profit then large loss
        WHEN total drawdown exceeds 10% limit
        THEN challenge immediately FAILS
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # First build up equity
        profit_trade = self._create_trade_event(pnl=Money(Decimal('500'), 'USD'))
        challenge.on_trade_executed(profit_trade)
        assert challenge.max_equity.amount == Decimal('10500')  # Peak

        # Then lose more than 10% of peak
        large_loss = self._create_trade_event(pnl=Money(Decimal('-1100'), 'USD'))  # 11% of peak
        challenge.on_trade_executed(large_loss)

        # Verify failure due to total drawdown
        assert challenge.status == ChallengeStatus.FAILED
        assert challenge.current_equity.amount == Decimal('9400')  # 10500 - 1100

    def test_multiple_small_losses_can_accumulate_to_failure(self):
        """GIVEN an active challenge
        WHEN multiple small losses accumulate to exceed daily limit
        THEN challenge FAILS
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Multiple losses that individually are ok but combined exceed limit
        losses = [Decimal('-200'), Decimal('-150'), Decimal('-160')]  # Total 6.1% > 5%

        for loss_amount in losses:
            trade = self._create_trade_event(pnl=Money(loss_amount, 'USD'))
            if loss_amount == Decimal('-160'):  # Last trade should fail
                challenge.on_trade_executed(trade)
                assert challenge.status == ChallengeStatus.FAILED
                break
            else:
                challenge.on_trade_executed(trade)
                assert challenge.status == ChallengeStatus.ACTIVE


class TestSuccessScenarios:
    """Test scenarios that cause challenge SUCCESS (FUNDING)."""

    def test_profit_target_achievement_causes_funding(self):
        """GIVEN an active challenge
        WHEN profit reaches 8% target
        THEN challenge becomes FUNDED
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Execute trade that achieves 8% profit target
        profit_trade = self._create_trade_event(pnl=Money(Decimal('800'), 'USD'))  # Exactly 8%
        challenge.on_trade_executed(profit_trade)

        # Verify funding
        assert challenge.status == ChallengeStatus.FUNDED
        assert challenge.current_equity.amount == Decimal('10800')  # 10000 + 800
        assert challenge.is_terminal()

    def test_profit_above_target_still_funded(self):
        """GIVEN an active challenge
        WHEN profit exceeds 8% target
        THEN challenge becomes FUNDED
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Execute trade with >8% profit
        profit_trade = self._create_trade_event(pnl=Money(Decimal('900'), 'USD'))  # 9%
        challenge.on_trade_executed(profit_trade)

        assert challenge.status == ChallengeStatus.FUNDED
        assert challenge.current_equity.amount == Decimal('10900')


class TestInvalidOperationGuards:
    """Test safeguards that prevent invalid operations."""

    def test_trade_after_failure_raises_exception(self):
        """GIVEN a FAILED challenge
        WHEN attempting to process another trade
        THEN InvalidChallengeStateException is raised
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Cause failure
        failure_trade = self._create_trade_event(pnl=Money(Decimal('-600'), 'USD'))
        challenge.on_trade_executed(failure_trade)
        assert challenge.status == ChallengeStatus.FAILED

        # Attempt another trade - should raise exception
        with pytest.raises(InvalidChallengeStateException):
            challenge.on_trade_executed(self._create_trade_event())

    def test_trade_after_funding_raises_exception(self):
        """GIVEN a FUNDED challenge
        WHEN attempting to process another trade
        THEN InvalidChallengeStateException is raised
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Cause funding
        funding_trade = self._create_trade_event(pnl=Money(Decimal('800'), 'USD'))
        challenge.on_trade_executed(funding_trade)
        assert challenge.status == ChallengeStatus.FUNDED

        # Attempt another trade - should raise exception
        with pytest.raises(InvalidChallengeStateException):
            challenge.on_trade_executed(self._create_trade_event())

    def test_concurrent_trades_same_timestamp_rejected(self):
        """GIVEN an active challenge
        WHEN two trades have identical timestamps
        THEN ConcurrentTradeException is raised
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Create two trades with same timestamp
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        trade1 = self._create_trade_event(executed_at=timestamp)
        trade2 = self._create_trade_event(executed_at=timestamp)  # Same timestamp

        # First trade succeeds
        challenge.on_trade_executed(trade1)

        # Second trade with same timestamp fails
        with pytest.raises(ConcurrentTradeException):
            challenge.on_trade_executed(trade2)

    def test_extreme_negative_pnl_handled_safely(self):
        """GIVEN an active challenge
        WHEN trade would cause equity to go negative
        THEN InvalidTradeDataException is raised
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Trade that would make equity negative
        extreme_loss = self._create_trade_event(pnl=Money(Decimal('-15000'), 'USD'))
        challenge.on_trade_executed(extreme_loss)

        # Verify equity is floored at zero, not negative
        assert challenge.current_equity.amount == Decimal('0')
        assert challenge.status == ChallengeStatus.FAILED  # Due to drawdown violation


class TestDailyResetLogic:
    """Test daily reset functionality."""

    def test_daily_reset_at_midnight(self):
        """GIVEN trades across midnight
        WHEN date changes
        THEN daily tracking resets appropriately
        """
        challenge = self._create_standard_challenge()

        # Day 1: profitable trading
        day1_trade = self._create_trade_event(
            executed_at=datetime(2024, 1, 1, 14, 30, 0, tzinfo=timezone.utc)
        )
        challenge.on_trade_executed(day1_trade)

        profit_trade = self._create_trade_event(
            pnl=Money(Decimal('300'), 'USD'),
            executed_at=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        )
        challenge.on_trade_executed(profit_trade)

        # Verify day 1 state
        assert challenge.current_date == datetime(2024, 1, 1).date()
        assert challenge.daily_start_equity.amount == Decimal('10300')  # After profit

        # Day 2: crosses midnight, daily reset occurs
        day2_trade = self._create_trade_event(
            executed_at=datetime(2024, 1, 2, 9, 30, 0, tzinfo=timezone.utc)  # Next day
        )
        challenge.on_trade_executed(day2_trade)

        # Verify daily reset
        assert challenge.current_date == datetime(2024, 1, 2).date()
        assert challenge.daily_start_equity.amount == challenge.current_equity.amount
        assert challenge.daily_max_equity.amount == challenge.current_equity.amount
        assert challenge.daily_min_equity.amount == challenge.current_equity.amount

    def test_daily_drawdown_calculated_correctly(self):
        """GIVEN daily reset
        WHEN calculating drawdown
        THEN uses daily start equity, not overall max
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Build profit then reset daily at midnight
        profit_trade = self._create_trade_event(
            pnl=Money(Decimal('500'), 'USD'),
            executed_at=datetime(2024, 1, 1, 23, 59, 0, tzinfo=timezone.utc)
        )
        challenge.on_trade_executed(profit_trade)

        # Next day starts with reset daily equity
        day2_start = self._create_trade_event(
            executed_at=datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc)
        )
        challenge.on_trade_executed(day2_start)

        # Loss on day 2 - should be calculated from day 2 start
        day2_loss = self._create_trade_event(
            pnl=Money(Decimal('-300'), 'USD'),  # 3% of daily start
            executed_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        )
        challenge.on_trade_executed(day2_loss)

        # Should still be ACTIVE (3% < 5% daily limit)
        assert challenge.status == ChallengeStatus.ACTIVE
        assert challenge.current_equity.amount == Decimal('10200')  # 10500 - 300


class TestValueObjects:
    """Test value object behavior."""

    def test_money_operations(self):
        """Test Money value object operations."""
        money1 = Money(Decimal('100'), 'USD')
        money2 = Money(Decimal('50'), 'USD')

        assert money1 + money2 == Money(Decimal('150'), 'USD')
        assert money1 - money2 == Money(Decimal('50'), 'USD')
        assert money1 * 2 == Money(Decimal('200'), 'USD')

    def test_money_currency_safety(self):
        """Test Money prevents cross-currency operations."""
        usd = Money(Decimal('100'), 'USD')
        eur = Money(Decimal('100'), 'EUR')

        with pytest.raises(ValueError):
            usd + eur

    def test_percentage_validation(self):
        """Test Percentage validates range 0-100."""
        valid_pct = Percentage(Decimal('50'))
        assert valid_pct.value == Decimal('50')

        with pytest.raises(ValueError):
            Percentage(Decimal('150'))  # Too high

        with pytest.raises(ValueError):
            Percentage(Decimal('-10'))  # Negative

    def test_pnl_operations(self):
        """Test P&L value object."""
        pnl1 = PnL(Money(Decimal('100'), 'USD'))
        pnl2 = PnL(Money(Decimal('50'), 'USD'))

        result = pnl1 + pnl2
        assert result.amount == Money(Decimal('150'), 'USD')
        assert result.is_profit()

        loss = PnL(Money(Decimal('-50'), 'USD'))
        assert loss.is_loss()


class TestDomainEvents:
    """Test domain event emission."""

    def test_challenge_activation_emits_events(self):
        """GIVEN a new challenge
        WHEN first trade executes
        THEN ChallengeStatusChanged event is emitted
        """
        challenge = self._create_standard_challenge()

        trade = self._create_trade_event()
        challenge.on_trade_executed(trade)

        events = challenge.domain_events
        assert len(events) >= 1

        status_change_events = [e for e in events if e.__class__.__name__ == 'ChallengeStatusChanged']
        assert len(status_change_events) == 1

        event = status_change_events[0]
        assert event.old_status == ChallengeStatus.PENDING
        assert event.new_status == ChallengeStatus.ACTIVE

    def test_failure_emits_appropriate_events(self):
        """GIVEN an active challenge
        WHEN rule violation occurs
        THEN both ChallengeStatusChanged and ChallengeFailed events emitted
        """
        challenge = self._create_standard_challenge()
        challenge.on_trade_executed(self._create_trade_event())  # Activate

        # Cause failure
        failure_trade = self._create_trade_event(pnl=Money(Decimal('-600'), 'USD'))
        challenge.on_trade_executed(failure_trade)

        events = challenge.domain_events

        # Should have status change and failure events
        status_changes = [e for e in events if e.__class__.__name__ == 'ChallengeStatusChanged']
        failures = [e for e in events if e.__class__.__name__ == 'ChallengeFailed']

        assert len(status_changes) >= 2  # PENDING->ACTIVE, ACTIVE->FAILED
        assert len(failures) == 1

        failure_event = failures[0]
        assert failure_event.failure_reason == "MAX_DAILY_DRAWDOWN"


# Helper methods for test setup

    def _create_standard_challenge(self) -> Challenge:
        """Create a standard challenge for testing."""
        challenge_id = ChallengeId(str(uuid4()))
        trader_id = "test_trader_123"

        parameters = ChallengeParameters(
            initial_balance=Money(Decimal('10000'), 'USD'),
            max_daily_drawdown_percent=Percentage(Decimal('5')),    # 5%
            max_total_drawdown_percent=Percentage(Decimal('10')),   # 10%
            profit_target_percent=Percentage(Decimal('8')),         # 8%
            challenge_type="PHASE_1"
        )

        return Challenge(
            challenge_id=challenge_id,
            trader_id=trader_id,
            parameters=parameters,
            created_at=datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        )

    def _create_trade_event(
        self,
        pnl: Money = None,
        executed_at: datetime = None,
        trade_id: str = None
    ) -> TradeExecuted:
        """Create a TradeExecuted event for testing."""
        if pnl is None:
            pnl = Money(Decimal('100'), 'USD')  # Default profit

        if executed_at is None:
            executed_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        if trade_id is None:
            trade_id = f"trade_{uuid4()}"

        return TradeExecuted(
            aggregate_id=uuid4(),  # Not used in domain logic
            trader_id="test_trader_123",
            trade_id=trade_id,
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=pnl,
            commission=Money(Decimal('5'), 'USD'),
            executed_at=executed_at,
        )