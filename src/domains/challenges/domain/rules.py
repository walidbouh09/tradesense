"""
Risk Rule Evaluation Logic

Extracted from Challenge aggregate for:
- Deterministic evaluation
- Explainable results
- No side effects
- Testability in isolation
"""

from typing import Dict, Any
from decimal import Decimal

from .enums import ChallengeStatus
from .value_objects import Money, Percentage


class RiskEvaluationResult:
    """
    Result of risk rule evaluation.

    Contains:
    - New status if rules triggered
    - Which rule triggered the change
    - Computed metrics for explanation
    """

    def __init__(
        self,
        status: ChallengeStatus,
        rule_triggered: str = None,
        computed_metrics: Dict[str, Any] = None,
    ):
        self.status = status
        self.rule_triggered = rule_triggered
        self.computed_metrics = computed_metrics or {}


class RiskRuleEvaluator:
    """
    Evaluates risk rules against challenge state.

    Rules evaluated in priority order:
    1. Max Daily Drawdown (highest priority)
    2. Max Total Drawdown
    3. Profit Target (success condition)
    """

    @staticmethod
    def evaluate_rules(
        current_equity: Money,
        max_equity: Money,
        daily_start_equity: Money,
        initial_balance: Money,
        max_daily_drawdown_percent: Percentage,
        max_total_drawdown_percent: Percentage,
        profit_target_percent: Percentage,
    ) -> RiskEvaluationResult:
        """
        Evaluate all risk rules against current challenge state.

        Args:
            current_equity: Current account equity
            max_equity: All-time maximum equity (peak)
            daily_start_equity: Equity at start of current trading day
            initial_balance: Original challenge balance
            max_daily_drawdown_percent: Maximum allowed daily drawdown
            max_total_drawdown_percent: Maximum allowed total drawdown
            profit_target_percent: Required profit percentage

        Returns:
            RiskEvaluationResult with status and explanation
        """
        # Rule 1: Max Daily Drawdown (FAILURE - highest priority)
        daily_drawdown_result = RiskRuleEvaluator._evaluate_daily_drawdown_rule(
            current_equity, daily_start_equity, max_daily_drawdown_percent
        )
        if daily_drawdown_result.status == ChallengeStatus.FAILED:
            return daily_drawdown_result

        # Rule 2: Max Total Drawdown (FAILURE)
        total_drawdown_result = RiskRuleEvaluator._evaluate_total_drawdown_rule(
            current_equity, max_equity, max_total_drawdown_percent
        )
        if total_drawdown_result.status == ChallengeStatus.FAILED:
            return total_drawdown_result

        # Rule 3: Profit Target (SUCCESS)
        profit_target_result = RiskRuleEvaluator._evaluate_profit_target_rule(
            current_equity, initial_balance, profit_target_percent
        )
        if profit_target_result.status == ChallengeStatus.FUNDED:
            return profit_target_result

        # No rules triggered - remain ACTIVE
        return RiskEvaluationResult(
            status=ChallengeStatus.ACTIVE,
            rule_triggered=None,
            computed_metrics={}
        )

    @staticmethod
    def _evaluate_daily_drawdown_rule(
        current_equity: Money,
        daily_start_equity: Money,
        max_daily_drawdown_percent: Percentage,
    ) -> RiskEvaluationResult:
        """
        Evaluate daily drawdown rule.

        Formula: Daily Drawdown % = (Daily Start Equity - Current Equity) / Daily Start Equity * 100
        Trigger: Daily Drawdown % > Max Daily Drawdown %
        """
        if daily_start_equity.amount == 0:
            return RiskEvaluationResult(ChallengeStatus.ACTIVE)

        daily_drawdown_amount = daily_start_equity.amount - current_equity.amount

        if daily_drawdown_amount <= 0:
            # No drawdown or profit
            daily_drawdown_percent = Percentage(Decimal('0'))
        else:
            # Calculate drawdown percentage
            daily_drawdown_percent_value = (daily_drawdown_amount / daily_start_equity.amount) * Decimal('100')
            daily_drawdown_percent = Percentage(daily_drawdown_percent_value)

        # Check if rule is violated
        if daily_drawdown_percent > max_daily_drawdown_percent:
            return RiskEvaluationResult(
                status=ChallengeStatus.FAILED,
                rule_triggered="MAX_DAILY_DRAWDOWN",
                computed_metrics={
                    "daily_drawdown_percent": daily_drawdown_percent.value,
                    "limit_percent": max_daily_drawdown_percent.value,
                    "daily_start_equity": str(daily_start_equity.amount),
                    "current_equity": str(current_equity.amount),
                    "drawdown_amount": str(daily_drawdown_amount),
                }
            )

        return RiskEvaluationResult(ChallengeStatus.ACTIVE)

    @staticmethod
    def _evaluate_total_drawdown_rule(
        current_equity: Money,
        max_equity: Money,
        max_total_drawdown_percent: Percentage,
    ) -> RiskEvaluationResult:
        """
        Evaluate total drawdown rule.

        Formula: Total Drawdown % = (Max Equity - Current Equity) / Max Equity * 100
        Trigger: Total Drawdown % > Max Total Drawdown %
        """
        if max_equity.amount == 0:
            return RiskEvaluationResult(ChallengeStatus.ACTIVE)

        total_drawdown_amount = max_equity.amount - current_equity.amount

        if total_drawdown_amount <= 0:
            # No drawdown or profit
            total_drawdown_percent = Percentage(Decimal('0'))
        else:
            # Calculate drawdown percentage
            total_drawdown_percent_value = (total_drawdown_amount / max_equity.amount) * Decimal('100')
            total_drawdown_percent = Percentage(total_drawdown_percent_value)

        # Check if rule is violated
        if total_drawdown_percent > max_total_drawdown_percent:
            return RiskEvaluationResult(
                status=ChallengeStatus.FAILED,
                rule_triggered="MAX_TOTAL_DRAWDOWN",
                computed_metrics={
                    "total_drawdown_percent": total_drawdown_percent.value,
                    "limit_percent": max_total_drawdown_percent.value,
                    "max_equity": str(max_equity.amount),
                    "current_equity": str(current_equity.amount),
                    "drawdown_amount": str(total_drawdown_amount),
                }
            )

        return RiskEvaluationResult(ChallengeStatus.ACTIVE)

    @staticmethod
    def _evaluate_profit_target_rule(
        current_equity: Money,
        initial_balance: Money,
        profit_target_percent: Percentage,
    ) -> RiskEvaluationResult:
        """
        Evaluate profit target rule.

        Formula: Profit % = (Current Equity - Initial Balance) / Initial Balance * 100
        Trigger: Profit % >= Profit Target %
        """
        if initial_balance.amount == 0:
            return RiskEvaluationResult(ChallengeStatus.ACTIVE)

        profit_amount = current_equity.amount - initial_balance.amount

        if profit_amount <= 0:
            # No profit achieved
            profit_percent = Percentage(Decimal('0'))
        else:
            # Calculate profit percentage
            profit_percent_value = (profit_amount / initial_balance.amount) * Decimal('100')
            profit_percent = Percentage(profit_percent_value)

        # Check if target is achieved
        if profit_percent >= profit_target_percent:
            return RiskEvaluationResult(
                status=ChallengeStatus.FUNDED,
                rule_triggered="PROFIT_TARGET",
                computed_metrics={
                    "profit_percent": profit_percent.value,
                    "target_percent": profit_target_percent.value,
                    "current_equity": str(current_equity.amount),
                    "initial_balance": str(initial_balance.amount),
                    "profit_amount": str(profit_amount),
                }
            )

        return RiskEvaluationResult(ChallengeStatus.ACTIVE)

    @staticmethod
    def explain_rule_violation(
        rule_triggered: str,
        computed_metrics: Dict[str, Any],
    ) -> str:
        """
        Generate human-readable explanation for rule violation.

        Used for audit trails and user notifications.
        """
        if rule_triggered == "MAX_DAILY_DRAWDOWN":
            return (
                f"Daily drawdown limit exceeded. "
                f"Account lost {computed_metrics['daily_drawdown_percent']:.2f}% of daily starting equity "
                f"(limit: {computed_metrics['limit_percent']:.2f}%). "
                f"Daily starting equity: ${computed_metrics['daily_start_equity']}, "
                f"Current equity: ${computed_metrics['current_equity']}."
            )

        elif rule_triggered == "MAX_TOTAL_DRAWDOWN":
            return (
                f"Total drawdown limit exceeded. "
                f"Account lost {computed_metrics['total_drawdown_percent']:.2f}% from peak equity "
                f"(limit: {computed_metrics['limit_percent']:.2f}%). "
                f"Peak equity: ${computed_metrics['max_equity']}, "
                f"Current equity: ${computed_metrics['current_equity']}."
            )

        elif rule_triggered == "PROFIT_TARGET":
            return (
                f"Profit target achieved. "
                f"Account gained {computed_metrics['profit_percent']:.2f}% profit "
                f"(target: {computed_metrics['target_percent']:.2f}%). "
                f"Starting balance: ${computed_metrics['initial_balance']}, "
                f"Final equity: ${computed_metrics['current_equity']}."
            )

        return f"Rule violation: {rule_triggered}"