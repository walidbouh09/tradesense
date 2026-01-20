"""
Risk AI Service - Orchestrates Complete Risk Assessment Workflow

Provides clean API for risk assessment while coordinating all components:
- Trade data loading
- Feature engineering
- Risk scoring
- Threshold classification

Stateless service designed for async worker integration.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from .features import FeatureEngineer, TradeData, FeatureSet
from .scorer import RiskScorer, RiskScore
from .thresholds import RiskThresholds, RiskThreshold


@dataclass
class RiskAssessment:
    """Complete risk assessment result."""
    challenge_id: UUID
    trader_id: UUID
    risk_score: RiskScore
    threshold: RiskThreshold
    features: FeatureSet
    action_plan: Dict[str, Any]
    assessed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'challenge_id': str(self.challenge_id),
            'trader_id': str(self.trader_id),
            'risk_score': self.risk_score.to_dict(),
            'threshold': {
                'level': self.threshold.level.value,
                'score_range': self.threshold.score_range,
                'description': self.threshold.description,
                'action_required': self.threshold.action_required
            },
            'features': {
                'total_trades': self.features.total_trades,
                'analysis_period_hours': float(self.features.analysis_period_hours),
                'avg_trade_pnl': float(self.features.avg_trade_pnl),
                'win_rate': float(self.features.win_rate),
                'pnl_volatility': float(self.features.pnl_volatility),
                'max_intraday_drawdown': float(self.features.max_intraday_drawdown),
                'loss_streak': self.features.loss_streak,
                'trades_per_hour': float(self.features.trades_per_hour),
                'overtrading_score': float(self.features.overtrading_score),
                'revenge_trading_score': float(self.features.revenge_trading_score)
            },
            'action_plan': self.action_plan,
            'assessed_at': self.assessed_at.isoformat()
        }


class RiskAIService:
    """
    Risk AI Service - Complete Risk Assessment Orchestration.

    Coordinates the entire risk assessment workflow:
    1. Load and validate trade data
    2. Engineer risk features
    3. Compute risk score
    4. Classify risk level
    5. Generate action plan

    Designed for background worker integration with proper error handling.
    """

    def __init__(self):
        """Initialize service with component dependencies."""
        self.feature_engineer = FeatureEngineer()
        self.risk_scorer = RiskScorer()
        self.threshold_manager = RiskThresholds()

    def assess_challenge_risk(
        self,
        challenge_id: UUID,
        trader_id: UUID,
        trades: List[Dict[str, Any]],
        challenge_started_at: datetime
    ) -> RiskAssessment:
        """
        Perform complete risk assessment for a challenge.

        Args:
            challenge_id: UUID of the challenge being assessed
            trader_id: UUID of the trader
            trades: List of trade dictionaries from database
            challenge_started_at: When the challenge began

        Returns:
            RiskAssessment with complete analysis

        Raises:
            ValueError: If input data is invalid
        """
        try:
            # Step 1: Convert and validate trade data
            trade_data = self._convert_trade_data(trades)

            # Step 2: Engineer features from trade data
            features = self.feature_engineer.compute_features(trade_data, challenge_started_at)

            # Step 3: Compute risk score from features
            risk_score = self.risk_scorer.compute_score(features)

            # Step 4: Classify into risk threshold
            threshold = self.threshold_manager.classify_score(risk_score.score)

            # Step 5: Generate action plan
            action_plan = self.threshold_manager.generate_action_plan(risk_score.score)

            # Step 6: Create complete assessment
            assessment = RiskAssessment(
                challenge_id=challenge_id,
                trader_id=trader_id,
                risk_score=risk_score,
                threshold=threshold,
                features=features,
                action_plan=action_plan,
                assessed_at=datetime.utcnow().replace(tzinfo=None)
            )

            return assessment

        except Exception as e:
            # Log error but don't expose internal details
            print(f"Risk assessment failed for challenge {challenge_id}: {e}")
            raise ValueError(f"Risk assessment computation failed: {str(e)}")

    def _convert_trade_data(self, trades: List[Dict[str, Any]]) -> List[TradeData]:
        """
        Convert database trade records to domain objects.

        Validates required fields and converts data types.
        """
        converted_trades = []

        for trade_dict in trades:
            try:
                trade = TradeData(
                    trade_id=str(trade_dict['trade_id']),
                    symbol=str(trade_dict['symbol']),
                    side=str(trade_dict['side']),
                    quantity=Decimal(str(trade_dict['quantity'])),
                    price=Decimal(str(trade_dict['price'])),
                    realized_pnl=Decimal(str(trade_dict['realized_pnl'])),
                    executed_at=trade_dict['executed_at']  # Already datetime
                )
                converted_trades.append(trade)
            except (KeyError, ValueError, TypeError) as e:
                # Skip invalid trade records but log the issue
                print(f"Skipping invalid trade record: {e}")
                continue

        return converted_trades

    def get_alert_thresholds(self) -> Dict[str, float]:
        """
        Get score thresholds that trigger alerts.

        Returns:
            Dictionary mapping alert levels to score thresholds
        """
        thresholds = self.threshold_manager.get_alert_thresholds()
        return {k: float(v) for k, v in thresholds.items()}

    def should_emit_alert(self, risk_score: float) -> Optional[str]:
        """
        Determine if risk score should trigger an alert.

        Args:
            risk_score: Current risk score (0-100)

        Returns:
            Alert type ('warning' or 'critical') or None
        """
        from decimal import Decimal

        thresholds = self.get_alert_thresholds()

        if risk_score >= thresholds['critical']:
            return 'critical'
        elif risk_score >= thresholds['warning']:
            return 'warning'

        return None

    def validate_assessment_data(
        self,
        challenge_id: UUID,
        trader_id: UUID,
        trades: List[Dict[str, Any]],
        challenge_started_at: datetime
    ) -> None:
        """
        Validate input data before processing.

        Args:
            challenge_id: Challenge identifier
            trader_id: Trader identifier
            trades: Trade data list
            challenge_started_at: Challenge start time

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(challenge_id, UUID):
            raise ValueError("challenge_id must be UUID")

        if not isinstance(trader_id, UUID):
            raise ValueError("trader_id must be UUID")

        if not isinstance(trades, list):
            raise ValueError("trades must be a list")

        if not isinstance(challenge_started_at, datetime):
            raise ValueError("challenge_started_at must be datetime")

        if challenge_started_at > datetime.utcnow().replace(tzinfo=None):
            raise ValueError("challenge_started_at cannot be in the future")

        # Check that all trades have required fields
        required_fields = ['trade_id', 'symbol', 'side', 'quantity', 'price', 'realized_pnl', 'executed_at']
        for i, trade in enumerate(trades):
            missing_fields = [field for field in required_fields if field not in trade]
            if missing_fields:
                raise ValueError(f"Trade {i} missing required fields: {missing_fields}")

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get service health status for monitoring.

        Returns:
            Dictionary with health metrics
        """
        return {
            'service': 'risk_ai',
            'status': 'healthy',
            'timestamp': datetime.utcnow().replace(tzinfo=None).isoformat(),
            'capabilities': [
                'feature_engineering',
                'risk_scoring',
                'threshold_classification',
                'action_planning'
            ]
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get relative importance of each feature in scoring.

        Useful for model interpretability and regulatory reporting.
        """
        # Return the weights from the scorer
        from .scorer import RiskScorer
        return {k: float(v) for k, v in RiskScorer.WEIGHTS.items()}