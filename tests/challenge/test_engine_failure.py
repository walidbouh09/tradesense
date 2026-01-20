"""
Unit tests for Challenge Engine failure scenarios.

Tests state transitions that result in challenge termination due to rule violations.
Explicit PnL values and clear assertions of failure reasons.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.domains.challenge.engine import ChallengeEngine, TradeExecutedEvent
from src.domains.challenge.model import Challenge, ChallengeStatus


class TestDailyDrawdownFailure:
    """Test scenarios where daily drawdown limit is exceeded."""

    def test_daily_drawdown_breach_causes_failure(self, active_challenge):
        """WHEN trade causes daily drawdown to exceed 5%
        THEN challenge immediately FAILS with correct reason
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Execute trade causing 6% daily drawdown (above 5% limit)
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="failing_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-600'),  # 6% loss
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Verify failure
        assert active_challenge.status == ChallengeStatus.FAILED
        assert active_challenge.failure_reason == "MAX_DAILY_DRAWDOWN"
        assert active_challenge.current_equity == Decimal('9400')  # 10000 - 600
        assert active_challenge.ended_at == trade_event.executed_at

        # Verify status change event emitted
        event_bus.emit.assert_called_once()
        args = event_bus.emit.call_args
        assert args[0] == "CHALLENGE_STATUS_CHANGED"
        event = args[1]
        assert event.challenge_id == active_challenge.id
        assert event.old_status == "ACTIVE"
        assert event.new_status == "FAILED"
        assert event.reason == "MAX_DAILY_DRAWDOWN"

    def test_daily_drawdown_at_exact_limit_causes_failure(self, active_challenge):
        """WHEN trade causes daily drawdown to equal exactly 5%
        THEN challenge FAILS (strict inequality enforcement)
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Execute trade causing exactly 5% daily drawdown
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="exact_limit_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-500'),  # Exactly 5% loss
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        assert active_challenge.status == ChallengeStatus.FAILED
        assert active_challenge.failure_reason == "MAX_DAILY_DRAWDOWN"
        assert active_challenge.current_equity == Decimal('9500')


class TestTotalDrawdownFailure:
    """Test scenarios where total drawdown limit is exceeded."""

    def test_total_drawdown_breach_causes_failure(self, active_challenge):
        """WHEN trade causes total drawdown from peak to exceed 10%
        THEN challenge FAILS with correct reason
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First build equity to establish higher peak
        profit_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="profit_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('500'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(profit_trade, session)
        assert active_challenge.max_equity_ever == Decimal('10500')

        # Then lose more than 10% of peak
        loss_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="big_loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-1200'),  # 11.4% of peak (1200/10500)
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(loss_trade, session)

        # Verify total drawdown failure
        assert active_challenge.status == ChallengeStatus.FAILED
        assert active_challenge.failure_reason == "MAX_TOTAL_DRAWDOWN"
        assert active_challenge.current_equity == Decimal('9300')  # 10500 - 1200

    def test_total_drawdown_at_exact_limit_causes_failure(self, active_challenge):
        """WHEN trade causes total drawdown to equal exactly 10%
        THEN challenge FAILS (strict inequality enforcement)
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Build to peak then lose exactly 10%
        profit_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="profit_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1000'),  # Peak at 11000
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(profit_trade, session)

        loss_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="exact_loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-1100'),  # Exactly 10% of peak (1100/11000)
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(loss_trade, session)

        assert active_challenge.status == ChallengeStatus.FAILED
        assert active_challenge.failure_reason == "MAX_TOTAL_DRAWDOWN"
        assert active_challenge.current_equity == Decimal('10000')  # 11000 - 1100


class TestFailureTerminalState:
    """Test that ended_at is set correctly when challenges fail."""

    def test_ended_at_set_on_failure(self, active_challenge):
        """WHEN challenge fails due to rule violation
        THEN ended_at timestamp is set to failure time
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        failure_time = datetime(2024, 1, 1, 13, 15, 0, tzinfo=timezone.utc)

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="failure_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-600'),
            executed_at=failure_time
        )

        engine.handle_trade_executed(trade_event, session)

        assert active_challenge.ended_at == failure_time
        assert active_challenge.status == ChallengeStatus.FAILED


class TestEquityUpdateBeforeFailure:
    """Test that equity is updated correctly even when rules cause failure."""

    def test_equity_updated_before_failure_check(self, active_challenge):
        """WHEN trade would cause rule violation
        THEN equity is updated first, then failure is determined
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        initial_equity = active_challenge.current_equity

        # Execute trade that causes failure
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="failing_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-600'),
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Equity should be updated to reflect the trade
        expected_equity = initial_equity + Decimal('-600')
        assert active_challenge.current_equity == expected_equity

        # But status should be FAILED due to rule violation
        assert active_challenge.status == ChallengeStatus.FAILED

        # And max_equity_ever should be updated if this was a new high
        # (though in this case it wasn't)
        if expected_equity > active_challenge.max_equity_ever:
            assert active_challenge.max_equity_ever == expected_equity
        else:
            assert active_challenge.max_equity_ever == initial_equity

    def test_max_equity_ever_updated_before_failure(self, active_challenge):
        """WHEN profitable trade increases equity to new high before causing total drawdown failure
        THEN max_equity_ever is updated correctly
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First make a profit to set a higher peak
        profit_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="profit_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('300'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(profit_trade, session)
        assert active_challenge.max_equity_ever == Decimal('10300')

        # Then lose enough to trigger total drawdown failure
        loss_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="big_loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="15000",
            price="1.0850",
            realized_pnl=Decimal('-1400'),  # 13.6% of peak (1400/10300)
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(loss_trade, session)

        # Verify equity updated and peak maintained
        assert active_challenge.current_equity == Decimal('9900')  # 10300 - 1400
        assert active_challenge.max_equity_ever == Decimal('10300')  # Peak unchanged
        assert active_challenge.status == ChallengeStatus.FAILED
        assert active_challenge.failure_reason == "MAX_TOTAL_DRAWDOWN"