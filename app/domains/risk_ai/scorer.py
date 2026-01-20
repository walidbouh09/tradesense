"""
Explainable Baseline Risk Scoring Model

Computes risk scores using weighted heuristic combinations of features.
Fully explainable, deterministic, and regulator-friendly.

Scoring Formula:
Risk Score = (Volatility × 0.30) + (Drawdown × 0.25) + (Behavior × 0.20) +
             (Loss Streak × 0.15) + (Overtrading × 0.10)

Where each component is normalized to 0-100 scale.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any
from datetime import datetime

from .features import FeatureSet


@dataclass
class RiskScore:
    """Complete risk assessment result."""
    score: Decimal  # 0-100 risk score
    level: str      # STABLE, MONITOR, HIGH_RISK, CRITICAL
    breakdown: Dict[str, Any]  # Detailed score components
    computed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'score': float(self.score),
            'level': self.level,
            'breakdown': self.breakdown,
            'computed_at': self.computed_at.isoformat()
        }


class RiskScorer:
    """
    Baseline Risk Scoring Model.

    Uses weighted heuristic combinations of features to compute
    explainable risk scores. Designed for regulatory transparency.

    Scoring Weights (Total = 100%):
    - Volatility: 30% (consistency of returns)
    - Drawdown Behavior: 25% (risk-taking patterns)
    - Trading Behavior: 20% (trading frequency and patterns)
    - Loss Streak: 15% (current losing momentum)
    - Overtrading: 10% (excessive trading relative to success)
    """

    # Component weights (must sum to 1.0)
    WEIGHTS = {
        'volatility': Decimal('0.30'),      # 30%
        'drawdown': Decimal('0.25'),        # 25%
        'behavior': Decimal('0.20'),        # 20%
        'loss_streak': Decimal('0.15'),     # 15%
        'overtrading': Decimal('0.10'),     # 10%
    }

    @staticmethod
    def compute_score(features: FeatureSet) -> RiskScore:
        """
        Compute complete risk score from feature set.

        Args:
            features: Engineered features from FeatureEngineer

        Returns:
            RiskScore with score, level, and detailed breakdown
        """
        # Compute individual component scores (0-100 scale)
        volatility_score = RiskScorer._compute_volatility_score(features)
        drawdown_score = RiskScorer._compute_drawdown_score(features)
        behavior_score = RiskScorer._compute_behavior_score(features)
        loss_streak_score = RiskScorer._compute_loss_streak_score(features)
        overtrading_score = RiskScorer._compute_overtrading_score(features)

        # Apply weights and sum
        weighted_volatility = volatility_score * RiskScorer.WEIGHTS['volatility']
        weighted_drawdown = drawdown_score * RiskScorer.WEIGHTS['drawdown']
        weighted_behavior = behavior_score * RiskScorer.WEIGHTS['behavior']
        weighted_loss_streak = loss_streak_score * RiskScorer.WEIGHTS['loss_streak']
        weighted_overtrading = overtrading_score * RiskScorer.WEIGHTS['overtrading']

        total_score = (
            weighted_volatility +
            weighted_drawdown +
            weighted_behavior +
            weighted_loss_streak +
            weighted_overtrading
        )

        # Ensure bounds (should be 0-100, but clamp for safety)
        final_score = max(Decimal('0'), min(Decimal('100'), total_score))

        # Create detailed breakdown
        breakdown = {
            'components': {
                'volatility': {
                    'raw_score': float(volatility_score),
                    'weight': float(RiskScorer.WEIGHTS['volatility']),
                    'contribution': float(weighted_volatility),
                    'explanation': 'Return consistency and predictability'
                },
                'drawdown': {
                    'raw_score': float(drawdown_score),
                    'weight': float(RiskScorer.WEIGHTS['drawdown']),
                    'contribution': float(weighted_drawdown),
                    'explanation': 'Risk-taking patterns and loss tolerance'
                },
                'behavior': {
                    'raw_score': float(behavior_score),
                    'weight': float(RiskScorer.WEIGHTS['behavior']),
                    'contribution': float(weighted_behavior),
                    'explanation': 'Trading frequency and market participation'
                },
                'loss_streak': {
                    'raw_score': float(loss_streak_score),
                    'weight': float(RiskScorer.WEIGHTS['loss_streak']),
                    'contribution': float(weighted_loss_streak),
                    'explanation': 'Current losing momentum and streak risk'
                },
                'overtrading': {
                    'raw_score': float(overtrading_score),
                    'weight': float(RiskScorer.WEIGHTS['overtrading']),
                    'contribution': float(weighted_overtrading),
                    'explanation': 'Excessive trading relative to profitability'
                }
            },
            'total_score': float(final_score),
            'feature_summary': {
                'total_trades': features.total_trades,
                'analysis_period_hours': float(features.analysis_period_hours),
                'avg_trade_pnl': float(features.avg_trade_pnl),
                'win_rate': float(features.win_rate),
                'pnl_volatility': float(features.pnl_volatility)
            }
        }

        return RiskScore(
            score=final_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            level=RiskScorer._classify_risk_level(final_score),
            breakdown=breakdown,
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    @staticmethod
    def _compute_volatility_score(features: FeatureSet) -> Decimal:
        """
        Compute volatility component score (0-100).

        High volatility indicates unpredictable returns, increasing risk.
        Uses PnL standard deviation normalized by average trade size.
        """
        if features.total_trades < 2:
            return Decimal('50')  # Neutral score for insufficient data

        # Volatility ratio: std_dev / |mean|
        if features.avg_trade_pnl == 0:
            volatility_ratio = float('inf')  # Infinite volatility if no average return
        else:
            volatility_ratio = float(features.pnl_volatility / abs(features.avg_trade_pnl))

        # Convert to 0-100 score (higher ratio = higher risk)
        # Cap at 5.0 ratio for scoring purposes
        capped_ratio = min(volatility_ratio, 5.0)
        score = Decimal(str(capped_ratio / 5.0 * 100))

        return min(Decimal('100'), max(Decimal('0'), score))

    @staticmethod
    def _compute_drawdown_score(features: FeatureSet) -> Decimal:
        """
        Compute drawdown behavior component score (0-100).

        High drawdown indicates aggressive risk-taking.
        Combines max drawdown percentage and drawdown speed.
        """
        # Max drawdown contribution (70% weight)
        max_dd_score = min(Decimal('100'), features.max_intraday_drawdown * Decimal('2'))

        # Drawdown speed contribution (30% weight)
        speed_score = min(Decimal('100'), features.drawdown_speed * Decimal('10'))

        # Weighted combination
        combined_score = (max_dd_score * Decimal('0.7')) + (speed_score * Decimal('0.3'))

        return min(Decimal('100'), max(Decimal('0'), combined_score))

    @staticmethod
    def _compute_behavior_score(features: FeatureSet) -> Decimal:
        """
        Compute trading behavior component score (0-100).

        Evaluates trading frequency and market participation patterns.
        Very high or very low frequency can indicate risk.
        """
        # Base score from trades per hour
        # Optimal range: 1-5 trades per hour
        tph = float(features.trades_per_hour)

        if tph < 1:
            # Too few trades - may indicate lack of activity
            base_score = Decimal('30')
        elif tph <= 5:
            # Optimal trading frequency
            base_score = Decimal('10')
        elif tph <= 10:
            # Moderately high frequency
            base_score = Decimal('40')
        else:
            # Very high frequency - potential overtrading
            base_score = Decimal('80')

        return base_score

    @staticmethod
    def _compute_loss_streak_score(features: FeatureSet) -> Decimal:
        """
        Compute loss streak component score (0-100).

        Current losing momentum increases risk score.
        Longer streaks indicate higher emotional risk.
        """
        streak = features.loss_streak

        if streak == 0:
            return Decimal('0')  # No current losing streak
        elif streak == 1:
            return Decimal('20')  # Single loss
        elif streak == 2:
            return Decimal('40')  # Double loss
        elif streak == 3:
            return Decimal('65')  # Triple loss
        elif streak <= 5:
            return Decimal('80')  # Significant streak
        else:
            return Decimal('100')  # Critical streak

    @staticmethod
    def _compute_overtrading_score(features: FeatureSet) -> Decimal:
        """
        Compute overtrading component score (0-100).

        Uses the pre-computed overtrading score from features.
        This is already normalized 0-100 by the feature engineer.
        """
        return features.overtrading_score

    @staticmethod
    def _classify_risk_level(score: Decimal) -> str:
        """
        Classify risk score into severity levels.

        Thresholds are designed to provide actionable risk management:
        - STABLE: Normal monitoring
        - MONITOR: Enhanced oversight
        - HIGH_RISK: Active intervention
        - CRITICAL: Immediate action required
        """
        score_float = float(score)

        if score_float <= 30:
            return "STABLE"
        elif score_float <= 60:
            return "MONITOR"
        elif score_float <= 80:
            return "HIGH_RISK"
        else:
            return "CRITICAL"

    @staticmethod
    def explain_score(score: RiskScore) -> str:
        """
        Generate human-readable explanation of risk score.

        Useful for audit reports and risk committee presentations.
        """
        breakdown = score.breakdown

        explanation = f"""
Risk Score: {score.score}/100 ({score.level})

Score Composition:
- Volatility ({breakdown['components']['volatility']['weight']*100:.0f}%): {breakdown['components']['volatility']['contribution']:.1f} points
  {breakdown['components']['volatility']['explanation']}

- Drawdown Behavior ({breakdown['components']['drawdown']['weight']*100:.0f}%): {breakdown['components']['drawdown']['contribution']:.1f} points
  {breakdown['components']['drawdown']['explanation']}

- Trading Behavior ({breakdown['components']['behavior']['weight']*100:.0f}%): {breakdown['components']['behavior']['contribution']:.1f} points
  {breakdown['components']['behavior']['explanation']}

- Loss Streak ({breakdown['components']['loss_streak']['weight']*100:.0f}%): {breakdown['components']['loss_streak']['contribution']:.1f} points
  {breakdown['components']['loss_streak']['explanation']}

- Overtrading ({breakdown['components']['overtrading']['weight']*100:.0f}%): {breakdown['components']['overtrading']['contribution']:.1f} points
  {breakdown['components']['overtrading']['explanation']}

Analysis based on {breakdown['feature_summary']['total_trades']} trades over {breakdown['feature_summary']['analysis_period_hours']:.1f} hours.
Win rate: {breakdown['feature_summary']['win_rate']:.1f}%, Avg PnL: ${breakdown['feature_summary']['avg_trade_pnl']:.2f}
        """.strip()

        return explanation