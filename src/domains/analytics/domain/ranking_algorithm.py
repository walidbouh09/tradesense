"""
Leaderboard Ranking Algorithm

Calculates trader rankings based on multiple factors:
- Performance metrics (P&L, win rate, consistency)
- Risk-adjusted returns
- Challenge completion rates
- Trading activity and experience

Supports different ranking periods and challenge types.
"""

from typing import List, Dict, Any, Optional, Callable
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum


class RankingMetric(Enum):
    """Available ranking metrics."""

    NET_PNL = "net_pnl"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTANCY = "expectancy"
    CONSISTENCY_SCORE = "consistency_score"
    PASS_RATE = "pass_rate"
    RISK_ADJUSTED_RETURN = "risk_adjusted_return"
    SHARPE_RATIO = "sharpe_ratio"


class RankingPeriod(Enum):
    """Available ranking periods."""

    ALL_TIME = "all_time"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"


class RankingAlgorithm:
    """Advanced ranking algorithm for trader leaderboards."""

    def __init__(self, minimum_trades: int = 10, minimum_challenges: int = 1):
        self.minimum_trades = minimum_trades
        self.minimum_challenges = minimum_challenges

    def calculate_rankings(
        self,
        traders: List['TraderPerformance'],
        metric: RankingMetric,
        period: RankingPeriod,
        challenge_type: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calculate rankings for traders based on specified metric and period.

        Returns list of ranking entries sorted by rank.
        """
        # Filter eligible traders
        eligible_traders = self._filter_eligible_traders(traders, period, challenge_type)

        if not eligible_traders:
            return []

        # Calculate metric values
        trader_scores = []
        for trader in eligible_traders:
            score = self._calculate_metric_score(trader, metric, weights)
            if score is not None:
                trader_scores.append({
                    'trader': trader,
                    'score': score,
                    'raw_value': self._get_raw_metric_value(trader, metric),
                })

        # Sort by score (descending for most metrics)
        trader_scores.sort(key=lambda x: x['score'], reverse=self._is_descending_metric(metric))

        # Assign ranks and calculate rank changes
        rankings = []
        for position, entry in enumerate(trader_scores, 1):
            trader = entry['trader']

            # Calculate rank change (would need historical data)
            previous_rank = getattr(trader, f'{metric.value}_rank', 0)
            rank_change = previous_rank - position if previous_rank > 0 else 0

            ranking_entry = {
                'rank': position,
                'trader_id': trader.trader_id,
                'username': trader.username,
                'score': entry['score'],
                'raw_value': entry['raw_value'],
                'metric_type': metric.value,
                'period': period.value,
                'challenge_type': challenge_type,
                'rank_change': rank_change,
                'total_challenges': trader.total_challenges,
                'pass_rate': float(trader.pass_rate),
                'trading_days': trader.trading_days,
                'last_updated': datetime.utcnow(),
            }

            rankings.append(ranking_entry)

        return rankings

    def _filter_eligible_traders(
        self,
        traders: List['TraderPerformance'],
        period: RankingPeriod,
        challenge_type: Optional[str],
    ) -> List['TraderPerformance']:
        """Filter traders eligible for ranking."""
        eligible = []

        for trader in traders:
            # Must meet minimum activity requirements
            if trader.total_challenges < self.minimum_challenges:
                continue

            if trader.total_trades < self.minimum_trades:
                continue

            # Must have been active in the period
            if not self._is_active_in_period(trader, period):
                continue

            # Filter by challenge type if specified
            if challenge_type and not self._has_challenge_type(trader, challenge_type):
                continue

            eligible.append(trader)

        return eligible

    def _calculate_metric_score(
        self,
        trader: 'TraderPerformance',
        metric: RankingMetric,
        weights: Optional[Dict[str, float]],
    ) -> Optional[Decimal]:
        """Calculate weighted score for ranking."""
        base_score = self._get_raw_metric_value(trader, metric)
        if base_score is None:
            return None

        # Apply default or custom weights
        if weights:
            # Weighted combination of multiple metrics
            total_weight = sum(weights.values())
            if total_weight == 0:
                return base_score

            weighted_score = Decimal('0')
            for metric_name, weight in weights.items():
                metric_value = self._get_raw_metric_value(trader, RankingMetric(metric_name))
                if metric_value is not None:
                    # Normalize different metrics to 0-1 scale
                    normalized_value = self._normalize_metric(metric_value, RankingMetric(metric_name))
                    weighted_score += normalized_value * Decimal(str(weight))

            return weighted_score / Decimal(str(total_weight))
        else:
            return base_score

    def _get_raw_metric_value(self, trader: 'TraderPerformance', metric: RankingMetric) -> Optional[Decimal]:
        """Get raw metric value from trader performance."""
        metric_map = {
            RankingMetric.NET_PNL: trader.net_pnl,
            RankingMetric.WIN_RATE: trader.win_rate,
            RankingMetric.PROFIT_FACTOR: trader.profit_factor,
            RankingMetric.EXPECTANCY: trader.expectancy,
            RankingMetric.CONSISTENCY_SCORE: self._calculate_consistency_score(trader),
            RankingMetric.PASS_RATE: trader.pass_rate,
            RankingMetric.RISK_ADJUSTED_RETURN: self._calculate_risk_adjusted_return(trader),
            RankingMetric.SHARPE_RATIO: self._calculate_sharpe_ratio(trader),
        }

        return metric_map.get(metric)

    def _calculate_consistency_score(self, trader: 'TraderPerformance') -> Decimal:
        """Calculate consistency score based on steady performance."""
        if trader.trading_days < 7:  # Need at least a week of data
            return Decimal('0')

        # Simplified consistency calculation
        # In production, this would analyze daily P&L volatility
        # and consistency of returns over time

        # Placeholder: average daily P&L divided by standard deviation
        # For now, return a score based on pass rate and trading days
        base_score = float(trader.pass_rate) * min(trader.trading_days / 30, 1.0)
        return Decimal(str(base_score))

    def _calculate_risk_adjusted_return(self, trader: 'TraderPerformance') -> Decimal:
        """Calculate risk-adjusted return (return per unit of risk)."""
        if trader.average_drawdown == 0:
            return trader.net_pnl if trader.net_pnl > 0 else Decimal('0')

        # RAR = Total Return / Max Drawdown
        return trader.net_pnl / abs(trader.average_drawdown)

    def _calculate_sharpe_ratio(self, trader: 'TraderPerformance') -> Decimal:
        """Calculate Sharpe ratio (excess return per unit of volatility)."""
        # Simplified Sharpe ratio calculation
        # In production, would use historical daily returns and risk-free rate

        if trader.trading_days < 30 or trader.average_daily_pnl == 0:
            return Decimal('0')

        # Placeholder: average daily return / volatility estimate
        # Assume 10% annualized volatility as baseline
        daily_volatility = Decimal('0.10') / Decimal('16')  # sqrt(256 trading days)

        if daily_volatility == 0:
            return Decimal('0')

        return trader.average_daily_pnl / daily_volatility

    def _normalize_metric(self, value: Decimal, metric: RankingMetric) -> Decimal:
        """Normalize metric value to 0-1 scale for weighted calculations."""
        # Different normalization strategies for different metrics
        if metric in [RankingMetric.WIN_RATE, RankingMetric.PASS_RATE]:
            # Already 0-1 scale
            return max(Decimal('0'), min(Decimal('1'), value))
        elif metric == RankingMetric.PROFIT_FACTOR:
            # Profit factor: 0.5 = bad, 1.5 = good, 3.0+ = excellent
            return max(Decimal('0'), min(Decimal('1'), (value - Decimal('0.5')) / Decimal('2.5')))
        elif metric in [RankingMetric.NET_PNL, RankingMetric.EXPECTANCY]:
            # P&L metrics: normalize based on magnitude
            # Simple approach: sigmoid function
            return Decimal('1') / (Decimal('1') + Decimal('2.718').pow(-value / Decimal('1000')))
        else:
            # Default: assume positive is better, normalize to 0-1
            return max(Decimal('0'), min(Decimal('1'), value / Decimal('100') if value > 0 else Decimal('0')))

    def _is_descending_metric(self, metric: RankingMetric) -> bool:
        """Check if higher metric values mean better ranking."""
        # Most metrics: higher = better (descending sort)
        # Some metrics might be ascending (lower = better)
        ascending_metrics = []  # Add metrics where lower values are better
        return metric not in ascending_metrics

    def _is_active_in_period(self, trader: 'TraderPerformance', period: RankingPeriod) -> bool:
        """Check if trader was active in the specified period."""
        if period == RankingPeriod.ALL_TIME:
            return True

        # Check last active date against period
        now = datetime.utcnow()
        period_map = {
            RankingPeriod.DAILY: timedelta(days=1),
            RankingPeriod.WEEKLY: timedelta(weeks=1),
            RankingPeriod.MONTHLY: timedelta(days=30),
            RankingPeriod.YEARLY: timedelta(days=365),
        }

        cutoff = now - period_map.get(period, timedelta(days=365))
        return trader.last_active >= cutoff

    def _has_challenge_type(self, trader: 'TraderPerformance', challenge_type: str) -> bool:
        """Check if trader has participated in specified challenge type."""
        # This would check trader's challenge history
        # For now, assume all traders have participated in all types
        return True

    def get_recommended_weights(self, metric: RankingMetric) -> Dict[str, float]:
        """Get recommended weights for composite scoring."""
        # Predefined weight combinations for different ranking goals

        weight_presets = {
            RankingMetric.NET_PNL: {
                "net_pnl": 0.6,
                "consistency_score": 0.2,
                "pass_rate": 0.2,
            },
            RankingMetric.WIN_RATE: {
                "win_rate": 0.5,
                "profit_factor": 0.3,
                "expectancy": 0.2,
            },
            RankingMetric.CONSISTENCY_SCORE: {
                "consistency_score": 0.4,
                "risk_adjusted_return": 0.3,
                "sharpe_ratio": 0.3,
            },
        }

        return weight_presets.get(metric, {"net_pnl": 1.0})

    def calculate_percentile_rank(self, trader_score: Decimal, all_scores: List[Decimal]) -> Decimal:
        """Calculate percentile rank for a trader's score."""
        if not all_scores:
            return Decimal('0')

        # Count scores below trader's score
        below_count = sum(1 for score in all_scores if score < trader_score)
        total_count = len(all_scores)

        return Decimal(str(below_count)) / Decimal(str(total_count)) * Decimal('100')