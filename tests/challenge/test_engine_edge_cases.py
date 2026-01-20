"""
Unit tests for temporal edge cases in Challenge Engine.

Tests daily reset logic, timestamp handling, and time-based edge cases.
All timestamps are UTC and explicitly controlled.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.domains.challenge.engine import ChallengeEngine, TradeExecutedEvent
from src.domains.challenge.model import Challenge, ChallengeStatus


class TestDailyResetLogic:
    """Test daily equity reset functionality."""

    def test_daily_equity_resets_when_trade_date_changes(self, active_challenge):
        """WHEN trade executed on different date than current_date
        THEN daily equity tracking resets appropriately
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Initial state: Day 1
        assert active_challenge.current_date == datetime(2024, 1, 1).date()
        assert active_challenge.daily_start_equity == Decimal('10000')

        # Execute trade on Day 2 (different date)
        day2_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="day2_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('200'),
            executed_at=datetime(2024, 1, 2, 9, 30, 0, tzinfo=timezone.utc)  # Day 2
        )

        engine.handle_trade_executed(day2_trade, session)

        # Verify daily reset occurred
        assert active_challenge.current_date == datetime(2024, 1, 2).date()
        assert active_challenge.daily_start_equity == Decimal('10200')  # Equity after Day 1 trade
        assert active_challenge.daily_max_equity == Decimal('10200')   # Reset to current equity
        assert active_challenge.daily_min_equity == Decimal('10200')   # Reset to current equity

    def test_no_daily_reset_for_same_day_trades(self, active_challenge):
        """WHEN multiple trades executed on same day
        THEN daily tracking accumulates without reset
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        initial_daily_start = active_challenge.daily_start_equity

        # First trade on same day
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

        # Second trade on same day
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

        # Daily tracking should NOT reset
        assert active_challenge.current_date == datetime(2024, 1, 1).date()
        assert active_challenge.daily_start_equity == initial_daily_start  # Unchanged

        # Daily highs/lows should accumulate
        assert active_challenge.daily_max_equity == Decimal('10300')  # Peak after first trade
        assert active_challenge.daily_min_equity == Decimal('10200')  # Low after second trade


class TestTimestampUpdates:
    """Test timestamp field updates."""

    def test_last_trade_at_updated_correctly(self, active_challenge):
        """WHEN trade executed
        THEN last_trade_at is updated to trade execution time
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_time = datetime(2024, 1, 1, 14, 45, 30, tzinfo=timezone.utc)

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="timestamp_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=trade_time
        )

        engine.handle_trade_executed(trade_event, session)

        assert active_challenge.last_trade_at == trade_time

    def test_last_trade_at_overwrites_previous(self, active_challenge):
        """WHEN multiple trades executed
        THEN last_trade_at reflects most recent trade time
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First trade
        first_trade_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=first_trade_time
        )
        engine.handle_trade_executed(trade1, session)
        assert active_challenge.last_trade_at == first_trade_time

        # Second trade (later time)
        second_trade_time = datetime(2024, 1, 1, 15, 30, 0, tzinfo=timezone.utc)
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_002",
            symbol="EURUSD",
            side="SELL",
            quantity="5000",
            price="1.0850",
            realized_pnl=Decimal('-50'),
            executed_at=second_trade_time
        )
        engine.handle_trade_executed(trade2, session)

        # Should reflect most recent trade
        assert active_challenge.last_trade_at == second_trade_time


class TestSameTimestampHandling:
    """Test handling of trades with identical timestamps."""

    def test_trades_with_same_timestamp_processed_sequentially(self, active_challenge):
        """WHEN two trades have identical timestamps
        THEN they are processed correctly in sequence
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Two trades with exact same timestamp
        same_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('200'),
            executed_at=same_time
        )

        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_002",
            symbol="GBPUSD",
            side="SELL",
            quantity="5000",
            price="1.2650",
            realized_pnl=Decimal('150'),
            executed_at=same_time  # Same timestamp
        )

        # Process both trades
        engine.handle_trade_executed(trade1, session)
        engine.handle_trade_executed(trade2, session)

        # Equity should accumulate both trades
        expected_equity = Decimal('10000') + Decimal('200') + Decimal('150')
        assert active_challenge.current_equity == expected_equity

        # Trade count should be correct
        assert active_challenge.total_trades == 3  # 1 activation + 2 trades

        # Last trade timestamp should be updated
        assert active_challenge.last_trade_at == same_time

    def test_same_timestamp_trades_daily_tracking(self, active_challenge):
        """WHEN multiple trades at same timestamp
        THEN daily high/low tracking works correctly
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        same_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # First trade: +300 (new high)
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('300'),
            executed_at=same_time
        )
        engine.handle_trade_executed(trade1, session)

        # Second trade: -100 (lower but still above start)
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="trade_002",
            symbol="EURUSD",
            side="SELL",
            quantity="5000",
            price="1.0850",
            realized_pnl=Decimal('-100'),
            executed_at=same_time
        )
        engine.handle_trade_executed(trade2, session)

        # Daily tracking should reflect both trades
        assert active_challenge.daily_max_equity == Decimal('10300')  # Peak after first trade
        assert active_challenge.daily_min_equity == Decimal('10200')  # Low after second trade


class TestMidnightBoundary:
    """Test UTC midnight boundary for daily resets."""

    def test_midnight_reset_occurs_at_utc_midnight(self, active_challenge):
        """WHEN trade executed exactly at UTC midnight
        THEN daily reset occurs for the new day
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Trade at exactly 2024-01-01 23:59:59 (last second of day 1)
        last_second_day1 = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="day1_final",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=last_second_day1
        )
        engine.handle_trade_executed(trade1, session)

        # Trade at 2024-01-02 00:00:00 (first second of day 2)
        first_second_day2 = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="day2_first",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('50'),
            executed_at=first_second_day2
        )
        engine.handle_trade_executed(trade2, session)

        # Verify day 2 reset occurred
        assert active_challenge.current_date == datetime(2024, 1, 2).date()
        assert active_challenge.daily_start_equity == Decimal('10100')  # Day 1 close
        assert active_challenge.daily_max_equity == Decimal('10150')   # Day 2 high
        assert active_challenge.daily_min_equity == Decimal('10150')   # Day 2 low

    def test_midnight_boundary_precision(self, active_challenge):
        """WHEN trades executed across midnight boundary
        THEN date detection is precise to the second
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Just before midnight
        before_midnight = datetime(2024, 1, 1, 23, 59, 59, 999999, tzinfo=timezone.utc)
        trade_before = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="before_midnight",
            symbol="EURUSD",
            side="BUY",
            quantity="1000",
            price="1.0850",
            realized_pnl=Decimal('10'),
            executed_at=before_midnight
        )
        engine.handle_trade_executed(trade_before, session)

        # Just after midnight (next microsecond)
        after_midnight = datetime(2024, 1, 2, 0, 0, 0, 1, tzinfo=timezone.utc)
        trade_after = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="after_midnight",
            symbol="EURUSD",
            side="BUY",
            quantity="1000",
            price="1.0850",
            realized_pnl=Decimal('5'),
            executed_at=after_midnight
        )
        engine.handle_trade_executed(trade_after, session)

        # Should trigger daily reset
        assert active_challenge.current_date == datetime(2024, 1, 2).date()
        assert active_challenge.daily_start_equity == Decimal('10010')  # After before-midnight trade