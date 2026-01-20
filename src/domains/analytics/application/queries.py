"""Analytics application queries."""

from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal


@dataclass
class GetLeaderboardQuery:
    """Query to get leaderboard rankings."""

    metric_type: str  # 'net_pnl', 'win_rate', 'consistency_score', etc.
    period: str = "all_time"  # 'all_time', 'monthly', 'weekly', 'daily'
    challenge_type: Optional[str] = None  # 'PHASE_1', 'PHASE_2', etc.
    limit: int = 100
    offset: int = 0


@dataclass
class GetTraderPerformanceQuery:
    """Query to get trader performance details."""

    trader_id: str


@dataclass
class GetChallengeAnalyticsQuery:
    """Query to get challenge analytics."""

    challenge_id: str


@dataclass
class GetTopPerformersQuery:
    """Query to get top performers for a metric."""

    metric_type: str
    period: str = "monthly"
    challenge_type: Optional[str] = None
    limit: int = 10


@dataclass
class SearchTradersQuery:
    """Query to search traders by performance criteria."""

    min_pass_rate: Optional[Decimal] = None
    min_trades: Optional[int] = None
    min_pnl: Optional[Decimal] = None
    risk_profile: Optional[str] = None
    limit: int = 50
    offset: int = 0


@dataclass
class GetAnalyticsMetadataQuery:
    """Query to get analytics system metadata."""

    pass  # No parameters needed


@dataclass
class GetTraderComparisonQuery:
    """Query to compare trader performance."""

    trader_ids: List[str]
    metrics: List[str] = None  # If None, return all metrics


@dataclass
class GetChallengeTypeStatsQuery:
    """Query to get statistics by challenge type."""

    challenge_type: str
    period: str = "all_time"