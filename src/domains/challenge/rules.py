"""
Challenge Rules Engine - Pure Business Logic

Evaluates prop firm trading rules deterministically.
No database access, no side effects, no external dependencies.

Rules evaluated in strict priority order:
1. Max Daily Drawdown (highest priority - immediate failure)
2. Max Total Drawdown (failure)
3. Profit Target (success)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class RuleEvaluationResult:
    """
    Result of rule evaluation.

    Contains the new status and reason for the decision.
    """
    new_status: str  # PENDING, ACTIVE, FAILED, FUNDED
    reason: Optional[str] = None  # Specific rule that triggered the change


class ChallengeRulesEngine:
    """
    Pure business logic for evaluating challenge rules.

    All methods are deterministic and have no side effects.
    Input: Current challenge state
    Output: Rule evaluation result
    """

    # Rule constants (business requirements)
    MAX_DAILY_DRAWDOWN = Decimal('0.05')    # 5% maximum daily loss
    MAX_TOTAL_DRAWDOWN = Decimal('0.10')    # 10% maximum total loss from peak
    PROFIT_TARGET = Decimal('0.10')         # 10% profit target

    @staticmethod
    def evaluate_rules(
        current_status: str,
        current_equity: Decimal,
        max_equity_ever: Decimal,
        daily_start_equity: Decimal,
        initial_balance: Decimal,
        max_daily_drawdown_percent: Decimal,
        max_total_drawdown_percent: Decimal,
        profit_target_percent: Decimal,
    ) -> RuleEvaluationResult:
        """
        Evaluate all challenge rules against current state.

        Rules are evaluated in strict priority order for deterministic results.

        Args:
            current_status: Current challenge status
            current_equity: Current account equity
            max_equity_ever: All-time maximum equity (peak)
            daily_start_equity: Equity at start of current trading day
            initial_balance: Original challenge balance
            max_daily_drawdown_percent: Maximum allowed daily drawdown percentage
            max_total_drawdown_percent: Maximum allowed total drawdown percentage
            profit_target_percent: Required profit percentage

        Returns:
            RuleEvaluationResult with new status and reason
        """
        # Only evaluate rules for ACTIVE challenges
        if current_status != "ACTIVE":
            return RuleEvaluationResult(new_status=current_status)

        # Rule 1: Max Daily Drawdown (FAILURE - highest priority)
        daily_drawdown_result = ChallengeRulesEngine._evaluate_daily_drawdown_rule(
            current_equity, daily_start_equity, max_daily_drawdown_percent
        )
        if daily_drawdown_result.new_status == "FAILED":
            return daily_drawdown_result

        # Rule 2: Max Total Drawdown (FAILURE)
        total_drawdown_result = ChallengeRulesEngine._evaluate_total_drawdown_rule(
            current_equity, max_equity_ever, max_total_drawdown_percent
        )
        if total_drawdown_result.new_status == "FAILED":
            return total_drawdown_result

        # Rule 3: Profit Target (SUCCESS)
        profit_target_result = ChallengeRulesEngine._evaluate_profit_target_rule(
            current_equity, initial_balance, profit_target_percent
        )
        if profit_target_result.new_status == "FUNDED":
            return profit_target_result

        # No rules triggered - remain ACTIVE
        return RuleEvaluationResult(new_status="ACTIVE")

    @staticmethod
    def _evaluate_daily_drawdown_rule(
        current_equity: Decimal,
        daily_start_equity: Decimal,
        max_daily_drawdown_percent: Decimal,
    ) -> RuleEvaluationResult:
        """
        Evaluate daily drawdown rule.

        Formula: Daily Drawdown % = (Daily Start Equity - Current Equity) / Daily Start Equity
        Trigger: Daily Drawdown % > Max Daily Drawdown %

        Financial Meaning:
        - Prevents traders from losing more than X% of their starting capital in a single day
        - Protects against catastrophic single-day losses
        - Resets daily at UTC midnight
        """
        if daily_start_equity <= 0:
            return RuleEvaluationResult(new_status="ACTIVE")

        # Calculate daily drawdown percentage
        daily_loss = daily_start_equity - current_equity
        if daily_loss <= 0:
            # No drawdown - equity is at or above daily start
            return RuleEvaluationResult(new_status="ACTIVE")

        daily_drawdown_percent = (daily_loss / daily_start_equity)

        # Check if rule is violated
        if daily_drawdown_percent > max_daily_drawdown_percent:
            return RuleEvaluationResult(
                new_status="FAILED",
                reason="MAX_DAILY_DRAWDOWN"
            )

        return RuleEvaluationResult(new_status="ACTIVE")

    @staticmethod
    def _evaluate_total_drawdown_rule(
        current_equity: Decimal,
        max_equity_ever: Decimal,
        max_total_drawdown_percent: Decimal,
    ) -> RuleEvaluationResult:
        """
        Evaluate total drawdown rule.

        Formula: Total Drawdown % = (Max Equity Ever - Current Equity) / Max Equity Ever
        Trigger: Total Drawdown % > Max Total Drawdown %

        Financial Meaning:
        - Prevents traders from losing more than X% from their all-time peak equity
        - Accounts for profitable periods followed by losses
        - Never resets - permanent protection against total loss
        """
        if max_equity_ever <= 0:
            return RuleEvaluationResult(new_status="ACTIVE")

        # Calculate total drawdown percentage
        total_loss = max_equity_ever - current_equity
        if total_loss <= 0:
            # No drawdown - equity is at all-time high
            return RuleEvaluationResult(new_status="ACTIVE")

        total_drawdown_percent = (total_loss / max_equity_ever)

        # Check if rule is violated
        if total_drawdown_percent > max_total_drawdown_percent:
            return RuleEvaluationResult(
                new_status="FAILED",
                reason="MAX_TOTAL_DRAWDOWN"
            )

        return RuleEvaluationResult(new_status="ACTIVE")

    @staticmethod
    def _evaluate_profit_target_rule(
        current_equity: Decimal,
        initial_balance: Decimal,
        profit_target_percent: Decimal,
    ) -> RuleEvaluationResult:
        """
        Evaluate profit target rule.

        Formula: Profit % = (Current Equity - Initial Balance) / Initial Balance
        Trigger: Profit % >= Profit Target %

        Financial Meaning:
        - Requires traders to achieve X% profit before being funded
        - Calculated from original starting balance
        - Once achieved, trader is eligible for live trading account
        """
        if initial_balance <= 0:
            return RuleEvaluationResult(new_status="ACTIVE")

        # Calculate profit percentage
        profit = current_equity - initial_balance
        if profit <= 0:
            # No profit achieved yet
            return RuleEvaluationResult(new_status="ACTIVE")

        profit_percent = (profit / initial_balance)

        # Check if target is achieved
        if profit_percent >= profit_target_percent:
            return RuleEvaluationResult(
                new_status="FUNDED",
                reason="PROFIT_TARGET"
            )

        return RuleEvaluationResult(new_status="ACTIVE")

    @staticmethod
    def calculate_daily_drawdown_percentage(
        current_equity: Decimal,
        daily_start_equity: Decimal,
    ) -> Decimal:
        """
        Calculate current daily drawdown percentage.

        Used for monitoring and reporting.
        """
        if daily_start_equity <= 0:
            return Decimal('0')

        daily_loss = daily_start_equity - current_equity
        if daily_loss <= 0:
            return Decimal('0')

        return (daily_loss / daily_start_equity)

    @staticmethod
    def calculate_total_drawdown_percentage(
        current_equity: Decimal,
        max_equity_ever: Decimal,
    ) -> Decimal:
        """
        Calculate current total drawdown percentage.

        Used for monitoring and reporting.
        """
        if max_equity_ever <= 0:
            return Decimal('0')

        total_loss = max_equity_ever - current_equity
        if total_loss <= 0:
            return Decimal('0')

        return (total_loss / max_equity_ever)

    @staticmethod
    def calculate_profit_percentage(
        current_equity: Decimal,
        initial_balance: Decimal,
    ) -> Decimal:
        """
        Calculate current profit percentage.

        Used for monitoring and reporting.
        """
        if initial_balance <= 0:
            return Decimal('0')

        profit = current_equity - initial_balance
        if profit <= 0:
            return Decimal('0')

        return (profit / initial_balance)