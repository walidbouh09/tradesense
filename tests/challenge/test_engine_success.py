"""
Unit tests for successful Challenge Engine scenarios.

Tests state transitions that result in continued trading or successful funding.
Uses ChallengeEngine directly with controlled timestamps and mock event bus.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.domains.challenge.engine import ChallengeEngine, TradeExecutedEvent
from src.domains.challenge.model import Challenge, ChallengeStatus


class TestActiveTradingContinues:
    """Test scenarios where trading continues in ACTIVE state."""

    def test_trade_keeps_challenge_active(self, active_challenge):
        """WHEN profitable trade executed on active challenge
        THEN challenge remains ACTIVE with updated equity
        """
        # Setup
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)

        # Mock database session (not used in business logic)
        session = Mock()

        # Execute trade
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('200'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )

        # Process trade
        engine.handle_trade_executed(trade_event, session)

        # Verify challenge remains ACTIVE
        assert active_challenge.status == ChallengeStatus.ACTIVE

        # Verify equity updated correctly
        assert active_challenge.current_equity == Decimal('10200')  # 10000 + 200
        assert active_challenge.max_equity_ever == Decimal('10200')  # New peak

        # Verify trade tracking
        assert active_challenge.total_trades == 2  # 1 (activation) + 1 (this trade)
        assert active_challenge.total_pnl == Decimal('200')
        assert active_challenge.last_trade_at == trade_event.executed_at

        # Verify no status change events emitted (remains ACTIVE)
        event_bus.emit.assert_not_called()

    def test_multiple_profitable_trades_accumulate_correctly(self, active_challenge):
        """WHEN multiple profitable trades executed
        THEN equity and statistics accumulate correctly
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First trade: +300
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('300'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade1, session)

        # Second trade: +150
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_002",
            symbol="GBPUSD",
            side="SELL",
            quantity="5000",
            price="1.2650",
            realized_pnl=Decimal('150'),
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade2, session)

        # Verify accumulated results
        assert active_challenge.status == ChallengeStatus.ACTIVE
        assert active_challenge.current_equity == Decimal('10450')  # 10000 + 300 + 150
        assert active_challenge.max_equity_ever == Decimal('10450')
        assert active_challenge.total_trades == 3  # 1 + 2 trades
        assert active_challenge.total_pnl == Decimal('450')
        assert active_challenge.last_trade_at == trade2.executed_at


class TestProfitTargetAchievement:
    """Test scenarios where profit target is reached and challenge becomes FUNDED."""

    def test_trade_reaches_profit_target_becomes_funded(self, active_challenge):
        """WHEN trade reaches exact 10% profit target
        THEN challenge becomes FUNDED
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Execute trade that achieves 10% profit target
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="winning_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1000'),  # Exactly 10% of $10K
            executed_at=datetime(2024, 1, 1, 14, 30, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Verify challenge becomes FUNDED
        assert active_challenge.status == ChallengeStatus.FUNDED
        assert active_challenge.current_equity == Decimal('11000')
        assert active_challenge.funded_at == trade_event.executed_at

        # Verify status change event emitted
        event_bus.emit.assert_called_once()
        args = event_bus.emit.call_args
        assert args[0] == "CHALLENGE_STATUS_CHANGED"
        event = args[1]
        assert event.challenge_id == active_challenge.id
        assert event.old_status == "ACTIVE"
        assert event.new_status == "FUNDED"
        assert event.reason == "PROFIT_TARGET"
        assert event.changed_at == trade_event.executed_at

    def test_trade_exceeds_profit_target_becomes_funded(self, active_challenge):
        """WHEN trade exceeds 10% profit target
        THEN challenge becomes FUNDED
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Execute trade with 12% profit
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="big_win",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1200'),  # 12% profit
            executed_at=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        assert active_challenge.status == ChallengeStatus.FUNDED
        assert active_challenge.current_equity == Decimal('11200')
        assert active_challenge.funded_at == trade_event.executed_at


class TestTerminalStateTimestamps:
    """Test that ended_at is set correctly when challenges become FUNDED."""

    def test_ended_at_set_on_funding(self, active_challenge):
        """WHEN challenge becomes FUNDED
        THEN ended_at timestamp is set to funding time
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        funding_time = datetime(2024, 1, 2, 16, 45, 0, tzinfo=timezone.utc)

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="funding_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1000'),
            executed_at=funding_time
        )

        engine.handle_trade_executed(trade_event, session)

        assert active_challenge.ended_at == funding_time
        assert active_challenge.funded_at == funding_time


class TestEquityPeakTracking:
    """Test that max_equity_ever updates correctly during profitable trading."""

    def test_max_equity_ever_updates_on_new_highs(self, active_challenge):
        """WHEN equity reaches new all-time high
        THEN max_equity_ever is updated correctly
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First trade: +200 (new high: 10200)
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('200'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade1, session)
        assert active_challenge.max_equity_ever == Decimal('10200')

        # Second trade: -100 (lower but still above initial)
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_002",
            symbol="EURUSD",
            side="SELL",
            quantity="5000",
            price="1.0850",
            realized_pnl=Decimal('-100'),
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade2, session)
        assert active_challenge.max_equity_ever == Decimal('10200')  # Unchanged

        # Third trade: +300 (new high: 10400)
        trade3 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_003",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('300'),
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade3, session)
        assert active_challenge.max_equity_ever == Decimal('10400')  # Updated to new high

    def test_max_equity_ever_never_decreases(self, active_challenge):
        """WHEN equity decreases from peak
        THEN max_equity_ever maintains the all-time high
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Build up to peak
        peak_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="peak_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('500'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(peak_trade, session)
        assert active_challenge.max_equity_ever == Decimal('10500')

        # Subsequent losses don't reduce the peak
        loss_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('-800'),
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(loss_trade, session)

        # Peak remains unchanged despite losses
        assert active_challenge.max_equity_ever == Decimal('10500')
        assert active_challenge.current_equity == Decimal('9700')  # 10500 - 800