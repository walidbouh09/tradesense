"""
Feature Engineering for Risk Analysis

Extracts risk-relevant features from historical trade data.
All functions are pure, deterministic, and explainable.

Features computed:
- Performance metrics: profitability and consistency
- Risk metrics: drawdown behavior and loss patterns
- Behavioral metrics: trading frequency and patterns

All calculations are designed to be:
- Financially meaningful
- Statistically robust
- Regulatorily explainable
- Computationally efficient
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from statistics import mean, stdev, pstdev


@dataclass
class TradeData:
    """Immutable trade data structure for feature engineering."""
    trade_id: str
    symbol: str
    side: str  # BUY or SELL
    quantity: Decimal
    price: Decimal
    realized_pnl: Decimal
    executed_at: datetime

    @property
    def is_profit(self) -> bool:
        """Check if this trade resulted in a profit."""
        return self.realized_pnl > 0

    @property
    def is_loss(self) -> bool:
        """Check if this trade resulted in a loss."""
        return self.realized_pnl < 0


@dataclass
class FeatureSet:
    """Collection of computed risk features."""
    # Performance features
    avg_trade_pnl: Decimal
    pnl_volatility: Decimal
    win_rate: Decimal
    profit_factor: Decimal

    # Risk features
    max_intraday_drawdown: Decimal
    drawdown_speed: Decimal
    loss_streak: int

    # Behavioral features
    trades_per_hour: Decimal
    overtrading_score: Decimal
    revenge_trading_score: Decimal

    # Metadata
    total_trades: int
    analysis_period_hours: Decimal
    computed_at: datetime


class FeatureEngineer:
    """
    Feature Engineering for Trader Risk Analysis.

    Extracts risk-relevant features from trade history using
    pure functions with no external dependencies.
    """

    @staticmethod
    def compute_features(trades: List[TradeData], challenge_started_at: datetime) -> FeatureSet:
        """
        Compute complete feature set from trade history.

        Args:
            trades: List of historical trades (sorted by execution time)
            challenge_started_at: When the challenge began

        Returns:
            FeatureSet with all computed risk features

        Note:
            Returns default safe values if insufficient data
        """
        if not trades:
            return FeatureEngineer._default_features(challenge_started_at)

        # Sort trades by execution time (ensure chronological order)
        sorted_trades = sorted(trades, key=lambda t: t.executed_at)

        # Compute time-based metrics
        analysis_period = FeatureEngineer._compute_analysis_period(
            challenge_started_at, sorted_trades
        )

        # Performance features
        performance_features = FeatureEngineer._compute_performance_features(sorted_trades)

        # Risk features
        risk_features = FeatureEngineer._compute_risk_features(sorted_trades)

        # Behavioral features
        behavioral_features = FeatureEngineer._compute_behavioral_features(
            sorted_trades, analysis_period
        )

        return FeatureSet(
            # Performance
            avg_trade_pnl=performance_features['avg_trade_pnl'],
            pnl_volatility=performance_features['pnl_volatility'],
            win_rate=performance_features['win_rate'],
            profit_factor=performance_features['profit_factor'],

            # Risk
            max_intraday_drawdown=risk_features['max_intraday_drawdown'],
            drawdown_speed=risk_features['drawdown_speed'],
            loss_streak=risk_features['loss_streak'],

            # Behavioral
            trades_per_hour=behavioral_features['trades_per_hour'],
            overtrading_score=behavioral_features['overtrading_score'],
            revenge_trading_score=behavioral_features['revenge_trading_score'],

            # Metadata
            total_trades=len(trades),
            analysis_period_hours=analysis_period,
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    @staticmethod
    def _default_features(challenge_started_at: datetime) -> FeatureSet:
        """Return safe default values when no trades available."""
        return FeatureSet(
            avg_trade_pnl=Decimal('0'),
            pnl_volatility=Decimal('0'),
            win_rate=Decimal('0'),
            profit_factor=Decimal('1'),  # Neutral profit factor
            max_intraday_drawdown=Decimal('0'),
            drawdown_speed=Decimal('0'),
            loss_streak=0,
            trades_per_hour=Decimal('0'),
            overtrading_score=Decimal('0'),
            revenge_trading_score=Decimal('0'),
            total_trades=0,
            analysis_period_hours=Decimal('1'),  # Minimum 1 hour
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    @staticmethod
    def _compute_analysis_period(challenge_started_at: datetime, trades: List[TradeData]) -> Decimal:
        """
        Compute analysis period in hours.

        Financial Meaning: How long has this trader been active?
        Used to normalize frequency-based metrics.
        """
        if not trades:
            return Decimal('1')  # Minimum period

        first_trade = min(trades, key=lambda t: t.executed_at)
        last_trade = max(trades, key=lambda t: t.executed_at)

        # Use challenge start if earlier than first trade
        start_time = min(challenge_started_at, first_trade.executed_at)
        end_time = max(last_trade.executed_at, datetime.utcnow().replace(tzinfo=None))

        duration = end_time - start_time
        hours = duration.total_seconds() / 3600

        return Decimal(str(max(hours, 1.0)))  # Minimum 1 hour

    @staticmethod
    def _compute_performance_features(trades: List[TradeData]) -> Dict[str, Decimal]:
        """
        Compute performance-related risk features.

        Financial Meaning: How profitable and consistent is this trader?
        """
        if not trades:
            return {
                'avg_trade_pnl': Decimal('0'),
                'pnl_volatility': Decimal('0'),
                'win_rate': Decimal('0'),
                'profit_factor': Decimal('1')
            }

        pnl_values = [float(t.realized_pnl) for t in trades]

        # Average trade PnL
        avg_trade_pnl = Decimal(str(mean(pnl_values)))

        # PnL volatility (population standard deviation)
        pnl_volatility = Decimal('0')
        if len(pnl_values) > 1:
            pnl_volatility = Decimal(str(pstdev(pnl_values)))

        # Win rate (percentage of profitable trades)
        winning_trades = sum(1 for t in trades if t.is_profit)
        win_rate = Decimal(str(winning_trades / len(trades) * 100))

        # Profit factor (gross profit / gross loss)
        gross_profit = sum(t.realized_pnl for t in trades if t.is_profit)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.is_loss))

        profit_factor = Decimal('1')  # Default neutral
        if gross_loss > 0:
            profit_factor = Decimal(str(float(gross_profit / gross_loss)))

        return {
            'avg_trade_pnl': avg_trade_pnl.quantize(Decimal('0.01')),
            'pnl_volatility': pnl_volatility.quantize(Decimal('0.01')),
            'win_rate': win_rate.quantize(Decimal('0.01')),
            'profit_factor': profit_factor.quantize(Decimal('0.01'))
        }

    @staticmethod
    def _compute_risk_features(trades: List[TradeData]) -> Dict[str, Any]:
        """
        Compute risk-related features.

        Financial Meaning: How much risk does this trader take?
        """
        if not trades:
            return {
                'max_intraday_drawdown': Decimal('0'),
                'drawdown_speed': Decimal('0'),
                'loss_streak': 0
            }

        # Max intraday drawdown
        max_intraday_drawdown = FeatureEngineer._compute_max_intraday_drawdown(trades)

        # Drawdown speed (how quickly does equity decline)
        drawdown_speed = FeatureEngineer._compute_drawdown_speed(trades)

        # Current loss streak
        loss_streak = FeatureEngineer._compute_loss_streak(trades)

        return {
            'max_intraday_drawdown': max_intraday_drawdown,
            'drawdown_speed': drawdown_speed,
            'loss_streak': loss_streak
        }

    @staticmethod
    def _compute_max_intraday_drawdown(trades: List[TradeData]) -> Decimal:
        """
        Compute maximum intraday drawdown percentage.

        Financial Meaning: Largest single-day equity decline experienced.
        Indicates trader's maximum risk tolerance in a day.
        """
        if not trades:
            return Decimal('0')

        # Group trades by day
        daily_equity = {}
        current_equity = Decimal('10000')  # Assume starting balance

        for trade in trades:
            day_key = trade.executed_at.date()
            if day_key not in daily_equity:
                daily_equity[day_key] = []

            current_equity += trade.realized_pnl
            daily_equity[day_key].append(float(current_equity))

        # Compute drawdown for each day
        max_drawdown = Decimal('0')

        for day_trades in daily_equity.values():
            if len(day_trades) < 2:
                continue

            day_start = day_trades[0]
            day_low = min(day_trades)

            if day_start > 0:
                drawdown_pct = (day_start - day_low) / day_start * 100
                max_drawdown = max(max_drawdown, Decimal(str(drawdown_pct)))

        return max_drawdown.quantize(Decimal('0.01'))

    @staticmethod
    def _compute_drawdown_speed(trades: List[TradeData]) -> Decimal:
        """
        Compute drawdown speed (equity decline rate).

        Financial Meaning: How quickly does this trader lose money?
        Measured as average drawdown percentage per losing trade.
        """
        if not trades:
            return Decimal('0')

        losing_trades = [t for t in trades if t.is_loss]
        if not losing_trades:
            return Decimal('0')

        # Average loss percentage per losing trade
        avg_loss_pct = abs(mean(float(t.realized_pnl) for t in losing_trades))

        # Normalize to starting equity assumption
        starting_equity = Decimal('10000')
        speed_score = (avg_loss_pct / float(starting_equity)) * 100

        return Decimal(str(speed_score)).quantize(Decimal('0.01'))

    @staticmethod
    def _compute_loss_streak(trades: List[TradeData]) -> int:
        """
        Compute current loss streak.

        Financial Meaning: How many consecutive losing trades?
        Indicates potential emotional trading or strategy issues.
        """
        if not trades:
            return 0

        # Find the longest current loss streak (from end backwards)
        streak = 0
        for trade in reversed(trades):
            if trade.is_loss:
                streak += 1
            else:
                break

        return streak

    @staticmethod
    def _compute_behavioral_features(trades: List[TradeData], analysis_period_hours: Decimal) -> Dict[str, Decimal]:
        """
        Compute behavioral risk features.

        Financial Meaning: How does this trader behave?
        """
        if not trades:
            return {
                'trades_per_hour': Decimal('0'),
                'overtrading_score': Decimal('0'),
                'revenge_trading_score': Decimal('0')
            }

        # Trading frequency
        trades_per_hour = Decimal(str(len(trades) / float(analysis_period_hours)))

        # Overtrading score (excessive trading relative to profitability)
        overtrading_score = FeatureEngineer._compute_overtrading_score(trades, trades_per_hour)

        # Revenge trading score (increasing position size after losses)
        revenge_trading_score = FeatureEngineer._compute_revenge_trading_score(trades)

        return {
            'trades_per_hour': trades_per_hour.quantize(Decimal('0.01')),
            'overtrading_score': overtrading_score,
            'revenge_trading_score': revenge_trading_score
        }

    @staticmethod
    def _compute_overtrading_score(trades: List[TradeData], trades_per_hour: Decimal) -> Decimal:
        """
        Compute overtrading score.

        Financial Meaning: Does this trader trade too frequently relative to success?
        High frequency with low win rate suggests overtrading.
        """
        if not trades:
            return Decimal('0')

        win_rate = sum(1 for t in trades if t.is_profit) / len(trades)

        # Overtrading score: frequency penalty × (1 - win_rate)
        frequency_penalty = min(float(trades_per_hour) / 10, 1.0)  # Cap at 1.0
        overtrading_score = frequency_penalty * (1 - win_rate) * 100

        return Decimal(str(overtrading_score)).quantize(Decimal('0.01'))

    @staticmethod
    def _compute_revenge_trading_score(trades: List[TradeData]) -> Decimal:
        """
        Compute revenge trading score.

        Financial Meaning: Does this trader increase position size after losses?
        Indicates emotional decision-making.
        """
        if len(trades) < 3:
            return Decimal('0')

        revenge_instances = 0
        total_sequences = 0

        # Look for loss followed by larger position
        for i in range(len(trades) - 1):
            current_trade = trades[i]
            next_trade = trades[i + 1]

            if current_trade.is_loss:
                total_sequences += 1
                # Check if next trade has larger position size
                current_size = float(current_trade.quantity * current_trade.price)
                next_size = float(next_trade.quantity * next_trade.price)

                if next_size > current_size * 1.2:  # 20% larger
                    revenge_instances += 1

        if total_sequences == 0:
            return Decimal('0')

        revenge_rate = revenge_instances / total_sequences
        revenge_score = revenge_rate * 100

        return Decimal(str(revenge_score)).quantize(Decimal('0.01'))