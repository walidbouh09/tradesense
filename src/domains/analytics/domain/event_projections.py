"""
Event Projections for Analytics Read Models

These projectors:
- Listen to domain events from other contexts
- Update read models in eventual consistency
- Never modify business state
- Optimized for bulk updates
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from .read_models import TraderPerformance, ChallengeAnalytics, LeaderboardEntry


class TraderPerformanceProjector:
    """Projects events onto TraderPerformance read model."""

    def __init__(self, repository: 'AnalyticsRepository'):
        self.repository = repository

    async def project_challenge_started(self, event: Dict[str, Any]) -> None:
        """Project ChallengeStarted event."""
        trader_id = event.get("trader_id")
        challenge_id = event.get("aggregate_id")

        # Get or create trader performance
        performance = await self.repository.get_trader_performance(trader_id)
        if not performance:
            # Create new trader performance record
            performance = TraderPerformance(
                trader_id=trader_id,
                username=f"user_{trader_id[:8]}",  # Placeholder - would get from user service
                registration_date=datetime.utcnow(),
                last_active=datetime.utcnow(),
            )

        # Update challenge counts
        performance.total_challenges += 1
        performance.active_challenges += 1
        performance.last_active = datetime.utcnow()
        performance.last_updated = datetime.utcnow()

        await self.repository.save_trader_performance(performance)

        # Create challenge analytics record
        challenge_analytics = ChallengeAnalytics(
            challenge_id=challenge_id,
            trader_id=trader_id,
            challenge_type=event.get("challenge_type", "UNKNOWN"),
            status="ACTIVE",
            start_date=datetime.utcnow(),
            initial_balance=Decimal(str(event.get("initial_balance", 0))),
            current_balance=Decimal(str(event.get("initial_balance", 0))),
            peak_balance=Decimal(str(event.get("initial_balance", 0))),
        )

        await self.repository.save_challenge_analytics(challenge_analytics)

    async def project_challenge_passed(self, event: Dict[str, Any]) -> None:
        """Project ChallengePassed event."""
        trader_id = event.get("trader_id")
        challenge_id = event.get("aggregate_id")

        # Update trader performance
        performance = await self.repository.get_trader_performance(trader_id)
        if performance:
            performance.passed_challenges += 1
            performance.active_challenges -= 1
            performance.last_active = datetime.utcnow()
            performance.last_updated = datetime.utcnow()

            # Update financial metrics
            final_pnl = Decimal(str(event.get("total_profit", 0)))
            performance.total_profit += max(final_pnl, Decimal('0'))
            performance.total_loss += abs(min(final_pnl, Decimal('0')))
            performance.net_pnl += final_pnl
            performance.largest_win = max(performance.largest_win, final_pnl)
            performance.largest_loss = min(performance.largest_loss, final_pnl)

            await self.repository.save_trader_performance(performance)

        # Update challenge analytics
        challenge = await self.repository.get_challenge_analytics(challenge_id)
        if challenge:
            challenge.status = "PASSED"
            challenge.end_date = datetime.utcnow()
            challenge.final_pnl = Decimal(str(event.get("total_profit", 0)))
            challenge.current_balance = challenge.initial_balance + challenge.final_pnl
            challenge.last_updated = datetime.utcnow()

            await self.repository.save_challenge_analytics(challenge)

    async def project_challenge_failed(self, event: Dict[str, Any]) -> None:
        """Project ChallengeFailed event."""
        trader_id = event.get("trader_id")
        challenge_id = event.get("aggregate_id")

        # Update trader performance
        performance = await self.repository.get_trader_performance(trader_id)
        if performance:
            performance.failed_challenges += 1
            performance.active_challenges -= 1
            performance.last_active = datetime.utcnow()
            performance.last_updated = datetime.utcnow()

            await self.repository.save_trader_performance(performance)

        # Update challenge analytics
        challenge = await self.repository.get_challenge_analytics(challenge_id)
        if challenge:
            challenge.status = "FAILED"
            challenge.end_date = datetime.utcnow()
            challenge.failure_reason = event.get("failure_reason")
            challenge.failed_requirements = event.get("failed_requirements", [])
            challenge.last_updated = datetime.utcnow()

            await self.repository.save_challenge_analytics(challenge)

    async def project_trade_executed(self, event: Dict[str, Any]) -> None:
        """Project TradeExecuted event."""
        trader_id = event.get("user_id")
        challenge_id = event.get("challenge_id")  # Would need to be added to trade events

        # Update trader performance
        performance = await self.repository.get_trader_performance(trader_id)
        if performance:
            performance.total_trades += 1
            performance.last_active = datetime.utcnow()
            performance.last_updated = datetime.utcnow()

            # Update win/loss counts (would need P&L data)
            pnl = Decimal(str(event.get("realized_pnl", 0)))
            if pnl > 0:
                performance.winning_trades += 1
            elif pnl < 0:
                performance.losing_trades += 1

            # Recalculate win rate
            total_decisive_trades = performance.winning_trades + performance.losing_trades
            if total_decisive_trades > 0:
                performance.win_rate = Decimal(str(performance.winning_trades)) / Decimal(str(total_decisive_trades))

            await self.repository.save_trader_performance(performance)

        # Update challenge analytics if challenge_id provided
        if challenge_id:
            challenge = await self.repository.get_challenge_analytics(challenge_id)
            if challenge:
                challenge.total_trades += 1
                challenge.last_updated = datetime.utcnow()
                await self.repository.save_challenge_analytics(challenge)

    async def project_daily_pnl_calculated(self, event: Dict[str, Any]) -> None:
        """Project DailyPnLCalculated event."""
        trader_id = event.get("user_id")
        daily_pnl = Decimal(str(event.get("daily_pnl", 0)))
        trading_days = event.get("trading_days", 0)

        performance = await self.repository.get_trader_performance(trader_id)
        if performance:
            performance.trading_days = max(performance.trading_days, trading_days)
            performance.last_active = datetime.utcnow()
            performance.last_updated = datetime.utcnow()

            # Recalculate average daily P&L
            if performance.trading_days > 0:
                # This is simplified - would need historical data
                performance.average_daily_pnl = performance.net_pnl / Decimal(str(performance.trading_days))

            await self.repository.save_trader_performance(performance)


class ChallengeAnalyticsProjector:
    """Projects events onto ChallengeAnalytics read model."""

    def __init__(self, repository: 'AnalyticsRepository'):
        self.repository = repository

    async def project_trading_metrics_updated(self, event: Dict[str, Any]) -> None:
        """Project TradingMetricsUpdated event."""
        challenge_id = event.get("challenge_id")  # Would need to be added to events

        if not challenge_id:
            return

        challenge = await self.repository.get_challenge_analytics(challenge_id)
        if not challenge:
            return

        # Update challenge metrics
        challenge.current_balance = Decimal(str(event.get("current_balance", 0)))
        challenge.peak_balance = max(challenge.peak_balance, challenge.current_balance)

        # Update drawdown
        drawdown = challenge.peak_balance - challenge.current_balance
        challenge.max_drawdown = max(challenge.max_drawdown, drawdown)
        challenge.max_drawdown_percentage = (challenge.max_drawdown / challenge.initial_balance) * Decimal('100')

        challenge.trading_days = event.get("trading_days", 0)
        challenge.last_updated = datetime.utcnow()

        await self.repository.save_challenge_analytics(challenge)

    async def project_rule_violation_detected(self, event: Dict[str, Any]) -> None:
        """Project RuleViolationDetected event."""
        challenge_id = event.get("challenge_id")  # Would need to be added to events

        if not challenge_id:
            return

        challenge = await self.repository.get_challenge_analytics(challenge_id)
        if not challenge:
            return

        # Update violation counts
        challenge.rule_violations += 1
        severity = event.get("severity", "WARNING")

        if severity == "CRITICAL":
            challenge.critical_violations += 1
        elif severity == "HIGH":
            challenge.warning_violations += 1

        challenge.last_updated = datetime.utcnow()

        await self.repository.save_challenge_analytics(challenge)


class LeaderboardProjector:
    """Projects events to update leaderboards."""

    def __init__(self, repository: 'AnalyticsRepository', cache_service: 'AnalyticsCacheService'):
        self.repository = repository
        self.cache = cache_service

    async def project_performance_updated(self, trader_id: str) -> None:
        """Recalculate leaderboards when trader performance changes."""
        # Get updated performance
        performance = await self.repository.get_trader_performance(trader_id)
        if not performance:
            return

        # Recalculate rankings for different metrics and periods
        await self._recalculate_leaderboards()

    async def _recalculate_leaderboards(self) -> None:
        """Recalculate all leaderboard rankings."""

        # Get all trader performances
        all_performances = await self.repository.get_all_trader_performances(limit=1000)

        # Calculate rankings for different metrics
        metrics = [
            ("net_pnl", lambda p: p.net_pnl),
            ("win_rate", lambda p: p.win_rate),
            ("consistency", lambda p: p.consistency_score),
            ("profit_factor", lambda p: p.profit_factor),
        ]

        for metric_name, metric_func in metrics:
            # Sort by metric (descending for most metrics)
            sorted_traders = sorted(
                all_performances,
                key=metric_func,
                reverse=True
            )

            # Update ranks
            for rank, performance in enumerate(sorted_traders, 1):
                await self._update_trader_rank(
                    performance.trader_id,
                    metric_name,
                    "all_time",
                    rank
                )

                # Create leaderboard entries for caching
                entry = LeaderboardEntry(
                    rank=rank,
                    trader_id=performance.trader_id,
                    username=performance.username,
                    metric_value=metric_func(performance),
                    metric_type=metric_name,
                    period="all_time",
                    total_challenges=performance.total_challenges,
                    pass_rate=performance.pass_rate,
                    trading_days=performance.trading_days,
                )

                await self.cache.store_leaderboard_entry(entry)

        # Update cache timestamps
        await self.cache.update_metadata()

    async def _update_trader_rank(
        self,
        trader_id: str,
        metric_type: str,
        period: str,
        rank: int
    ) -> None:
        """Update trader's rank for specific metric and period."""
        performance = await self.repository.get_trader_performance(trader_id)
        if performance:
            if not hasattr(performance, 'challenge_type_ranks'):
                performance.challenge_type_ranks = {}

            key = f"{metric_type}_{period}"
            performance.challenge_type_ranks[key] = rank
            performance.rank_last_updated = datetime.utcnow()

            await self.repository.save_trader_performance(performance)


class AnalyticsEventHandler:
    """Main event handler that routes events to appropriate projectors."""

    def __init__(
        self,
        trader_projector: TraderPerformanceProjector,
        challenge_projector: ChallengeAnalyticsProjector,
        leaderboard_projector: LeaderboardProjector,
    ):
        self.trader_projector = trader_projector
        self.challenge_projector = challenge_projector
        self.leaderboard_projector = leaderboard_projector

        # Event routing map
        self.event_handlers = {
            "ChallengeStarted": self.trader_projector.project_challenge_started,
            "ChallengePassed": [
                self.trader_projector.project_challenge_passed,
                self.leaderboard_projector.project_performance_updated,
            ],
            "ChallengeFailed": [
                self.trader_projector.project_challenge_failed,
                self.leaderboard_projector.project_performance_updated,
            ],
            "TradeExecuted": self.trader_projector.project_trade_executed,
            "DailyPnLCalculated": self.trader_projector.project_daily_pnl_calculated,
            "TradingMetricsUpdated": self.challenge_projector.project_trading_metrics_updated,
            "RuleViolationDetected": self.challenge_projector.project_rule_violation_detected,
        }

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Route event to appropriate projector(s)."""
        handler = self.event_handlers.get(event_type)
        if not handler:
            return  # No handler for this event type

        try:
            if isinstance(handler, list):
                # Multiple handlers for this event
                for h in handler:
                    if asyncio.iscoroutinefunction(h):
                        await h(event_data)
                    else:
                        # Handle method calls with trader_id extraction
                        trader_id = event_data.get("trader_id") or event_data.get("user_id")
                        if trader_id:
                            await h(trader_id)
            else:
                # Single handler
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    # Handle method calls with trader_id extraction
                    trader_id = event_data.get("trader_id") or event_data.get("user_id")
                    if trader_id:
                        await handler(trader_id)

        except Exception as e:
            # Log error but don't fail the event processing
            # Analytics failures shouldn't block business operations
            print(f"Analytics projection error for {event_type}: {e}")
            # In production: self.logger.error(...)