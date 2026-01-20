"""
Trading Service - Triggers Challenge Engine

Handles trade execution requests and coordinates with Challenge Engine.
Ensures transactional safety and prevents concurrent equity corruption.

Why locking is required:
1. Challenge equity updates must be serialized to prevent race conditions
2. Rule evaluation depends on consistent equity state
3. Status transitions must be atomic
4. Prevents "lost updates" in concurrent trading scenarios
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from ..challenge.engine import ChallengeEngine, TradeExecutedEvent


class TradingService:
    """
    Service for processing trade executions.

    Coordinates between trade requests and challenge evaluation.
    Ensures all operations happen within database transactions.
    """

    def __init__(self, challenge_engine: ChallengeEngine):
        """
        Initialize with challenge engine.

        Args:
            challenge_engine: The challenge engine instance
        """
        self.challenge_engine = challenge_engine

    def process_trade_execution(
        self,
        challenge_id: UUID,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        realized_pnl: Decimal,
        executed_at,  # datetime - injected by framework
        session: Session,
    ) -> None:
        """
        Process a trade execution for a challenge.

        This is the main entry point for trade processing.
        All operations happen within the provided database transaction.

        Locking Strategy:
        - Challenge is loaded with SELECT FOR UPDATE (pessimistic locking)
        - This prevents concurrent updates to the same challenge
        - Ensures rule evaluation sees consistent equity state
        - Transaction commits atomically after all updates

        Args:
            challenge_id: UUID of the challenge
            trade_id: External trade identifier
            symbol: Trading instrument symbol
            side: BUY or SELL
            quantity: Trade quantity (string for precision)
            price: Trade price (string for precision)
            realized_pnl: Profit/loss from the trade
            executed_at: When the trade occurred (UTC datetime)
            session: SQLAlchemy session for transaction

        Raises:
            ValueError: If trade cannot be processed
        """
        # Create domain event from trade data
        trade_event = TradeExecutedEvent(
            challenge_id=challenge_id,
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            realized_pnl=realized_pnl,
            executed_at=executed_at,
        )

        # Process through challenge engine
        # Challenge loading and locking happens inside the engine
        self.challenge_engine.handle_trade_executed(trade_event, session)

    def validate_trade_data(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        realized_pnl: Decimal,
    ) -> None:
        """
        Validate trade data before processing.

        Basic validation to catch obvious errors early.
        More complex validation should happen at the edge (API layer).

        Args:
            trade_id: External trade identifier
            symbol: Trading instrument symbol
            side: BUY or SELL
            quantity: Trade quantity
            price: Trade price
            realized_pnl: Profit/loss amount

        Raises:
            ValueError: If trade data is invalid
        """
        if not trade_id or not trade_id.strip():
            raise ValueError("trade_id is required")

        if not symbol or not symbol.strip():
            raise ValueError("symbol is required")

        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side}")

        try:
            qty_decimal = Decimal(quantity)
            if qty_decimal <= 0:
                raise ValueError("quantity must be positive")
        except (ValueError, TypeError):
            raise ValueError(f"quantity must be valid decimal, got {quantity}")

        try:
            price_decimal = Decimal(price)
            if price_decimal <= 0:
                raise ValueError("price must be positive")
        except (ValueError, TypeError):
            raise ValueError(f"price must be valid decimal, got {price}")

        # PnL validation (can be negative)
        if realized_pnl is None:
            raise ValueError("realized_pnl is required")

        # Additional business rules can be added here
        # e.g., maximum trade size, allowed symbols, etc.