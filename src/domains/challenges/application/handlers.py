"""
Application Handlers for Challenge Engine.

Handlers orchestrate business operations using domain objects and infrastructure.
"""

import logging
from typing import List, Optional

from shared.kernel.handlers import CommandHandler, QueryHandler
from shared.kernel.events import DomainEvent

from .commands import ProcessTradeExecution, CreateChallenge
from .queries import GetChallengeDetails, GetChallengesByTrader, GetChallengePerformanceMetrics
from .repository import ChallengeRepository
from ..domain.challenge import Challenge, ChallengeParameters
from ..domain.enums import ChallengeStatus
from ..domain.events import TradeExecuted
from ..domain.value_objects import ChallengeId, Money, Percentage
from ..domain.exceptions import ChallengeDomainException

logger = logging.getLogger(__name__)


class ProcessTradeExecutionHandler(CommandHandler[ProcessTradeExecution, None]):
    """
    Handler for processing trade executions.

    Responsibilities:
    - Load challenge aggregate
    - Validate optimistic locking
    - Execute domain logic
    - Persist state changes
    - Publish domain events (via outbox pattern)

    This handler is idempotent - multiple executions with same trade_id are safe.
    """

    def __init__(self, repository: ChallengeRepository, event_publisher):
        self.repository = repository
        self.event_publisher = event_publisher

    async def handle(self, command: ProcessTradeExecution) -> None:
        """
        Process a trade execution.

        Steps:
        1. Load challenge aggregate
        2. Check optimistic locking version
        3. Create domain event from command
        4. Execute domain logic
        5. Persist aggregate
        6. Publish domain events
        """
        logger.info(
            "Processing trade execution",
            extra={
                "challenge_id": command.challenge_id,
                "trade_id": command.trade_id,
                "trader_id": command.trader_id,
                "pnl": str(command.realized_pnl.amount),
            }
        )

        # 1. Load challenge aggregate
        challenge_id = ChallengeId(command.challenge_id)
        challenge = await self.repository.get_by_id(challenge_id)

        if challenge is None:
            logger.error(
                "Challenge not found",
                extra={"challenge_id": command.challenge_id}
            )
            raise ValueError(f"Challenge {command.challenge_id} not found")

        # 2. Optimistic locking check
        if command.expected_version is not None:
            challenge.check_version(command.expected_version)

        # 3. Create domain event from command
        trade_event = TradeExecuted(
            aggregate_id=challenge_id.value,  # Use challenge ID as aggregate ID
            trader_id=command.trader_id,
            trade_id=command.trade_id,
            symbol=command.symbol,
            side=command.side,
            quantity=command.quantity,
            price=command.price,
            realized_pnl=command.realized_pnl,
            commission=command.commission,
            executed_at=command.executed_at,
        )

        try:
            # 4. Execute domain logic
            challenge.on_trade_executed(trade_event)

            # 5. Persist aggregate
            await self.repository.save(challenge)

            # 6. Publish domain events (outbox pattern)
            await self._publish_events(challenge.domain_events)

            logger.info(
                "Trade execution processed successfully",
                extra={
                    "challenge_id": command.challenge_id,
                    "new_status": challenge.status.value,
                    "equity": str(challenge.current_equity.amount),
                    "total_trades": challenge.total_trades,
                }
            )

        except ChallengeDomainException as e:
            logger.error(
                "Domain rule violation during trade processing",
                extra={
                    "challenge_id": command.challenge_id,
                    "trade_id": command.trade_id,
                    "error": str(e),
                },
                exc_info=True
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during trade processing",
                extra={
                    "challenge_id": command.challenge_id,
                    "trade_id": command.trade_id,
                },
                exc_info=True
            )
            raise

    async def _publish_events(self, events: List[DomainEvent]) -> None:
        """Publish domain events using the configured publisher."""
        for event in events:
            await self.event_publisher.publish(event)


class CreateChallengeHandler(CommandHandler[CreateChallenge, str]):
    """
    Handler for creating new challenges.
    """

    def __init__(self, repository: ChallengeRepository):
        self.repository = repository

    async def handle(self, command: CreateChallenge) -> str:
        """
        Create a new challenge.

        Returns the challenge ID.
        """
        logger.info(
            "Creating new challenge",
            extra={
                "trader_id": command.trader_id,
                "initial_balance": str(command.initial_balance_amount),
                "challenge_type": command.challenge_type,
            }
        )

        # Check if challenge already exists
        challenge_id = ChallengeId(command.challenge_id)
        if await self.repository.exists(challenge_id):
            raise ValueError(f"Challenge {command.challenge_id} already exists")

        # Create challenge parameters
        parameters = ChallengeParameters(
            initial_balance=Money(command.initial_balance_amount, command.initial_balance_currency),
            max_daily_drawdown_percent=Percentage(command.max_daily_drawdown_percent),
            max_total_drawdown_percent=Percentage(command.max_total_drawdown_percent),
            profit_target_percent=Percentage(command.profit_target_percent),
            challenge_type=command.challenge_type,
        )

        # Create challenge aggregate
        challenge = Challenge(
            challenge_id=challenge_id,
            trader_id=command.trader_id,
            parameters=parameters,
            created_at=command.metadata.occurred_at if hasattr(command, 'metadata') else None,
        )

        # Persist
        await self.repository.save(challenge)

        logger.info(
            "Challenge created successfully",
            extra={"challenge_id": command.challenge_id}
        )

        return command.challenge_id


class GetChallengeDetailsHandler(QueryHandler[GetChallengeDetails, dict]):
    """
    Handler for getting detailed challenge information.
    """

    def __init__(self, repository: ChallengeRepository):
        self.repository = repository

    async def handle(self, query: GetChallengeDetails) -> dict:
        """Get detailed challenge information."""
        challenge_id = ChallengeId(query.challenge_id)
        challenge = await self.repository.get_by_id(challenge_id)

        if challenge is None:
            return None

        return {
            "challenge_id": str(challenge.id.value),
            "trader_id": challenge.trader_id,
            "status": challenge.status.value,
            "current_equity": str(challenge.current_equity.amount),
            "max_equity": str(challenge.max_equity.amount),
            "daily_start_equity": str(challenge.daily_start_equity.amount),
            "total_trades": challenge.total_trades,
            "total_pnl": str(challenge.total_pnl.amount.amount),
            "created_at": challenge.created_at.isoformat(),
            "started_at": challenge.started_at.isoformat() if challenge.started_at else None,
            "completed_at": challenge.completed_at.isoformat() if challenge.completed_at else None,
            "last_trade_at": challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
            "parameters": {
                "initial_balance": str(challenge.parameters.initial_balance.amount),
                "max_daily_drawdown_percent": str(challenge.parameters.max_daily_drawdown_percent.value),
                "max_total_drawdown_percent": str(challenge.parameters.max_total_drawdown_percent.value),
                "profit_target_percent": str(challenge.parameters.profit_target_percent.value),
                "challenge_type": challenge.parameters.challenge_type,
            }
        }


class GetChallengesByTraderHandler(QueryHandler[GetChallengesByTrader, List[dict]]):
    """
    Handler for getting challenges by trader.
    """

    def __init__(self, repository: ChallengeRepository):
        self.repository = repository

    async def handle(self, query: GetChallengesByTrader) -> List[dict]:
        """Get challenges for a trader."""
        challenges = await self.repository.get_challenges_by_trader(
            trader_id=query.trader_id,
            status_filter=query.status_filter,
            limit=query.limit,
            offset=query.offset,
        )

        return [
            {
                "challenge_id": str(c.id.value),
                "status": c.status.value,
                "current_equity": str(c.current_equity.amount),
                "total_trades": c.total_trades,
                "created_at": c.created_at.isoformat(),
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            }
            for c in challenges
        ]


class GetChallengePerformanceMetricsHandler(QueryHandler[GetChallengePerformanceMetrics, dict]):
    """
    Handler for getting challenge performance metrics.
    """

    def __init__(self, repository: ChallengeRepository):
        self.repository = repository

    async def handle(self, query: GetChallengePerformanceMetrics) -> dict:
        """Get performance metrics for a challenge."""
        challenge_id = ChallengeId(query.challenge_id)
        challenge = await self.repository.get_by_id(challenge_id)

        if challenge is None:
            return None

        return {
            "challenge_id": str(challenge.id.value),
            "total_return_percent": str(challenge.get_profit_percentage().value),
            "max_drawdown_percent": str(challenge.get_total_drawdown_percentage().value),
            "daily_drawdown_percent": str(challenge.get_daily_drawdown_percentage().value),
            "total_trades": challenge.total_trades,
            "win_rate": "0.00",  # Would need trade-level data for this
            "sharpe_ratio": "0.00",  # Would need time-series data
            "status": challenge.status.value,
        }