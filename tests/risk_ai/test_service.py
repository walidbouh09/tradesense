"""
Unit Tests for Risk AI Service

Tests complete risk assessment workflow orchestration.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock

from app.domains.risk_ai.service import RiskAIService, RiskAssessment
from app.domains.risk_ai.features import TradeData


class TestRiskAIService:
    """Test Risk AI Service orchestration."""

    @pytest.fixture
    def service(self):
        """Create Risk AI Service instance."""
        return RiskAIService()

    @pytest.fixture
    def challenge_id(self):
        """Sample challenge ID."""
        return uuid4()

    @pytest.fixture
    def trader_id(self):
        """Sample trader ID."""
        return uuid4()

    @pytest.fixture
    def challenge_started_at(self):
        """Challenge start time."""
        return datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def sample_trades(self, challenge_started_at):
        """Sample trade data for testing."""
        return [
            {
                'trade_id': str(uuid4()),
                'symbol': 'EURUSD',
                'side': 'BUY',
                'quantity': '10000',
                'price': '1.0500',
                'realized_pnl': '50.00',
                'executed_at': challenge_started_at.replace(hour=9)
            },
            {
                'trade_id': str(uuid4()),
                'symbol': 'EURUSD',
                'side': 'SELL',
                'quantity': '10000',
                'price': '1.0520',
                'realized_pnl': '25.00',
                'executed_at': challenge_started_at.replace(hour=10)
            },
            {
                'trade_id': str(uuid4()),
                'symbol': 'GBPUSD',
                'side': 'BUY',
                'quantity': '5000',
                'price': '1.2500',
                'realized_pnl': '-15.00',
                'executed_at': challenge_started_at.replace(hour=11)
            }
        ]

    def test_complete_assessment_workflow(self, service, challenge_id, trader_id, sample_trades, challenge_started_at):
        """Test complete risk assessment workflow."""
        assessment = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=sample_trades,
            challenge_started_at=challenge_started_at
        )

        # Verify assessment structure
        assert isinstance(assessment, RiskAssessment)
        assert assessment.challenge_id == challenge_id
        assert assessment.trader_id == trader_id

        # Verify risk score is within bounds
        assert Decimal("0") <= assessment.risk_score.score <= Decimal("100")
        assert assessment.risk_score.level in ['STABLE', 'MONITOR', 'HIGH_RISK', 'CRITICAL']

        # Verify threshold classification
        assert assessment.threshold.level.value == assessment.risk_score.level

        # Verify features are computed
        assert assessment.features.total_trades == len(sample_trades)
        assert assessment.features.avg_trade_pnl == Decimal("20.00")  # (50+25-15)/3

        # Verify action plan is generated
        assert 'risk_level' in assessment.action_plan
        assert 'immediate_actions' in assessment.action_plan

    def test_empty_trades_assessment(self, service, challenge_id, trader_id, challenge_started_at):
        """Test assessment with no trades."""
        assessment = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=[],
            challenge_started_at=challenge_started_at
        )

        # Should still produce valid assessment
        assert isinstance(assessment, RiskAssessment)
        assert assessment.features.total_trades == 0
        assert assessment.risk_score.score == Decimal("0")  # Default to lowest risk
        assert assessment.risk_score.level == "STABLE"

    def test_invalid_input_validation(self, service):
        """Test input validation."""
        valid_challenge_id = uuid4()
        valid_trader_id = uuid4()
        valid_trades = []
        valid_started_at = datetime.utcnow().replace(tzinfo=None)

        # Test invalid challenge_id
        with pytest.raises(ValueError, match="challenge_id must be UUID"):
            service.validate_assessment_data(
                "invalid-uuid", valid_trader_id, valid_trades, valid_started_at
            )

        # Test invalid trader_id
        with pytest.raises(ValueError, match="trader_id must be UUID"):
            service.validate_assessment_data(
                valid_challenge_id, "invalid-uuid", valid_trades, valid_started_at
            )

        # Test invalid trades list
        with pytest.raises(ValueError, match="trades must be a list"):
            service.validate_assessment_data(
                valid_challenge_id, valid_trader_id, "not-a-list", valid_started_at
            )

        # Test invalid datetime
        with pytest.raises(ValueError, match="challenge_started_at must be datetime"):
            service.validate_assessment_data(
                valid_challenge_id, valid_trader_id, valid_trades, "not-a-datetime"
            )

        # Test future start date
        future_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="cannot be in the future"):
            service.validate_assessment_data(
                valid_challenge_id, valid_trader_id, valid_trades, future_date
            )

    def test_trade_data_conversion(self, service, sample_trades):
        """Test trade data conversion from dicts to TradeData objects."""
        trade_objects = service._convert_trade_data(sample_trades)

        assert len(trade_objects) == len(sample_trades)

        for i, trade_obj in enumerate(trade_objects):
            original = sample_trades[i]
            assert str(trade_obj.trade_id) == original['trade_id']
            assert trade_obj.symbol == original['symbol']
            assert trade_obj.side == original['side']
            assert str(trade_obj.quantity) == original['quantity']
            assert str(trade_obj.price) == original['price']
            assert str(trade_obj.realized_pnl) == original['realized_pnl']
            assert trade_obj.executed_at == original['executed_at']

    def test_invalid_trade_data_handling(self, service):
        """Test handling of invalid trade data."""
        invalid_trades = [
            {'missing_fields': 'incomplete'},  # Missing required fields
            {  # Invalid data types
                'trade_id': 'test-id',
                'symbol': 'EURUSD',
                'side': 'BUY',
                'quantity': 'not-a-number',
                'price': '1.05',
                'realized_pnl': '10.00',
                'executed_at': datetime.utcnow().replace(tzinfo=None)
            }
        ]

        # Should skip invalid trades and continue
        trade_objects = service._convert_trade_data(invalid_trades)
        assert len(trade_objects) == 0  # No valid trades

    def test_alert_thresholds(self, service):
        """Test alert threshold configuration."""
        thresholds = service.get_alert_thresholds()

        assert 'warning' in thresholds
        assert 'critical' in thresholds
        assert thresholds['warning'] == 60.0
        assert thresholds['critical'] == 80.0

    def test_should_emit_alert_logic(self, service):
        """Test alert emission logic."""
        # Below warning threshold
        assert service.should_emit_alert(50.0) is None

        # At warning threshold
        assert service.should_emit_alert(60.0) == 'warning'

        # Above warning, below critical
        assert service.should_emit_alert(70.0) == 'warning'

        # At critical threshold
        assert service.should_emit_alert(80.0) == 'critical'

        # Above critical
        assert service.should_emit_alert(90.0) == 'critical'

    def test_service_health_check(self, service):
        """Test service health status."""
        health = service.get_service_health()

        assert health['service'] == 'risk_ai'
        assert health['status'] == 'healthy'
        assert 'capabilities' in health
        assert 'timestamp' in health

        expected_capabilities = [
            'feature_engineering',
            'risk_scoring',
            'threshold_classification',
            'action_planning'
        ]
        assert health['capabilities'] == expected_capabilities

    def test_feature_importance(self, service):
        """Test feature importance weights."""
        importance = service.get_feature_importance()

        assert 'volatility' in importance
        assert 'drawdown' in importance
        assert 'behavior' in importance
        assert 'loss_streak' in importance
        assert 'overtrading' in importance

        # Weights should sum to 1.0
        total_weight = sum(importance.values())
        assert abs(total_weight - 1.0) < 0.001

    def test_assessment_serialization(self, service, challenge_id, trader_id, sample_trades, challenge_started_at):
        """Test assessment serialization."""
        assessment = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=sample_trades,
            challenge_started_at=challenge_started_at
        )

        assessment_dict = assessment.to_dict()

        # Check required top-level keys
        required_keys = [
            'challenge_id', 'trader_id', 'risk_score', 'threshold',
            'features', 'action_plan', 'assessed_at'
        ]
        for key in required_keys:
            assert key in assessment_dict

        # Check risk score structure
        risk_score = assessment_dict['risk_score']
        assert 'score' in risk_score
        assert 'level' in risk_score
        assert 'breakdown' in risk_score
        assert 'computed_at' in risk_score

        # Check features structure
        features = assessment_dict['features']
        assert 'total_trades' in features
        assert 'analysis_period_hours' in features
        assert 'avg_trade_pnl' in features
        assert 'win_rate' in features

    def test_deterministic_assessment(self, service, challenge_id, trader_id, sample_trades, challenge_started_at):
        """Test that assessments are deterministic."""
        assessment1 = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=sample_trades,
            challenge_started_at=challenge_started_at
        )

        assessment2 = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=sample_trades,
            challenge_started_at=challenge_started_at
        )

        # Should produce identical results
        assert assessment1.risk_score.score == assessment2.risk_score.score
        assert assessment1.risk_score.level == assessment2.risk_score.level
        assert assessment1.threshold.level == assessment2.threshold.level

    def test_error_handling_in_assessment(self, service, challenge_id, trader_id, challenge_started_at):
        """Test error handling in assessment workflow."""
        # Create trades that will cause conversion errors
        problematic_trades = [
            {'trade_id': None, 'symbol': None},  # Will cause conversion errors
        ]

        # Should not crash, should handle errors gracefully
        assessment = service.assess_challenge_risk(
            challenge_id=challenge_id,
            trader_id=trader_id,
            trades=problematic_trades,
            challenge_started_at=challenge_started_at
        )

        # Should still produce valid assessment (with empty/default features)
        assert isinstance(assessment, RiskAssessment)
        assert assessment.features.total_trades == 0  # No valid trades converted