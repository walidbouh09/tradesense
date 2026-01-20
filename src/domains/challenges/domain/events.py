"""
Domain Events for Challenge Engine.

All events are:
- Immutable after creation
- Versioned (v1) for schema evolution
- Timestamped in UTC
- JSON-serializable
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.kernel.events import DomainEvent

from .enums import ChallengeStatus
from .value_objects import Money, PnL


class TradeExecuted(DomainEvent):
    """
    Domain event representing a trade execution.

    This is an INPUT event to the Challenge Engine.
    Schema version: v1
    """

    def __init__(
        self,
        aggregate_id: UUID,  # Challenge ID this trade belongs to
        trader_id: str,
        trade_id: str,
        symbol: str,
        side: str,  # BUY/SELL
        quantity: str,  # Decimal string for precision
        price: str,  # Decimal string for precision
        realized_pnl: PnL,
        commission: Money,
        executed_at: datetime,
        version: int = 1,
    ):
        super().__init__(aggregate_id, occurred_at=executed_at)
        self._trader_id = trader_id
        self._trade_id = trade_id
        self._symbol = symbol
        self._side = side
        self._quantity = quantity
        self._price = price
        self._realized_pnl = realized_pnl
        self._commission = commission
        self._version = version

    @property
    def trader_id(self) -> str:
        return self._trader_id

    @property
    def trade_id(self) -> str:
        return self._trade_id

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def side(self) -> str:
        return self._side

    @property
    def quantity(self) -> str:
        return self._quantity

    @property
    def price(self) -> str:
        return self._price

    @property
    def realized_pnl(self) -> PnL:
        return self._realized_pnl

    @property
    def commission(self) -> Money:
        return self._commission

    @property
    def executed_at(self) -> datetime:
        return self.occurred_at

    @property
    def version(self) -> int:
        return self._version

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "event_type": "TradeExecuted",
            "event_version": self.version,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            "trader_id": self.trader_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "realized_pnl": {
                "amount": str(self.realized_pnl.amount.amount),
                "currency": self.realized_pnl.amount.currency,
            },
            "commission": {
                "amount": str(self.commission.amount),
                "currency": self.commission.currency,
            },
        }


class ChallengeStatusChanged(DomainEvent):
    """
    Domain event emitted when challenge status changes.

    Schema version: v1
    """

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: str,
        old_status: ChallengeStatus,
        new_status: ChallengeStatus,
        changed_at: datetime,
        rule_triggered: Optional[str] = None,
        version: int = 1,
    ):
        super().__init__(aggregate_id, occurred_at=changed_at)
        self._trader_id = trader_id
        self._old_status = old_status
        self._new_status = new_status
        self._rule_triggered = rule_triggered
        self._version = version

    @property
    def trader_id(self) -> str:
        return self._trader_id

    @property
    def old_status(self) -> ChallengeStatus:
        return self._old_status

    @property
    def new_status(self) -> ChallengeStatus:
        return self._new_status

    @property
    def rule_triggered(self) -> Optional[str]:
        return self._rule_triggered

    @property
    def changed_at(self) -> datetime:
        return self.occurred_at

    @property
    def version(self) -> int:
        return self._version

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "event_type": "ChallengeStatusChanged",
            "event_version": self.version,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            "trader_id": self.trader_id,
            "old_status": self.old_status.value,
            "new_status": self.new_status.value,
            "rule_triggered": self.rule_triggered,
        }


class ChallengeFailed(DomainEvent):
    """
    Domain event emitted when challenge fails.

    This is a TERMINAL event - no further state changes possible.
    Schema version: v1
    """

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: str,
        failure_reason: str,
        final_equity: Money,
        total_trades: int,
        completed_at: datetime,
        version: int = 1,
    ):
        super().__init__(aggregate_id, occurred_at=completed_at)
        self._trader_id = trader_id
        self._failure_reason = failure_reason
        self._final_equity = final_equity
        self._total_trades = total_trades
        self._version = version

    @property
    def trader_id(self) -> str:
        return self._trader_id

    @property
    def failure_reason(self) -> str:
        return self._failure_reason

    @property
    def final_equity(self) -> Money:
        return self._final_equity

    @property
    def total_trades(self) -> int:
        return self._total_trades

    @property
    def completed_at(self) -> datetime:
        return self.occurred_at

    @property
    def version(self) -> int:
        return self._version

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "event_type": "ChallengeFailed",
            "event_version": self.version,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            "trader_id": self.trader_id,
            "failure_reason": self.failure_reason,
            "final_equity": {
                "amount": str(self.final_equity.amount),
                "currency": self.final_equity.currency,
            },
            "total_trades": self.total_trades,
        }


class ChallengeFunded(DomainEvent):
    """
    Domain event emitted when challenge succeeds and trader is funded.

    This is a TERMINAL event - challenge completed successfully.
    Schema version: v1
    """

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: str,
        final_equity: Money,
        profit_achieved: Money,
        total_trades: int,
        funded_at: datetime,
        version: int = 1,
    ):
        super().__init__(aggregate_id, occurred_at=funded_at)
        self._trader_id = trader_id
        self._final_equity = final_equity
        self._profit_achieved = profit_achieved
        self._total_trades = total_trades
        self._version = version

    @property
    def trader_id(self) -> str:
        return self._trader_id

    @property
    def final_equity(self) -> Money:
        return self._final_equity

    @property
    def profit_achieved(self) -> Money:
        return self._profit_achieved

    @property
    def total_trades(self) -> int:
        return self._total_trades

    @property
    def funded_at(self) -> datetime:
        return self.occurred_at

    @property
    def version(self) -> int:
        return self._version

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "event_type": "ChallengeFunded",
            "event_version": self.version,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            "trader_id": self.trader_id,
            "final_equity": {
                "amount": str(self.final_equity.amount),
                "currency": self.final_equity.currency,
            },
            "profit_achieved": {
                "amount": str(self.profit_achieved.amount),
                "currency": self.profit_achieved.currency,
            },
            "total_trades": self.total_trades,
        }