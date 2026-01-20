"""
Application Commands for Challenge Engine.

Commands represent user intents and contain all data needed for execution.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from shared.kernel.commands import Command

from ..domain.value_objects import Money


@dataclass
class ProcessTradeExecution(Command):
    """
    Command to process a trade execution in a challenge.

    This command is idempotent and supports optimistic locking.
    """

    challenge_id: str
    trader_id: str
    trade_id: str
    symbol: str
    side: str  # BUY/SELL
    quantity: str
    price: str
    realized_pnl: Money
    commission: Money
    executed_at: datetime
    expected_version: Optional[int] = None  # For optimistic locking

    @property
    def aggregate_id(self) -> str:
        """The challenge ID this command targets."""
        return self.challenge_id

    def __post_init__(self):
        """Validate command data."""
        if not self.challenge_id:
            raise ValueError("challenge_id is required")

        if not self.trade_id:
            raise ValueError("trade_id is required")

        if self.side not in {"BUY", "SELL"}:
            raise ValueError(f"Invalid side: {self.side}")

        # Validate timestamps are timezone-aware
        if self.executed_at.tzinfo is None:
            raise ValueError("executed_at must be timezone-aware")


@dataclass
class CreateChallenge(Command):
    """
    Command to create a new challenge.
    """

    challenge_id: str
    trader_id: str
    initial_balance_amount: Decimal
    initial_balance_currency: str
    max_daily_drawdown_percent: Decimal
    max_total_drawdown_percent: Decimal
    profit_target_percent: Decimal
    challenge_type: str

    @property
    def aggregate_id(self) -> str:
        return self.challenge_id

    def __post_init__(self):
        """Validate command data."""
        if self.initial_balance_amount <= 0:
            raise ValueError("initial_balance_amount must be positive")

        if not (0 < self.max_daily_drawdown_percent <= 100):
            raise ValueError("max_daily_drawdown_percent must be 0-100")

        if not (0 < self.max_total_drawdown_percent <= 100):
            raise ValueError("max_total_drawdown_percent must be 0-100")

        if not (0 < self.profit_target_percent <= 100):
            raise ValueError("profit_target_percent must be 0-100")