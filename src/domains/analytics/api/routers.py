"""Analytics API FastAPI routers."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse

from shared.infrastructure.logging.audit_logger import AuditLogger
import redis.asyncio as redis

from ..domain.ranking_algorithm import RankingAlgorithm
from ..infrastructure.cache_service import AnalyticsCacheService
from ..application.handlers import (
    GetLeaderboardHandler,
    GetTraderPerformanceHandler,
    GetTopPerformersHandler,
    SearchTradersHandler,
    GetAnalyticsMetadataHandler,
)
from ..application.queries import (
    GetLeaderboardQuery,
    GetTraderPerformanceQuery,
    GetTopPerformersQuery,
    SearchTradersQuery,
    GetAnalyticsMetadataQuery,
)
from .schemas import (
    LeaderboardResponse,
    TraderPerformanceSchema,
    TopPerformersResponse,
    SearchTradersRequest,
    SearchTradersResponse,
    AnalyticsMetadataSchema,
    ErrorResponse,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


# Rate limiting dependency (simplified)
async def check_rate_limit(request: Request) -> None:
    """Basic rate limiting check."""
    # In production, implement proper rate limiting
    # For now, just allow all requests
    pass


# Dependencies
async def get_analytics_repository():
    """Get analytics repository - placeholder."""
    # In production, inject proper repository
    class MockAnalyticsRepository:
        async def get_trader_performance(self, trader_id: str):
            return None
        async def get_all_trader_performances(self, limit: int = 1000):
            return []
        async def get_challenge_analytics(self, challenge_id: str):
            return None
        async def get_trader_count(self) -> int:
            return 0
        async def get_challenge_count(self) -> int:
            return 0
        async def get_trade_count(self) -> int:
            return 0

    return MockAnalyticsRepository()


async def get_cache_service(redis_client: redis.Redis = Depends(lambda: None)):
    """Get cache service."""
    # Placeholder - in production, inject Redis client
    return None


async def get_ranking_algorithm():
    """Get ranking algorithm."""
    return RankingAlgorithm()


async def get_audit_logger():
    """Get audit logger."""
    # Placeholder
    return None


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get Leaderboard Rankings",
    description="""
    Get trader leaderboard rankings for specified metric and period.

    **Caching**: Results are cached for 5 minutes to improve performance.

    **Rate Limiting**: 100 requests per minute per IP.

    **Metrics Available**:
    - `net_pnl`: Net profit & loss
    - `win_rate`: Trade win rate percentage
    - `profit_factor`: Gross profit / gross loss
    - `expectancy`: Average win * win rate - average loss * loss rate
    - `consistency_score`: Steady performance score
    - `pass_rate`: Challenge pass rate
    - `risk_adjusted_return`: Return per unit of risk
    - `sharpe_ratio`: Risk-adjusted returns

    **Periods Available**:
    - `all_time`: All-time rankings
    - `yearly`: Current year rankings
    - `monthly`: Current month rankings
    - `weekly`: Current week rankings
    - `daily`: Current day rankings
    """,
    responses={
        200: {"description": "Leaderboard retrieved successfully"},
        400: {"description": "Invalid parameters"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)
async def get_leaderboard(
    metric_type: str = Query(..., description="Ranking metric type"),
    period: str = Query("all_time", description="Time period for rankings"),
    challenge_type: Optional[str] = Query(None, description="Filter by challenge type"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    repository=Depends(get_analytics_repository),
    cache_service=Depends(get_cache_service),
    ranking_algorithm=Depends(get_ranking_algorithm),
    audit_logger=Depends(get_audit_logger),
    rate_limit: None = Depends(check_rate_limit),
) -> LeaderboardResponse:
    """Get leaderboard rankings."""
    try:
        handler = GetLeaderboardHandler(repository, cache_service, ranking_algorithm, audit_logger)

        query = GetLeaderboardQuery(
            metric_type=metric_type,
            period=period,
            challenge_type=challenge_type,
            limit=limit,
            offset=offset,
        )

        result = await handler.handle(query)

        return LeaderboardResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/traders/{trader_id}/performance",
    response_model=TraderPerformanceSchema,
    summary="Get Trader Performance",
    description="""
    Get detailed performance metrics for a specific trader.

    **Includes**:
    - Challenge statistics (passed/failed/active)
    - Financial metrics (P&L, win rate, profit factor)
    - Risk metrics (drawdown, expectancy)
    - Trading activity (days traded, consistency)
    - Rankings and percentiles

    **Caching**: Individual trader data cached for 1 hour.
    """,
    responses={
        200: {"description": "Trader performance retrieved"},
        404: {"description": "Trader not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def get_trader_performance(
    trader_id: str,
    repository=Depends(get_analytics_repository),
    cache_service=Depends(get_cache_service),
    audit_logger=Depends(get_audit_logger),
) -> TraderPerformanceSchema:
    """Get trader performance details."""
    handler = GetTraderPerformanceHandler(repository, cache_service, audit_logger)

    query = GetTraderPerformanceQuery(trader_id=trader_id)
    result = await handler.handle(query)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trader {trader_id} not found",
        )

    return TraderPerformanceSchema(**result)


@router.get(
    "/top-performers",
    response_model=TopPerformersResponse,
    summary="Get Top Performers",
    description="""
    Get top-performing traders for a specific metric and period.

    **Use Case**: Featured traders on homepage, hall of fame, etc.

    **Default**: Top 10 by net P&L this month.
    """,
)
async def get_top_performers(
    metric_type: str = Query("net_pnl", description="Ranking metric"),
    period: str = Query("monthly", description="Time period"),
    challenge_type: Optional[str] = Query(None, description="Challenge type filter"),
    limit: int = Query(10, ge=1, le=50, description="Number of top performers"),
    repository=Depends(get_analytics_repository),
    cache_service=Depends(get_cache_service),
    ranking_algorithm=Depends(get_ranking_algorithm),
    audit_logger=Depends(get_audit_logger),
) -> TopPerformersResponse:
    """Get top performers."""
    handler = GetTopPerformersHandler(repository, cache_service, ranking_algorithm, audit_logger)

    query = GetTopPerformersQuery(
        metric_type=metric_type,
        period=period,
        challenge_type=challenge_type,
        limit=limit,
    )

    performers = await handler.handle(query)

    return TopPerformersResponse(performers=performers)


@router.post(
    "/traders/search",
    response_model=SearchTradersResponse,
    summary="Search Traders",
    description="""
    Search for traders matching specific performance criteria.

    **Use Case**: Find traders with specific performance profiles.

    **Example**: Find traders with >80% pass rate and >1000 trades.
    """,
)
async def search_traders(
    request: SearchTradersRequest,
    repository=Depends(get_analytics_repository),
    cache_service=Depends(get_cache_service),
    audit_logger=Depends(get_audit_logger),
) -> SearchTradersResponse:
    """Search traders by performance criteria."""
    handler = SearchTradersHandler(repository, cache_service, audit_logger)

    query = SearchTradersQuery(
        min_pass_rate=request.min_pass_rate,
        min_trades=request.min_trades,
        min_pnl=request.min_pnl,
        risk_profile=request.risk_profile,
        limit=request.limit,
        offset=request.offset,
    )

    traders = await handler.handle(query)

    return SearchTradersResponse(
        traders=traders,
        total_count=len(traders),  # Simplified - would need proper count query
    )


@router.get(
    "/metadata",
    response_model=AnalyticsMetadataSchema,
    summary="Get Analytics Metadata",
    description="""
    Get metadata about the analytics system.

    **Includes**:
    - Last full recalculation timestamp
    - Total traders, challenges, trades
    - Cache performance metrics
    - System health indicators
    """,
)
async def get_analytics_metadata(
    repository=Depends(get_analytics_repository),
    cache_service=Depends(get_cache_service),
    audit_logger=Depends(get_audit_logger),
) -> AnalyticsMetadataSchema:
    """Get analytics system metadata."""
    handler = GetAnalyticsMetadataHandler(repository, cache_service, audit_logger)

    query = GetAnalyticsMetadataQuery()
    metadata = await handler.handle(query)

    return AnalyticsMetadataSchema(**metadata)


@router.get(
    "/health",
    summary="Analytics Health Check",
    description="Check analytics service health and cache status.",
)
async def analytics_health(
    cache_service=Depends(get_cache_service),
) -> JSONResponse:
    """Analytics health check."""
    health_status = {
        "status": "healthy",
        "service": "analytics",
        "timestamp": "2024-01-17T12:00:00Z",  # Would be datetime.utcnow()
    }

    # Add cache statistics if available
    if cache_service:
        try:
            cache_stats = await cache_service.get_cache_statistics()
            health_status["cache"] = cache_stats
        except Exception:
            health_status["cache"] = {"status": "unavailable"}

    return JSONResponse(content=health_status)


# Webhook endpoint for receiving domain events
@router.post(
    "/events",
    summary="Receive Domain Events",
    description="Internal endpoint for receiving domain events to update analytics.",
)
async def receive_domain_event(
    event: dict,
    audit_logger=Depends(get_audit_logger),
) -> JSONResponse:
    """Receive domain events for analytics processing."""
    # This would integrate with the event projection system
    # For now, just acknowledge receipt

    event_type = event.get("event_type", "unknown")

    if audit_logger:
        audit_logger.log_business_event(
            event_type="analytics_event_received",
            details={
                "event_type": event_type,
                "event_id": event.get("event_id"),
            },
        )

    return JSONResponse(content={"status": "event_received", "event_type": event_type})