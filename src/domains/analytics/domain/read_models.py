"""
Analytics Read Models - Optimized for Query Performance

These models are:
- Denormalized for fast queries
- Updated via event projections
- Never modified directly by business logic
- Eventual consistency acceptable
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal


class TraderPerformance:
    """Denormalized trader performance metrics."""

    def __init__(
        self,
        trader_id: str,
        username: str,
        registration_date: datetime,
        last_active: datetime,

        # Challenge Statistics
        total_challenges: int = 0,
        active_challenges: int = 0,
        passed_challenges: int = 0,
        failed_challenges: int = 0,

        # Financial Metrics
        total_profit: Decimal = Decimal('0'),
        total_loss: Decimal = Decimal('0'),
        net_pnl: Decimal = Decimal('0'),
        largest_win: Decimal = Decimal('0'),
        largest_loss: Decimal = Decimal('0'),

        # Trading Activity
        total_trades: int = 0,
        winning_trades: int = 0,
        losing_trades: int = 0,
        win_rate: Decimal = Decimal('0'),

        # Risk Metrics
        best_drawdown: Decimal = Decimal('0'),  # Best (least negative) drawdown
        worst_drawdown: Decimal = Decimal('0'),  # Worst (most negative) drawdown
        average_drawdown: Decimal = Decimal('0'),

        # Time-based metrics
        trading_days: int = 0,
        average_daily_pnl: Decimal = Decimal('0'),
        consistency_score: Decimal = Decimal('0'),  # Based on steady performance

        # Rankings
        overall_rank: int = 0,
        monthly_rank: int = 0,
        challenge_type_ranks: Dict[str, int] = None,

        # Metadata
        favorite_instruments: List[str] = None,
        preferred_timeframes: List[str] = None,
        risk_profile: str = "unknown",  # conservative, moderate, aggressive

        # Cache timestamps
        last_updated: datetime = None,
        rank_last_updated: datetime = None,
    ):
        self.trader_id = trader_id
        self.username = username
        self.registration_date = registration_date
        self.last_active = last_active

        self.total_challenges = total_challenges
        self.active_challenges = active_challenges
        self.passed_challenges = passed_challenges
        self.failed_challenges = failed_challenges

        self.total_profit = total_profit
        self.total_loss = total_loss
        self.net_pnl = net_pnl
        self.largest_win = largest_win
        self.largest_loss = largest_loss

        self.total_trades = total_trades
        self.winning_trades = winning_trades
        self.losing_trades = losing_trades
        self.win_rate = win_rate

        self.best_drawdown = best_drawdown
        self.worst_drawdown = worst_drawdown
        self.average_drawdown = average_drawdown

        self.trading_days = trading_days
        self.average_daily_pnl = average_daily_pnl
        self.consistency_score = consistency_score

        self.overall_rank = overall_rank
        self.monthly_rank = monthly_rank
        self.challenge_type_ranks = challenge_type_ranks or {}

        self.favorite_instruments = favorite_instruments or []
        self.preferred_timeframes = preferred_timeframes or []
        self.risk_profile = risk_profile

        self.last_updated = last_updated
        self.rank_last_updated = rank_last_updated

    @property
    def pass_rate(self) -> Decimal:
        """Calculate challenge pass rate."""
        if self.total_challenges == 0:
            return Decimal('0')
        return Decimal(str(self.passed_challenges)) / Decimal(str(self.total_challenges))

    @property
    def profit_factor(self) -> Decimal:
        """Calculate profit factor (gross profit / gross loss)."""
        if self.total_loss == 0:
            return Decimal('0') if self.total_profit == 0 else Decimal('999')
        return self.total_profit / abs(self.total_loss)

    @property
    def expectancy(self) -> Decimal:
        """Calculate expectancy (average win * win rate - average loss * loss rate)."""
        if self.total_trades == 0:
            return Decimal('0')

        avg_win = self.total_profit / self.winning_trades if self.winning_trades > 0 else Decimal('0')
        avg_loss = abs(self.total_loss) / self.losing_trades if self.losing_trades > 0 else Decimal('0')
        win_rate = self.win_rate
        loss_rate = Decimal('1') - win_rate

        return (avg_win * win_rate) - (avg_loss * loss_rate)


class ChallengeAnalytics:
    """Challenge-level analytics and statistics."""

    def __init__(
        self,
        challenge_id: str,
        trader_id: str,
        challenge_type: str,
        status: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,

        # Performance metrics
        initial_balance: Decimal = Decimal('0'),
        current_balance: Decimal = Decimal('0'),
        peak_balance: Decimal = Decimal('0'),
        final_pnl: Decimal = Decimal('0'),
        total_trades: int = 0,

        # Risk metrics
        max_drawdown: Decimal = Decimal('0'),
        max_drawdown_percentage: Decimal = Decimal('0'),
        daily_loss_limit: Decimal = Decimal('0'),
        total_loss_limit: Decimal = Decimal('0'),

        # Trading activity
        trading_days: int = 0,
        winning_days: int = 0,
        losing_days: int = 0,

        # Violation tracking
        rule_violations: int = 0,
        critical_violations: int = 0,
        warning_violations: int = 0,

        # Metadata
        failure_reason: Optional[str] = None,
        passed_requirements: List[str] = None,
        failed_requirements: List[str] = None,

        # Rankings within challenge
        challenge_rank: int = 0,
        percentile_rank: Decimal = Decimal('0'),  # 0-100

        last_updated: datetime = None,
    ):
        self.challenge_id = challenge_id
        self.trader_id = trader_id
        self.challenge_type = challenge_type
        self.status = status
        self.start_date = start_date
        self.end_date = end_date

        self.initial_balance = initial_balance
        self.current_balance = current_balance
        self.peak_balance = peak_balance
        self.final_pnl = final_pnl
        self.total_trades = total_trades

        self.max_drawdown = max_drawdown
        self.max_drawdown_percentage = max_drawdown_percentage
        self.daily_loss_limit = daily_loss_limit
        self.total_loss_limit = total_loss_limit

        self.trading_days = trading_days
        self.winning_days = winning_days
        self.losing_days = losing_days

        self.rule_violations = rule_violations
        self.critical_violations = critical_violations
        self.warning_violations = warning_violations

        self.failure_reason = failure_reason
        self.passed_requirements = passed_requirements or []
        self.failed_requirements = failed_requirements or []

        self.challenge_rank = challenge_rank
        self.percentile_rank = percentile_rank

        self.last_updated = last_updated or datetime.utcnow()

    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate P&L as percentage of initial balance."""
        if self.initial_balance == 0:
            return Decimal('0')
        return (self.final_pnl / self.initial_balance) * Decimal('100')

    @property
    def drawdown_percentage(self) -> Decimal:
        """Calculate drawdown as percentage of initial balance."""
        if self.initial_balance == 0:
            return Decimal('0')
        return (self.max_drawdown / self.initial_balance) * Decimal('100')

    @property
    def completion_rate(self) -> Decimal:
        """Calculate challenge completion rate (0-100)."""
        # Simplified - would be based on requirements met
        if self.status == "PASSED":
            return Decimal('100')
        elif self.status == "FAILED":
            return Decimal('0')
        else:
            # Active challenge - estimate based on progress
            return Decimal('50')  # Placeholder


class LeaderboardEntry:
    """Leaderboard entry with ranking information."""

    def __init__(
        self,
        rank: int,
        trader_id: str,
        username: str,
        metric_value: Decimal,
        metric_type: str,  # 'pnl', 'win_rate', 'consistency', etc.
        period: str,  # 'all_time', 'monthly', 'weekly', 'daily'
        challenge_type: Optional[str] = None,  # 'PHASE_1', 'PHASE_2', etc.

        # Additional context
        total_challenges: int = 0,
        pass_rate: Decimal = Decimal('0'),
        trading_days: int = 0,

        # Change indicators
        rank_change: int = 0,  # +1 (moved up), -1 (moved down), 0 (same)
        value_change: Decimal = Decimal('0'),  # Change in metric value

        last_updated: datetime = None,
    ):
        self.rank = rank
        self.trader_id = trader_id
        self.username = username
        self.metric_value = metric_value
        self.metric_type = metric_type
        self.period = period
        self.challenge_type = challenge_type

        self.total_challenges = total_challenges
        self.pass_rate = pass_rate
        self.trading_days = trading_days

        self.rank_change = rank_change
        self.value_change = value_change

        self.last_updated = last_updated or datetime.utcnow()


class LeaderboardSnapshot:
    """Snapshot of leaderboard at a point in time."""

    def __init__(
        self,
        leaderboard_id: str,
        metric_type: str,
        period: str,
        challenge_type: Optional[str],
        entries: List[LeaderboardEntry],
        total_entries: int,
        snapshot_time: datetime,
        next_update_time: datetime,
    ):
        self.leaderboard_id = leaderboard_id
        self.metric_type = metric_type
        self.period = period
        self.challenge_type = challenge_type
        self.entries = entries
        self.total_entries = total_entries
        self.snapshot_time = snapshot_time
        self.next_update_time = next_update_time


class AnalyticsMetadata:
    """Metadata about analytics calculations and caching."""

    def __init__(
        self,
        last_full_recalculation: datetime,
        total_traders: int,
        total_challenges: int,
        total_trades: int,
        cache_hit_rate: Decimal = Decimal('0'),
        average_calculation_time: float = 0.0,
    ):
        self.last_full_recalculation = last_full_recalculation
        self.total_traders = total_traders
        self.total_challenges = total_challenges
        self.total_trades = total_trades
        self.cache_hit_rate = cache_hit_rate
        self.average_calculation_time = average_calculation_time