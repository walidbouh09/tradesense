"""
Unit tests for illegal Challenge Engine operations.

Tests that invalid operations are rejected with clear, business-readable error messages.
No silent failures - all invalid operations raise explicit exceptions.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.domains.challenge.engine import ChallengeEngine, TradeExecutedEvent


class TestFailedChallengeRejection:
    """Test that trades are rejected when challenge status is FAILED."""

    def test_trade_rejected_on_failed_challenge(self, failed_challenge):
        """WHEN attempting to trade on FAILED challenge
        THEN ValueError is raised with clear business message
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=failed_challenge.id,
            trade_id="rejected_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError) as exc_info:
            engine.handle_trade_executed(trade_event, session)

        # Verify exact error message
        assert "already FAILED" in str(exc_info.value)
        assert str(failed_challenge.id) in str(exc_info.value)

        # Verify challenge state unchanged
        assert failed_challenge.status == "FAILED"
        assert failed_challenge.current_equity == Decimal('9400')  # Unchanged

        # Verify no events emitted
        event_bus.emit.assert_not_called()

    def test_error_message_includes_challenge_id(self, failed_challenge):
        """WHEN trade rejected on failed challenge
        THEN error message includes the specific challenge ID
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=failed_challenge.id,
            trade_id="rejected_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="1000",
            price="1.0850",
            realized_pnl=Decimal('50'),
            executed_at=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError) as exc_info:
            engine.handle_trade_executed(trade_event, session)

        error_message = str(exc_info.value)
        assert str(failed_challenge.id) in error_message
        assert "FAILED" in error_message

    def test_multiple_trade_attempts_all_rejected(self, failed_challenge):
        """WHEN multiple trades attempted on failed challenge
        THEN all are rejected consistently
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        # First rejected trade
        trade1 = TradeExecutedEvent(
            challenge_id=failed_challenge.id,
            trade_id="trade_001",
            symbol="EURUSD",
            side="BUY",
            quantity="1000",
            price="1.0850",
            realized_pnl=Decimal('10'),
            executed_at=datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError, match="already FAILED"):
            engine.handle_trade_executed(trade1, session)

        # Second rejected trade
        trade2 = TradeExecutedEvent(
            challenge_id=failed_challenge.id,
            trade_id="trade_002",
            symbol="GBPUSD",
            side="SELL",
            quantity="2000",
            price="1.2650",
            realized_pnl=Decimal('-20'),
            executed_at=datetime(2024, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError, match="already FAILED"):
            engine.handle_trade_executed(trade2, session)

        # Challenge state unchanged
        assert failed_challenge.status == "FAILED"
        assert failed_challenge.total_trades == 5  # Unchanged from fixture
        assert event_bus.emit.call_count == 0  # No events


class TestFundedChallengeRejection:
    """Test that trades are rejected when challenge status is FUNDED."""

    def test_trade_rejected_on_funded_challenge(self, funded_challenge):
        """WHEN attempting to trade on FUNDED challenge
        THEN ValueError is raised with clear business message
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=funded_challenge.id,
            trade_id="rejected_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError) as exc_info:
            engine.handle_trade_executed(trade_event, session)

        # Verify exact error message
        assert "already FUNDED" in str(exc_info.value)
        assert str(funded_challenge.id) in str(exc_info.value)

        # Verify challenge state unchanged
        assert funded_challenge.status == "FUNDED"
        assert funded_challenge.current_equity == Decimal('11000')  # Unchanged

        # Verify no events emitted
        event_bus.emit.assert_not_called()

    def test_funded_challenge_preserves_final_state(self, funded_challenge):
        """WHEN trade attempted on funded challenge
        THEN all final state fields remain unchanged
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        original_equity = funded_challenge.current_equity
        original_trades = funded_challenge.total_trades
        original_funded_at = funded_challenge.funded_at
        original_ended_at = funded_challenge.ended_at

        trade_event = TradeExecutedEvent(
            challenge_id=funded_challenge.id,
            trade_id="attempted_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="5000",
            price="1.0850",
            realized_pnl=Decimal('50'),
            executed_at=datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError):
            engine.handle_trade_executed(trade_event, session)

        # All final state preserved
        assert funded_challenge.current_equity == original_equity
        assert funded_challenge.total_trades == original_trades
        assert funded_challenge.funded_at == original_funded_at
        assert funded_challenge.ended_at == original_ended_at
        assert funded_challenge.last_trade_at != trade_event.executed_at  # Not updated


class TestPendingChallengeHandling:
    """Test that PENDING challenges are handled correctly."""

    def test_pending_challenge_accepts_first_trade(self, active_challenge):
        """WHEN first trade on PENDING challenge
        THEN challenge transitions to ACTIVE (handled in validation)
        """
        # Set challenge to PENDING state
        active_challenge.status = "PENDING"
        active_challenge.started_at = None

        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=active_challenge.id,
            trade_id="first_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=datetime(2024, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
        )

        engine.handle_trade_executed(trade_event, session)

        # Challenge should now be ACTIVE
        assert active_challenge.status == "ACTIVE"
        assert active_challenge.started_at == trade_event.executed_at
        assert active_challenge.current_equity == Decimal('10100')


class TestErrorMessageClarity:
    """Test that error messages are business-readable and actionable."""

    def test_failed_challenge_error_message_business_readable(self, failed_challenge):
        """WHEN trade rejected on failed challenge
        THEN error message is clear for business users
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=failed_challenge.id,
            trade_id="business_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=datetime(2024, 1, 1, 16, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError) as exc_info:
            engine.handle_trade_executed(trade_event, session)

        error_msg = str(exc_info.value)

        # Message should be business-readable
        assert "already FAILED" in error_msg
        assert "Trade rejected" in error_msg  # Clear action implication
        assert str(failed_challenge.id) in error_msg  # Identifies specific challenge

        # Should not contain technical jargon
        assert "terminal" not in error_msg.lower()
        assert "state" not in error_msg.lower()

    def test_funded_challenge_error_message_clear(self, funded_challenge):
        """WHEN trade rejected on funded challenge
        THEN error message clearly indicates successful completion
        """
        event_bus = Mock()
        engine = ChallengeEngine(event_bus)
        session = Mock()

        trade_event = TradeExecutedEvent(
            challenge_id=funded_challenge.id,
            trade_id="after_success_trade",
            symbol="EURUSD",
            side="BUY",
            quantity="10000",
            price="1.0850",
            realized_pnl=Decimal('100'),
            executed_at=datetime(2024, 1, 3, 14, 0, 0, tzinfo=timezone.utc)
        )

        with pytest.raises(ValueError) as exc_info:
            engine.handle_trade_executed(trade_event, session)

        error_msg = str(exc_info.value)

        # Clear business meaning
        assert "already FUNDED" in error_msg
        assert "Trade rejected" in error_msg
        assert str(funded_challenge.id) in error_msg