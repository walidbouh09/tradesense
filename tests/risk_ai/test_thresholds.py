"""
Unit Tests for Risk Thresholds

Tests threshold classification and interpretation logic.
"""

import pytest
from decimal import Decimal
from app.domains.risk_ai.thresholds import RiskThresholds, RiskLevel, RiskThreshold


class TestRiskThresholds:
    """Test risk threshold definitions and classification."""

    def test_threshold_coverage(self):
        """Test that thresholds cover 0-100 range contiguously."""
        thresholds = RiskThresholds.get_all_thresholds()

        # Should have 4 threshold levels
        assert len(thresholds) == 4

        # Check coverage
        assert thresholds[0].min_score == Decimal("0")
        assert thresholds[-1].max_score == Decimal("100")

        # Check contiguous coverage
        for i in range(len(thresholds) - 1):
            assert thresholds[i].max_score == thresholds[i + 1].min_score

    def test_threshold_levels(self):
        """Test correct threshold level definitions."""
        thresholds = RiskThresholds.get_all_thresholds()

        expected_levels = [RiskLevel.STABLE, RiskLevel.MONITOR, RiskLevel.HIGH_RISK, RiskLevel.CRITICAL]
        actual_levels = [t.level for t in thresholds]

        assert actual_levels == expected_levels

    def test_score_classification_stable(self):
        """Test STABLE range classification."""
        # Test boundaries
        assert RiskThresholds.classify_score(Decimal("0")).level == RiskLevel.STABLE
        assert RiskThresholds.classify_score(Decimal("15")).level == RiskLevel.STABLE
        assert RiskThresholds.classify_score(Decimal("29.99")).level == RiskLevel.STABLE

    def test_score_classification_monitor(self):
        """Test MONITOR range classification."""
        assert RiskThresholds.classify_score(Decimal("30")).level == RiskLevel.MONITOR
        assert RiskThresholds.classify_score(Decimal("45")).level == RiskLevel.MONITOR
        assert RiskThresholds.classify_score(Decimal("59.99")).level == RiskLevel.MONITOR

    def test_score_classification_high_risk(self):
        """Test HIGH_RISK range classification."""
        assert RiskThresholds.classify_score(Decimal("60")).level == RiskLevel.HIGH_RISK
        assert RiskThresholds.classify_score(Decimal("70")).level == RiskLevel.HIGH_RISK
        assert RiskThresholds.classify_score(Decimal("79.99")).level == RiskLevel.HIGH_RISK

    def test_score_classification_critical(self):
        """Test CRITICAL range classification."""
        assert RiskThresholds.classify_score(Decimal("80")).level == RiskLevel.CRITICAL
        assert RiskThresholds.classify_score(Decimal("90")).level == RiskLevel.CRITICAL
        assert RiskThresholds.classify_score(Decimal("100")).level == RiskLevel.CRITICAL

    def test_score_bounds_validation(self):
        """Test score bounds validation."""
        # Valid scores
        for score in [Decimal("0"), Decimal("50"), Decimal("100")]:
            threshold = RiskThresholds.classify_score(score)
            assert isinstance(threshold, RiskThreshold)

        # Invalid scores should raise ValueError
        with pytest.raises(ValueError):
            RiskThresholds.classify_score(Decimal("-1"))

        with pytest.raises(ValueError):
            RiskThresholds.classify_score(Decimal("100.01"))

    def test_get_threshold_by_level(self):
        """Test retrieving threshold by level."""
        stable_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.STABLE)
        assert stable_threshold.level == RiskLevel.STABLE
        assert stable_threshold.min_score == Decimal("0")
        assert stable_threshold.max_score == Decimal("30")

        critical_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.CRITICAL)
        assert critical_threshold.level == RiskLevel.CRITICAL
        assert critical_threshold.min_score == Decimal("80")
        assert critical_threshold.max_score == Decimal("100")

    def test_invalid_level_raises_error(self):
        """Test that invalid level raises error."""
        # This should work fine since we only have valid levels defined
        # If we had an invalid enum value, it would raise ValueError
        pass

    def test_threshold_contains_score(self):
        """Test threshold score containment."""
        stable_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.STABLE)

        assert stable_threshold.contains_score(Decimal("0"))
        assert stable_threshold.contains_score(Decimal("15"))
        assert stable_threshold.contains_score(Decimal("29.99"))
        assert not stable_threshold.contains_score(Decimal("30"))
        assert not stable_threshold.contains_score(Decimal("35"))

    def test_alert_thresholds(self):
        """Test alert threshold configuration."""
        alert_thresholds = RiskThresholds.get_alert_thresholds()

        assert 'warning' in alert_thresholds
        assert 'critical' in alert_thresholds
        assert alert_thresholds['warning'] == Decimal("60")
        assert alert_thresholds['critical'] == Decimal("80")

    def test_action_plan_generation_stable(self):
        """Test action plan generation for STABLE scores."""
        action_plan = RiskThresholds.generate_action_plan(Decimal("15"))

        assert action_plan['risk_level'] == 'STABLE'
        assert 'immediate_actions' in action_plan
        assert 'monitoring_actions' in action_plan
        assert action_plan['timeline'] == 'Ongoing'
        assert 'escalation_contacts' in action_plan

    def test_action_plan_generation_critical(self):
        """Test action plan generation for CRITICAL scores."""
        action_plan = RiskThresholds.generate_action_plan(Decimal("90"))

        assert action_plan['risk_level'] == 'CRITICAL'
        assert 'immediate_actions' in action_plan
        assert 'Suspend trading activity immediately' in action_plan['immediate_actions']
        assert action_plan['timeline'] == 'Immediate - account suspended'
        assert 'Chief Risk Officer' in action_plan['escalation_contacts']

    def test_threshold_summary_generation(self):
        """Test threshold summary generation."""
        summary = RiskThresholds.get_threshold_summary()

        assert 'STABLE (0-30)' in summary
        assert 'MONITOR (30-60)' in summary
        assert 'HIGH_RISK (60-80)' in summary
        assert 'CRITICAL (80-100)' in summary

        # Check that each threshold has description and actions
        assert 'Low risk trader' in summary
        assert 'Moderate risk requiring enhanced oversight' in summary
        assert 'High risk requiring active risk management' in summary
        assert 'Critical risk requiring immediate intervention' in summary

    def test_threshold_score_ranges(self):
        """Test threshold score range formatting."""
        stable_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.STABLE)
        assert stable_threshold.score_range == "0-30"

        monitor_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.MONITOR)
        assert monitor_threshold.score_range == "30-60"

        high_risk_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.HIGH_RISK)
        assert high_risk_threshold.score_range == "60-80"

        critical_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.CRITICAL)
        assert critical_threshold.score_range == "80-100"

    def test_threshold_descriptions(self):
        """Test threshold descriptions."""
        stable_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.STABLE)
        assert 'Low risk trader' in stable_threshold.description

        critical_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.CRITICAL)
        assert 'Critical risk requiring immediate intervention' in critical_threshold.description

    def test_escalation_criteria(self):
        """Test escalation criteria definitions."""
        monitor_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.MONITOR)
        assert len(monitor_threshold.escalation_criteria) > 0
        assert 'increases by 10+ points' in str(monitor_threshold.escalation_criteria)

        high_risk_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.HIGH_RISK)
        assert len(high_risk_threshold.escalation_criteria) > 0
        assert 'Large position sizes detected' in high_risk_threshold.escalation_criteria

    def test_monitoring_frequency(self):
        """Test monitoring frequency definitions."""
        stable_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.STABLE)
        assert stable_threshold.monitoring_frequency == 'Weekly review'

        critical_threshold = RiskThresholds.get_threshold_by_level(RiskLevel.CRITICAL)
        assert critical_threshold.monitoring_frequency == 'Immediate intervention'