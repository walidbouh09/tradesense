"""Analytics application query handlers."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from ...shared.infrastructure.logging.audit_logger import AuditLogger

from ..domain.read_models import TraderPerformance, ChallengeAnalytics, LeaderboardEntry
from ..domain.ranking_algorithm import RankingAlgorithm, RankingMetric, RankingPeriod
from ..infrastructure.cache_service import AnalyticsCacheService
from .queries import (
    GetLeaderboardQuery,
    GetTraderPerformanceQuery,
    GetChallengeAnalyticsQuery,
    GetTopPerformersQuery,
    SearchTradersQuery,
    GetAnalyticsMetadataQuery,
    GetTraderComparisonQuery,
    GetChallengeTypeStatsQuery,
)


class GetLeaderboardHandler:
    """Handler for leaderboard queries."""

    def __init__(
        self,
        repository: 'AnalyticsRepository',
        cache_service: AnalyticsCacheService,
        ranking_algorithm: RankingAlgorithm,
        audit_logger: AuditLogger,
    ):
        self.repository = repository
        self.cache = cache_service
        self.ranking = ranking_algorithm
        self.audit_logger = audit_logger

    async def handle(self, query: GetLeaderboardQuery) -> Dict[str, Any]:
        """Handle leaderboard query with caching."""
        # Try cache first
        cache_key = f"leaderboard:{query.metric_type}:{query.period}:{query.challenge_type or 'all'}:{query.limit}:{query.offset}"
        cached_result = await self.cache.get_query_result(cache_key)

        if cached_result:
            self.audit_logger.log_business_event(
                event_type="leaderboard_cache_hit",
                details={"query": cache_key},
            )
            return {"entries": cached_result, "cached": True, "cache_timestamp": datetime.utcnow()}

        # Cache miss - compute rankings
        self.audit_logger.log_business_event(
            event_type="leaderboard_cache_miss",
            details={"query": cache_key},
        )

        # Get all trader performances
        all_traders = await self.repository.get_all_trader_performances(limit=1000)

        # Calculate rankings
        try:
            metric = RankingMetric(query.metric_type)
            period = RankingPeriod(query.period)
        except ValueError:
            raise ValueError(f"Invalid metric '{query.metric_type}' or period '{query.period}'")

        rankings = self.ranking.calculate_rankings(
            traders=all_traders,
            metric=metric,
            period=period,
            challenge_type=query.challenge_type,
        )

        # Apply pagination
        paginated_rankings = rankings[query.offset:query.offset + query.limit]

        # Convert to response format
        result = []
        for ranking in paginated_rankings:
            result.append({
                "rank": ranking["rank"],
                "trader_id": ranking["trader_id"],
                "username": ranking["username"],
                "score": float(ranking["score"]),
                "raw_value": float(ranking["raw_value"]),
                "metric_type": ranking["metric_type"],
                "period": ranking["period"],
                "challenge_type": ranking["challenge_type"],
                "rank_change": ranking["rank_change"],
                "total_challenges": ranking["total_challenges"],
                "pass_rate": ranking["pass_rate"],
                "trading_days": ranking["trading_days"],
                "last_updated": ranking["last_updated"].isoformat(),
            })

        # Cache result
        await self.cache.store_query_result(cache_key, result)

        return {
            "entries": result,
            "total_count": len(rankings),
            "cached": False,
            "cache_timestamp": None,
        }


class GetTraderPerformanceHandler:
    """Handler for trader performance queries."""

    def __init__(
        self,
        repository: 'AnalyticsRepository',
        cache_service: AnalyticsCacheService,
        audit_logger: AuditLogger,
    ):
        self.repository = repository
        self.cache = cache_service
        self.audit_logger = audit_logger

    async def handle(self, query: GetTraderPerformanceQuery) -> Optional[Dict[str, Any]]:
        """Handle trader performance query."""
        # Try cache first
        cached_data = await self.cache.get_trader_performance(query.trader_id)
        if cached_data:
            return {**cached_data, "cached": True}

        # Cache miss - get from repository
        performance = await self.repository.get_trader_performance(query.trader_id)
        if not performance:
            return None

        # Convert to dict for response
        result = {
            "trader_id": performance.trader_id,
            "username": performance.username,
            "registration_date": performance.registration_date.isoformat(),
            "last_active": performance.last_active.isoformat(),
            "total_challenges": performance.total_challenges,
            "active_challenges": performance.active_challenges,
            "passed_challenges": performance.passed_challenges,
            "failed_challenges": performance.failed_challenges,
            "total_profit": float(performance.total_profit),
            "total_loss": float(performance.total_loss),
            "net_pnl": float(performance.net_pnl),
            "largest_win": float(performance.largest_win),
            "largest_loss": float(performance.largest_loss),
            "total_trades": performance.total_trades,
            "winning_trades": performance.winning_trades,
            "losing_trades": performance.losing_trades,
            "win_rate": float(performance.win_rate),
            "best_drawdown": float(performance.best_drawdown),
            "worst_drawdown": float(performance.worst_drawdown),
            "average_drawdown": float(performance.average_drawdown),
            "trading_days": performance.trading_days,
            "average_daily_pnl": float(performance.average_daily_pnl),
            "consistency_score": float(performance.consistency_score),
            "overall_rank": performance.overall_rank,
            "monthly_rank": performance.monthly_rank,
            "pass_rate": float(performance.pass_rate),
            "profit_factor": float(performance.profit_factor),
            "expectancy": float(performance.expectancy),
            "favorite_instruments": performance.favorite_instruments,
            "preferred_timeframes": performance.preferred_timeframes,
            "risk_profile": performance.risk_profile,
            "last_updated": performance.last_updated.isoformat() if performance.last_updated else None,
            "cached": False,
        }

        # Cache result
        await self.cache.store_trader_performance(query.trader_id, result)

        return result


class GetTopPerformersHandler:
    """Handler for top performers queries."""

    def __init__(
        self,
        repository: 'AnalyticsRepository',
        cache_service: AnalyticsCacheService,
        ranking_algorithm: RankingAlgorithm,
        audit_logger: AuditLogger,
    ):
        self.repository = repository
        self.cache = cache_service
        self.ranking = ranking_algorithm
        self.audit_logger = audit_logger

    async def handle(self, query: GetTopPerformersQuery) -> List[Dict[str, Any]]:
        """Handle top performers query."""
        cache_key = f"top_performers:{query.metric_type}:{query.period}:{query.challenge_type or 'all'}:{query.limit}"
        cached_result = await self.cache.get_query_result(cache_key)

        if cached_result:
            return cached_result

        # Get leaderboard and return top N
        leaderboard_query = GetLeaderboardQuery(
            metric_type=query.metric_type,
            period=query.period,
            challenge_type=query.challenge_type,
            limit=query.limit,
            offset=0,
        )

        handler = GetLeaderboardHandler(
            self.repository, self.cache, self.ranking, self.audit_logger
        )

        result = await handler.handle(leaderboard_query)

        # Cache result
        await self.cache.store_query_result(cache_key, result["entries"])

        return result["entries"]


class SearchTradersHandler:
    """Handler for trader search queries."""

    def __init__(
        self,
        repository: 'AnalyticsRepository',
        cache_service: AnalyticsCacheService,
        audit_logger: AuditLogger,
    ):
        self.repository = repository
        self.cache = cache_service
        self.audit_logger = audit_logger

    async def handle(self, query: SearchTradersQuery) -> List[Dict[str, Any]]:
        """Handle trader search query."""
        # This would implement complex filtering logic
        # For now, get all traders and filter in memory
        all_traders = await self.repository.get_all_trader_performances(limit=10000)

        filtered_traders = []
        for trader in all_traders:
            if self._matches_criteria(trader, query):
                filtered_traders.append({
                    "trader_id": trader.trader_id,
                    "username": trader.username,
                    "pass_rate": float(trader.pass_rate),
                    "total_trades": trader.total_trades,
                    "net_pnl": float(trader.net_pnl),
                    "risk_profile": trader.risk_profile,
                    "total_challenges": trader.total_challenges,
                })

        # Apply pagination
        start_idx = query.offset
        end_idx = start_idx + query.limit
        return filtered_traders[start_idx:end_idx]

    def _matches_criteria(self, trader: TraderPerformance, query: SearchTradersQuery) -> bool:
        """Check if trader matches search criteria."""
        if query.min_pass_rate and trader.pass_rate < query.min_pass_rate:
            return False

        if query.min_trades and trader.total_trades < query.min_trades:
            return False

        if query.min_pnl and trader.net_pnl < query.min_pnl:
            return False

        if query.risk_profile and trader.risk_profile != query.risk_profile:
            return False

        return True


class GetAnalyticsMetadataHandler:
    """Handler for analytics metadata queries."""

    def __init__(
        self,
        repository: 'AnalyticsRepository',
        cache_service: AnalyticsCacheService,
        audit_logger: AuditLogger,
    ):
        self.repository = repository
        self.cache = cache_service
        self.audit_logger = audit_logger

    async def handle(self, query: GetAnalyticsMetadataQuery) -> Dict[str, Any]:
        """Handle analytics metadata query."""
        metadata = await self.cache.get_metadata()

        if not metadata:
            # Generate metadata from repository
            total_traders = await self.repository.get_trader_count()
            total_challenges = await self.repository.get_challenge_count()
            total_trades = await self.repository.get_trade_count()

            metadata = {
                "last_full_recalculation": datetime.utcnow().isoformat(),
                "total_traders": total_traders,
                "total_challenges": total_challenges,
                "total_trades": total_trades,
                "cache_hit_rate": 0.0,
                "average_calculation_time": 0.0,
            }

            # Cache it
            from ..domain.read_models import AnalyticsMetadata
            from decimal import Decimal
            metadata_obj = AnalyticsMetadata(
                last_full_recalculation=datetime.utcnow(),
                total_traders=total_traders,
                total_challenges=total_challenges,
                total_trades=total_trades,
                cache_hit_rate=Decimal('0'),
                average_calculation_time=0.0,
            )
            await self.cache.update_metadata(metadata_obj)

        return metadata


# Type hint for repository
class AnalyticsRepository:
    """Repository interface for analytics."""
    async def get_trader_performance(self, trader_id: str) -> Optional[TraderPerformance]: ...
    async def get_all_trader_performances(self, limit: int = 1000) -> List[TraderPerformance]: ...
    async def get_challenge_analytics(self, challenge_id: str) -> Optional[ChallengeAnalytics]: ...
    async def get_trader_count(self) -> int: ...
    async def get_challenge_count(self) -> int: ...
    async def get_trade_count(self) -> int: ...