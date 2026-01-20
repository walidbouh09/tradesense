"""Analytics API schemas."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from decimal import Decimal

from pydantic import BaseModel, Field, validator


class LeaderboardEntrySchema(BaseModel):
    """Schema for leaderboard entry."""

    rank: int
    trader_id: str
    username: str
    score: float
    raw_value: float
    metric_type: str
    period: str
    challenge_type: Optional[str] = None
    rank_change: int
    total_challenges: int
    pass_rate: float
    trading_days: int
    last_updated: datetime


class LeaderboardResponse(BaseModel):
    """Response schema for leaderboard queries."""

    entries: List[LeaderboardEntrySchema]
    total_count: int
    cached: bool
    cache_timestamp: Optional[datetime] = None


class TraderPerformanceSchema(BaseModel):
    """Schema for trader performance details."""

    trader_id: str
    username: str
    registration_date: datetime
    last_active: datetime
    total_challenges: int
    active_challenges: int
    passed_challenges: int
    failed_challenges: int
    total_profit: float
    total_loss: float
    net_pnl: float
    largest_win: float
    largest_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    best_drawdown: float
    worst_drawdown: float
    average_drawdown: float
    trading_days: int
    average_daily_pnl: float
    consistency_score: float
    overall_rank: int
    monthly_rank: int
    pass_rate: float
    profit_factor: float
    expectancy: float
    favorite_instruments: List[str]
    preferred_timeframes: List[str]
    risk_profile: str
    last_updated: Optional[datetime] = None
    cached: bool


class TopPerformersResponse(BaseModel):
    """Response schema for top performers."""

    performers: List[LeaderboardEntrySchema]


class SearchTradersRequest(BaseModel):
    """Request schema for trader search."""

    min_pass_rate: Optional[float] = Field(None, ge=0, le=1)
    min_trades: Optional[int] = Field(None, ge=0)
    min_pnl: Optional[float] = None
    risk_profile: Optional[str] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class TraderSummarySchema(BaseModel):
    """Schema for trader summary in search results."""

    trader_id: str
    username: str
    pass_rate: float
    total_trades: int
    net_pnl: float
    risk_profile: str
    total_challenges: int


class SearchTradersResponse(BaseModel):
    """Response schema for trader search."""

    traders: List[TraderSummarySchema]
    total_count: int


class AnalyticsMetadataSchema(BaseModel):
    """Schema for analytics metadata."""

    last_full_recalculation: datetime
    total_traders: int
    total_challenges: int
    total_trades: int
    cache_hit_rate: float
    average_calculation_time: float


class TraderComparisonSchema(BaseModel):
    """Schema for trader comparison."""

    trader_id: str
    username: str
    metrics: Dict[str, float]


class TraderComparisonResponse(BaseModel):
    """Response schema for trader comparison."""

    traders: List[TraderComparisonSchema]
    requested_metrics: List[str]


class ChallengeTypeStatsSchema(BaseModel):
    """Schema for challenge type statistics."""

    challenge_type: str
    period: str
    total_challenges: int
    completion_rate: float
    average_duration_days: float
    average_pnl_percentage: float
    average_max_drawdown: float
    pass_rate: float
    total_traders: int


# Error schemas
class ErrorDetail(BaseModel):
    """Error detail schema."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None


# Validation helpers
@validator('metric_type')
def validate_metric_type(cls, v):
    valid_metrics = {
        'net_pnl', 'win_rate', 'profit_factor', 'expectancy',
        'consistency_score', 'pass_rate', 'risk_adjusted_return', 'sharpe_ratio'
    }
    if v not in valid_metrics:
        raise ValueError(f"Invalid metric type. Must be one of: {', '.join(valid_metrics)}")
    return v


@validator('period')
def validate_period(cls, v):
    valid_periods = {'all_time', 'yearly', 'monthly', 'weekly', 'daily'}
    if v not in valid_periods:
        raise ValueError(f"Invalid period. Must be one of: {', '.join(valid_periods)}")
    return v


@validator('challenge_type')
def validate_challenge_type(cls, v):
    if v is None:
        return v
    valid_types = {'PHASE_1', 'PHASE_2', 'PHASE_3'}
    if v not in valid_types:
        raise ValueError(f"Invalid challenge type. Must be one of: {', '.join(valid_types)}")
    return v