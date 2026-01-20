"""
Unit tests for extreme financial edge cases in Challenge Engine.

Tests equity bounds, extreme PnL values, and financial edge conditions.
Business-readable test names focusing on financial invariants.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.domains.challenge.engine import ChallengeEngine, TradeExecutedEvent
from src.domains.challenge.model import Challenge, ChallengeStatus


class TestEquityFloorProtection:
    """Test that equity never goes below zero."""

    def test_equity_floored_at_zero_on_extreme_loss(self, active_challenge):
        """WHEN extreme loss would drive equity negative
        THEN equity is floored at zero instead of going negative
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        initial_equity = active_challenge.current_equity

        # Execute trade with loss larger than current equity
        extreme_loss = initial_equity + Decimal('1000')  # Loss exceeds equity by $1000

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="extreme_loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="100000",  # Large position
            price="1.0850",
            realized_pnl=-extreme_loss,  # Loss exceeds equity
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Equity should be floored at zero, not negative
        assert active_challenge.current_equity == Decimal('0')
        assert active_challenge.current_equity >= 0  # Explicit bound check

        # But challenge should still be active (zero equity is allowed)
        assert active_challenge.status == ChallengeStatus.ACTIVE

    def test_multiple_extreme_losses_maintain_floor(self, active_challenge):
        """WHEN multiple extreme losses occur
        THEN equity stays at zero after first extreme loss
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First extreme loss - floors to zero
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="loss_1",
            symbol="EURUSD",
            side="SELL",
            quantity="50000",
            price="1.0850",
            realized_pnl=Decimal('-20000'),  # Loss > equity
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade1, session)
        assert active_challenge.current_equity == Decimal('0')

        # Second extreme loss - should stay at zero
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="loss_2",
            symbol="EURUSD",
            side="SELL",
            quantity="50000",
            price="1.0850",
            realized_pnl=Decimal('-50000'),  # Even larger loss
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade2, session)

        # Should still be zero, not negative
        assert active_challenge.current_equity == Decimal('0')
        assert active_challenge.status == ChallengeStatus.ACTIVE


class TestMaxEquityEverTracking:
    """Test that max_equity_ever never decreases."""

    def test_max_equity_ever_never_decreases_on_losses(self, active_challenge):
        """WHEN losses occur after reaching peak equity
        THEN max_equity_ever maintains the all-time high
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Build up to peak
        profit_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="profit_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1000'),  # Reach $11,000
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(profit_trade, session)
        assert active_challenge.max_equity_ever == Decimal('11000')

        # Subsequent losses don't reduce the peak
        loss_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="20000",
            price="1.0850",
            realized_pnl=Decimal('-2000'),  # Drop to $9,000
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(loss_trade, session)

        # Peak remains unchanged
        assert active_challenge.max_equity_ever == Decimal('11000')
        assert active_challenge.current_equity == Decimal('9000')

    def test_max_equity_ever_updates_on_new_peaks(self, active_challenge):
        """WHEN new equity peaks are reached
        THEN max_equity_ever updates to the new high
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First peak
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="peak_1",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('500'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade1, session)
        assert active_challenge.max_equity_ever == Decimal('10500')

        # Higher peak
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="peak_2",
            symbol="EURUSD",
            side="BUY",
            quantity="15000",
            price="1.0850",
            realized_pnl=Decimal('1000'),  # New high of $11,500
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade2, session)
        assert active_challenge.max_equity_ever == Decimal('11500')

        # Lower trade doesn't reduce peak
        trade3 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="lower_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="5000",
            price="1.0850",
            realized_pnl=Decimal('-1000'),  # Drop to $10,500
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade3, session)

        # Peak still at $11,500
        assert active_challenge.max_equity_ever == Decimal('11500')
        assert active_challenge.current_equity == Decimal('10500')


class TestExtremePnlValues:
    """Test handling of extreme P&L values."""

    def test_very_large_positive_pnl_handled(self, active_challenge):
        """WHEN very large positive P&L occurs
        THEN equity updates correctly without precision loss
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        initial_equity = active_challenge.current_equity

        # Very large profit (million dollar trade)
        large_profit = Decimal('1000000')

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="million_dollar_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="100000000",  # Huge position
            price="1.0850",
            realized_pnl=large_profit,
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        expected_equity = initial_equity + large_profit
        assert active_challenge.current_equity == expected_equity
        assert active_challenge.max_equity_ever == expected_equity

    def test_very_large_negative_pnl_floored_to_zero(self, active_challenge):
        """WHEN very large negative P&L occurs
        THEN equity is floored to zero, not negative
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Loss far exceeding current equity
        extreme_loss = Decimal('1000000')  # Million dollar loss

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="extreme_loss_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="100000000",
            price="1.0850",
            realized_pnl=-extreme_loss,
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Should be floored to zero
        assert active_challenge.current_equity == Decimal('0')
        assert active_challenge.current_equity >= 0

    def test_precision_maintained_with_extreme_values(self, active_challenge):
        """WHEN extreme values used
        THEN Decimal precision is maintained (no floating point errors)
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Values with many decimal places
        precise_pnl = Decimal('12345.67890123456789')

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="precise_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=precise_pnl,
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Precision should be maintained
        expected_equity = active_challenge.initial_balance + precise_pnl
        assert active_challenge.current_equity == expected_equity
        assert active_challenge.current_equity.as_tuple().exponent <= -2  # At least 2 decimal places


class TestProfitTargetNotTriggeredAccidentally:
    """Test that profit target is not triggered by invalid conditions."""

    def test_profit_target_not_triggered_on_negative_equity(self, active_challenge):
        """WHEN equity goes negative (floored to zero)
        THEN profit target is not accidentally triggered
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First cause equity to go to zero
        extreme_loss = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="to_zero_trade",
            symbol="EURUSD",
            side="SELL",
            quantity="100000",
            price="1.0850",
            realized_pnl=Decimal('-20000'),  # Loss > equity
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(extreme_loss, session)
        assert active_challenge.current_equity == Decimal('0')

        # Profit target should not be triggered at zero
        assert active_challenge.status == ChallengeStatus.ACTIVE

        # Even if we add profit that would normally trigger target
        recovery_trade = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="recovery_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1100'),  # Would be 11% if from $10K, but from $0
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(recovery_trade, session)

        # Still active - profit target calculated from initial balance
        assert active_challenge.status == ChallengeStatus.ACTIVE
        assert active_challenge.current_equity == Decimal('1100')  # 11% of $10K = $1100

    def test_zero_initial_balance_edge_case(self, active_challenge):
        """WHEN initial balance is zero (edge case)
        THEN profit target logic handles division by zero safely
        """
        # Temporarily set initial balance to zero for testing
        original_balance = active_challenge.initial_balance
        active_challenge.initial_balance = Decimal('0')

        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # Any profit should not trigger target when initial balance is zero
        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="zero_base_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('1000'),
            executed_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Should remain active (no division by zero crash)
        assert active_challenge.status == ChallengeStatus.ACTIVE

        # Restore original balance
        active_challenge.initial_balance = original_balance


class TestDailyTrackingWithExtremeValues:
    """Test daily equity tracking with extreme P&L values."""

    def test_daily_min_tracks_extreme_losses(self, active_challenge):
        """WHEN extreme losses occur
        THEN daily_min_equity correctly tracks the lowest point
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First trade: small profit
        trade1 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="small_profit",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('200'),
            executed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade1, session)

        # Second trade: extreme loss flooring to zero
        trade2 = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="extreme_loss",
            symbol="EURUSD",
            side="SELL",
            quantity="100000",
            price="1.0850",
            realized_pnl=Decimal('-20000'),
            executed_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        )
        engine.handle_trade_executed(trade2, session)

        # Daily minimum should be zero (the lowest point reached)
        assert active_challenge.daily_min_equity == Decimal('0')
        assert active_challenge.daily_max_equity == Decimal('10200')  # From first trade
        assert active_challenge.current_equity == Decimal('0')