"""
Unit tests for Challenge Rules Engine.

Tests pure business logic for prop firm rule evaluation.
No database, no engine, no external dependencies.

These tests protect financial invariants by ensuring rules are applied correctly.
"""

import pytest
from decimal import Decimal

from src.domains.challenge.rules import ChallengeRulesEngine


class TestProfitTargetRule:
    """Test profit target rule evaluation."""

    def test_profit_target_reached_returns_funded(self):
        """WHEN equity reaches exactly 10% profit target
        THEN rule evaluation returns FUNDED status with PROFIT_TARGET reason
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('11000'),  # 10% profit on $10K
            max_equity_ever=Decimal('11000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FUNDED"
        assert result.reason == "PROFIT_TARGET"

    def test_profit_target_exceeded_returns_funded(self):
        """WHEN equity exceeds 10% profit target
        THEN rule evaluation returns FUNDED status
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('11500'),  # 15% profit
            max_equity_ever=Decimal('11500'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FUNDED"
        assert result.reason == "PROFIT_TARGET"

    def test_profit_below_target_returns_active(self):
        """WHEN equity is below profit target
        THEN rule evaluation returns ACTIVE status
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('10900'),  # 9% profit - below target
            max_equity_ever=Decimal('10900'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "ACTIVE"
        assert result.reason is None


class TestDailyDrawdownRule:
    """Test daily drawdown rule evaluation."""

    def test_daily_drawdown_exceeded_returns_failed(self):
        """WHEN daily loss exceeds 5% limit
        THEN rule evaluation returns FAILED status with MAX_DAILY_DRAWDOWN reason
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9500'),  # 5% loss from daily start
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),  # Started day at $10K
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FAILED"
        assert result.reason == "MAX_DAILY_DRAWDOWN"

    def test_daily_drawdown_at_limit_returns_failed(self):
        """WHEN daily loss equals exactly 5% limit
        THEN rule evaluation returns FAILED status (strict inequality)
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9500'),  # Exactly 5% loss
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FAILED"
        assert result.reason == "MAX_DAILY_DRAWDOWN"

    def test_daily_drawdown_within_limit_returns_active(self):
        """WHEN daily loss is within 5% limit
        THEN rule evaluation returns ACTIVE status
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9600'),  # 4% loss - within limit
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "ACTIVE"
        assert result.reason is None


class TestTotalDrawdownRule:
    """Test total drawdown rule evaluation."""

    def test_total_drawdown_exceeded_returns_failed(self):
        """WHEN total drawdown from peak exceeds 10% limit
        THEN rule evaluation returns FAILED status with MAX_TOTAL_DRAWDOWN reason
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('8900'),  # 11% loss from $10K peak
            max_equity_ever=Decimal('10000'),  # Peak was $10K
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FAILED"
        assert result.reason == "MAX_TOTAL_DRAWDOWN"

    def test_total_drawdown_at_limit_returns_failed(self):
        """WHEN total drawdown equals exactly 10% limit
        THEN rule evaluation returns FAILED status (strict inequality)
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9000'),  # Exactly 10% loss from peak
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "FAILED"
        assert result.reason == "MAX_TOTAL_DRAWDOWN"

    def test_total_drawdown_within_limit_returns_active(self):
        """WHEN total drawdown is within 10% limit
        THEN rule evaluation returns ACTIVE status
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9100'),  # 9% loss from peak - within limit
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "ACTIVE"
        assert result.reason is None

    def test_total_drawdown_not_triggered_when_equity_recovers(self):
        """WHEN equity recovers and is above peak drawdown threshold
        THEN total drawdown rule is not triggered
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('9200'),  # Above 10% drawdown threshold
            max_equity_ever=Decimal('10000'),  # Peak still $10K
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "ACTIVE"
        assert result.reason is None


class TestRulePriority:
    """Test that rules are evaluated in correct priority order."""

    def test_daily_drawdown_takes_priority_over_total_drawdown(self):
        """WHEN both daily and total drawdown limits exceeded
        THEN daily drawdown failure is returned (higher priority)
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('8500'),  # Both 15% daily and 15% total drawdown
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        # Daily drawdown (15% > 5%) takes priority over total drawdown (15% > 10%)
        assert result.new_status == "FAILED"
        assert result.reason == "MAX_DAILY_DRAWDOWN"

    def test_total_drawdown_takes_priority_over_profit_target(self):
        """WHEN total drawdown exceeded but profit target also reached
        THEN total drawdown failure takes priority over profit success
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('11000'),  # 10% profit from initial
            max_equity_ever=Decimal('13000'),  # But peak was $13K, so 15.4% drawdown
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        # Total drawdown (15.4% > 10%) takes priority over profit target
        assert result.new_status == "FAILED"
        assert result.reason == "MAX_TOTAL_DRAWDOWN"


class TestNoRuleViolations:
    """Test scenarios where no rules are violated."""

    def test_no_violations_returns_active(self):
        """WHEN no drawdown limits exceeded and profit target not reached
        THEN rule evaluation returns ACTIVE status
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="ACTIVE",
            current_equity=Decimal('10500'),  # 5% profit - below target
            max_equity_ever=Decimal('10500'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "ACTIVE"
        assert result.reason is None

    def test_pending_status_not_evaluated(self):
        """WHEN challenge status is not ACTIVE
        THEN rules are not evaluated and status unchanged
        """
        result = ChallengeRulesEngine.evaluate_rules(
            current_status="PENDING",  # Not ACTIVE
            current_equity=Decimal('5000'),  # Would violate rules if ACTIVE
            max_equity_ever=Decimal('10000'),
            daily_start_equity=Decimal('10000'),
            initial_balance=Decimal('10000'),
            max_daily_drawdown_percent=Decimal('5'),
            max_total_drawdown_percent=Decimal('10'),
            profit_target_percent=Decimal('10'),
        )

        assert result.new_status == "PENDING"  # Unchanged
        assert result.reason is None