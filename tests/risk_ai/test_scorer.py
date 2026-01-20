"""
Unit Tests for Risk Scorer

Tests deterministic risk score computation from features.
All tests verify score bounds, component calculations, and explainability.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.domains.risk_ai.scorer import RiskScorer
from app.domains.risk_ai.features import FeatureSet


class TestRiskScorer:
    """Test risk score computation and explainability."""

    @pytest.fixture
    def stable_trader_features(self):
        """Features for a stable, low-risk trader."""
        return FeatureSet(
            avg_trade_pnl=Decimal("25.00"),
            pnl_volatility=Decimal("15.00"),
            win_rate=Decimal("65.00"),
            profit_factor=Decimal("1.50"),
            max_intraday_drawdown=Decimal("2.00"),
            drawdown_speed=Decimal("5.00"),
            loss_streak=0,
            trades_per_hour=Decimal("2.00"),
            overtrading_score=Decimal("10.00"),
            revenge_trading_score=Decimal("0.00"),
            total_trades=20,
            analysis_period_hours=Decimal("10.00"),
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    @pytest.fixture
    def volatile_trader_features(self):
        """Features for a volatile, high-risk trader."""
        return FeatureSet(
            avg_trade_pnl=Decimal("-10.00"),
            pnl_volatility=Decimal("200.00"),
            win_rate=Decimal("45.00"),
            profit_factor=Decimal("0.80"),
            max_intraday_drawdown=Decimal("15.00"),
            drawdown_speed=Decimal("50.00"),
            loss_streak=3,
            trades_per_hour=Decimal("8.00"),
            overtrading_score=Decimal("75.00"),
            revenge_trading_score=Decimal("60.00"),
            total_trades=40,
            analysis_period_hours=Decimal("5.00"),
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    @pytest.fixture
    def critical_trader_features(self):
        """Features for a critical risk trader."""
        return FeatureSet(
            avg_trade_pnl=Decimal("-50.00"),
            pnl_volatility=Decimal("500.00"),
            win_rate=Decimal("20.00"),
            profit_factor=Decimal("0.30"),
            max_intraday_drawdown=Decimal("40.00"),
            drawdown_speed=Decimal("150.00"),
            loss_streak=8,
            trades_per_hour=Decimal("15.00"),
            overtrading_score=Decimal("95.00"),
            revenge_trading_score=Decimal("85.00"),
            total_trades=60,
            analysis_period_hours=Decimal("4.00"),
            computed_at=datetime.utcnow().replace(tzinfo=None)
        )

    def test_stable_trader_score(self, stable_trader_features):
        """Test scoring for stable trader."""
        score = RiskScorer.compute_score(stable_trader_features)

        # Should be in STABLE range (0-30)
        assert Decimal("0") <= score.score <= Decimal("30")
        assert score.level == "STABLE"

        # Verify breakdown structure
        assert 'components' in score.breakdown
        assert 'total_score' in score.breakdown
        assert 'feature_summary' in score.breakdown

        # Check that all components are present
        components = score.breakdown['components']
        required_components = ['volatility', 'drawdown', 'behavior', 'loss_streak', 'overtrading']
        for component in required_components:
            assert component in components
            assert 'raw_score' in components[component]
            assert 'weight' in components[component]
            assert 'contribution' in components[component]

    def test_volatile_trader_score(self, volatile_trader_features):
        """Test scoring for volatile trader."""
        score = RiskScorer.compute_score(volatile_trader_features)

        # Should be in HIGH_RISK range (60-80)
        assert Decimal("60") <= score.score <= Decimal("80")
        assert score.level == "HIGH_RISK"

    def test_critical_trader_score(self, critical_trader_features):
        """Test scoring for critical risk trader."""
        score = RiskScorer.compute_score(critical_trader_features)

        # Should be in CRITICAL range (80-100)
        assert Decimal("80") <= score.score <= Decimal("100")
        assert score.level == "CRITICAL"

    def test_score_bounds(self, stable_trader_features, volatile_trader_features, critical_trader_features):
        """Test that all scores are within valid bounds."""
        scores = [
            RiskScorer.compute_score(stable_trader_features),
            RiskScorer.compute_score(volatile_trader_features),
            RiskScorer.compute_score(critical_trader_features)
        ]

        for score in scores:
            assert Decimal("0") <= score.score <= Decimal("100")
            assert score.level in ["STABLE", "MONITOR", "HIGH_RISK", "CRITICAL"]

    def test_component_weights_sum_to_100(self):
        """Test that component weights sum to 100%."""
        total_weight = sum(RiskScorer.WEIGHTS.values())
        assert total_weight == Decimal("1.0")

    def test_volatility_score_calculation(self):
        """Test volatility component score calculation."""
        # Low volatility
        low_vol_features = FeatureSet(
            avg_trade_pnl=Decimal("10"), pnl_volatility=Decimal("5"), win_rate=Decimal("50"),
            profit_factor=Decimal("1"), max_intraday_drawdown=Decimal("1"), drawdown_speed=Decimal("1"),
            loss_streak=0, trades_per_hour=Decimal("1"), overtrading_score=Decimal("0"), revenge_trading_score=Decimal("0"),
            total_trades=10, analysis_period_hours=Decimal("1"), computed_at=datetime.utcnow().replace(tzinfo=None)
        )

        # High volatility
        high_vol_features = FeatureSet(
            avg_trade_pnl=Decimal("10"), pnl_volatility=Decimal("200"), win_rate=Decimal("50"),
            profit_factor=Decimal("1"), max_intraday_drawdown=Decimal("1"), drawdown_speed=Decimal("1"),
            loss_streak=0, trades_per_hour=Decimal("1"), overtrading_score=Decimal("0"), revenge_trading_score=Decimal("0"),
            total_trades=10, analysis_period_hours=Decimal("1"), computed_at=datetime.utcnow().replace(tzinfo=None)
        )

        low_vol_score = RiskScorer.compute_score(low_vol_features)
        high_vol_score = RiskScorer.compute_score(high_vol_features)

        # High volatility should contribute more to risk score
        low_vol_contribution = low_vol_score.breakdown['components']['volatility']['contribution']
        high_vol_contribution = high_vol_score.breakdown['components']['volatility']['contribution']

        assert high_vol_contribution > low_vol_contribution

    def test_loss_streak_score_calculation(self):
        """Test loss streak component score calculation."""
        # No loss streak
        no_streak_features = FeatureSet(
            avg_trade_pnl=Decimal("10"), pnl_volatility=Decimal("10"), win_rate=Decimal("50"),
            profit_factor=Decimal("1"), max_intraday_drawdown=Decimal("1"), drawdown_speed=Decimal("1"),
            loss_streak=0, trades_per_hour=Decimal("1"), overtrading_score=Decimal("0"), revenge_trading_score=Decimal("0"),
            total_trades=10, analysis_period_hours=Decimal("1"), computed_at=datetime.utcnow().replace(tzinfo=None)
        )

        # Long loss streak
        long_streak_features = no_streak_features._replace(loss_streak=5)

        no_streak_score = RiskScorer.compute_score(no_streak_features)
        long_streak_score = RiskScorer.compute_score(long_streak_features)

        # Long loss streak should contribute more to risk score
        no_streak_contribution = no_streak_score.breakdown['components']['loss_streak']['contribution']
        long_streak_contribution = long_streak_score.breakdown['components']['loss_streak']['contribution']

        assert long_streak_contribution > no_streak_contribution

    def test_overtrading_score_calculation(self):
        """Test overtrading component score calculation."""
        # Normal trading
        normal_features = FeatureSet(
            avg_trade_pnl=Decimal("10"), pnl_volatility=Decimal("10"), win_rate=Decimal("70"),
            profit_factor=Decimal("1"), max_intraday_drawdown=Decimal("1"), drawdown_speed=Decimal("1"),
            loss_streak=0, trades_per_hour=Decimal("2"), overtrading_score=Decimal("20"), revenge_trading_score=Decimal("0"),
            total_trades=10, analysis_period_hours=Decimal("5"), computed_at=datetime.utcnow().replace(tzinfo=None)
        )

        # Overtrading
        overtrading_features = normal_features._replace(
            trades_per_hour=Decimal("10"),
            overtrading_score=Decimal("80"),
            win_rate=Decimal("40")  # Lower win rate
        )

        normal_score = RiskScorer.compute_score(normal_features)
        overtrading_score = RiskScorer.compute_score(overtrading_features)

        # Overtrading should contribute more to risk score
        normal_contribution = normal_score.breakdown['components']['overtrading']['contribution']
        overtrading_contribution = overtrading_score.breakdown['components']['overtrading']['contribution']

        assert overtrading_contribution > normal_contribution

    def test_score_explainability(self, stable_trader_features):
        """Test that scores are fully explainable."""
        score = RiskScorer.compute_score(stable_trader_features)

        # Should be able to explain the score
        explanation = RiskScorer.explain_score(score)

        # Explanation should contain key information
        assert str(float(score.score)) in explanation
        assert score.level in explanation
        assert "Score Composition:" in explanation
        assert "Analysis based on" in explanation

    def test_deterministic_scoring(self, stable_trader_features):
        """Test that scoring is deterministic."""
        score1 = RiskScorer.compute_score(stable_trader_features)
        score2 = RiskScorer.compute_score(stable_trader_features)

        assert score1.score == score2.score
        assert score1.level == score2.level
        assert score1.breakdown == score2.breakdown

    def test_score_serialization(self, stable_trader_features):
        """Test score serialization for storage/transmission."""
        score = RiskScorer.compute_score(stable_trader_features)

        # Should be serializable to dict
        score_dict = score.to_dict()

        required_keys = ['score', 'level', 'breakdown', 'computed_at']
        for key in required_keys:
            assert key in score_dict

        # Score should be float
        assert isinstance(score_dict['score'], float)
        assert 0 <= score_dict['score'] <= 100

        # Level should be string
        assert isinstance(score_dict['level'], str)
        assert score_dict['level'] in ['STABLE', 'MONITOR', 'HIGH_RISK', 'CRITICAL']

    def test_weighted_score_calculation(self, stable_trader_features):
        """Test that component scores are properly weighted."""
        score = RiskScorer.compute_score(stable_trader_features)

        total_contribution = sum(
            component['contribution']
            for component in score.breakdown['components'].values()
        )

        # Total contribution should equal the final score
        assert abs(float(total_contribution) - float(score.score)) < 0.01

    def test_component_score_bounds(self, stable_trader_features, volatile_trader_features):
        """Test that individual component scores are within bounds."""
        scores = [
            RiskScorer.compute_score(stable_trader_features),
            RiskScorer.compute_score(volatile_trader_features)
        ]

        for score in scores:
            for component_name, component_data in score.breakdown['components'].items():
                raw_score = component_data['raw_score']
                assert Decimal("0") <= raw_score <= Decimal("100"), f"{component_name} raw score out of bounds"

                contribution = component_data['contribution']
                assert contribution >= Decimal("0"), f"{component_name} contribution negative"