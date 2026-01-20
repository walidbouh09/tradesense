"""
Risk Thresholds and Interpretation Logic

Defines risk level classifications and provides actionable guidance
for each threshold. Designed for regulatory compliance and operational clarity.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Any
from enum import Enum


class RiskLevel(Enum):
    """Risk severity levels for trader classification."""
    STABLE = "STABLE"
    MONITOR = "MONITOR"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"


@dataclass
class RiskThreshold:
    """Definition of a risk threshold with bounds and guidance."""
    level: RiskLevel
    min_score: Decimal
    max_score: Decimal
    description: str
    action_required: str
    monitoring_frequency: str
    escalation_criteria: List[str]

    @property
    def score_range(self) -> str:
        """Human-readable score range."""
        return f"{self.min_score}-{self.max_score}"

    def contains_score(self, score: Decimal) -> bool:
        """Check if a score falls within this threshold."""
        return self.min_score <= score <= self.max_score


class RiskThresholds:
    """
    Risk Threshold Definitions and Interpretation Logic.

    Provides structured risk assessment framework with clear boundaries
    and actionable guidance for each risk level.
    """

    # Define threshold boundaries (must be contiguous and cover 0-100)
    THRESHOLDS = [
        RiskThreshold(
            level=RiskLevel.STABLE,
            min_score=Decimal('0'),
            max_score=Decimal('30'),
            description="Low risk trader with consistent, profitable performance",
            action_required="Standard monitoring - no intervention needed",
            monitoring_frequency="Weekly review",
            escalation_criteria=[]
        ),

        RiskThreshold(
            level=RiskLevel.MONITOR,
            min_score=Decimal('30'),
            max_score=Decimal('60'),
            description="Moderate risk requiring enhanced oversight",
            action_required="Increased monitoring frequency and trend analysis",
            monitoring_frequency="Daily review",
            escalation_criteria=[
                "Risk score increases by 10+ points in 24 hours",
                "Multiple consecutive losing days",
                "Significant increase in trading frequency"
            ]
        ),

        RiskThreshold(
            level=RiskLevel.HIGH_RISK,
            min_score=Decimal('60'),
            max_score=Decimal('80'),
            description="High risk trader requiring active risk management",
            action_required="Immediate risk mitigation and position limits consideration",
            monitoring_frequency="Real-time monitoring",
            escalation_criteria=[
                "Risk score reaches 75+ points",
                "Large position sizes detected",
                "Extended losing streaks (>5 consecutive losses)",
                "Significant drawdown events"
            ]
        ),

        RiskThreshold(
            level=RiskLevel.CRITICAL,
            min_score=Decimal('80'),
            max_score=Decimal('100'),
            description="Critical risk requiring immediate intervention",
            action_required="Immediate account suspension and manual review required",
            monitoring_frequency="Immediate intervention",
            escalation_criteria=[
                "Any score reaching 90+ points",
                "Extreme drawdown events (>50% intraday)",
                "Evidence of revenge trading patterns",
                "System-detected manipulation attempts"
            ]
        )
    ]

    @staticmethod
    def classify_score(score: Decimal) -> RiskThreshold:
        """
        Classify a risk score into the appropriate threshold.

        Args:
            score: Risk score between 0-100

        Returns:
            RiskThreshold containing the score

        Raises:
            ValueError: If score is outside 0-100 range
        """
        if not (Decimal('0') <= score <= Decimal('100')):
            raise ValueError(f"Risk score must be between 0-100, got {score}")

        for threshold in RiskThresholds.THRESHOLDS:
            if threshold.contains_score(score):
                return threshold

        # This should never happen if thresholds are properly defined
        raise ValueError(f"No threshold found for score {score}")

    @staticmethod
    def get_all_thresholds() -> List[RiskThreshold]:
        """Get all defined risk thresholds."""
        return RiskThresholds.THRESHOLDS.copy()

    @staticmethod
    def get_threshold_by_level(level: RiskLevel) -> RiskThreshold:
        """Get threshold definition for a specific risk level."""
        for threshold in RiskThresholds.THRESHOLDS:
            if threshold.level == level:
                return threshold
        raise ValueError(f"No threshold defined for level {level}")

    @staticmethod
    def get_alert_thresholds() -> Dict[str, Decimal]:
        """
        Get score thresholds that trigger alerts.

        Returns:
            Dictionary mapping alert types to score thresholds
        """
        return {
            'warning': Decimal('60'),   # HIGH_RISK threshold
            'critical': Decimal('80'),  # CRITICAL threshold
        }

    @staticmethod
    def generate_action_plan(score: Decimal) -> Dict[str, Any]:
        """
        Generate actionable risk management plan based on score.

        Args:
            score: Current risk score

        Returns:
            Dictionary with recommended actions and timeline
        """
        threshold = RiskThresholds.classify_score(score)

        action_plan = {
            'risk_level': threshold.level.value,
            'immediate_actions': [],
            'monitoring_actions': [],
            'timeline': 'Immediate',
            'escalation_contacts': []
        }

        # Define actions based on risk level
        if threshold.level == RiskLevel.STABLE:
            action_plan.update({
                'immediate_actions': ['Continue standard monitoring'],
                'monitoring_actions': ['Weekly performance review'],
                'timeline': 'Ongoing'
            })

        elif threshold.level == RiskLevel.MONITOR:
            action_plan.update({
                'immediate_actions': [
                    'Increase monitoring frequency',
                    'Review recent trading patterns'
                ],
                'monitoring_actions': [
                    'Daily risk score checks',
                    'Weekly strategy review with trader'
                ],
                'timeline': 'Next 24-48 hours',
                'escalation_contacts': ['Risk Analyst']
            })

        elif threshold.level == RiskLevel.HIGH_RISK:
            action_plan.update({
                'immediate_actions': [
                    'Implement position size limits',
                    'Require pre-trade approval for large positions',
                    'Schedule urgent strategy review'
                ],
                'monitoring_actions': [
                    'Real-time position monitoring',
                    'Daily risk committee review',
                    'Enhanced drawdown monitoring'
                ],
                'timeline': 'Immediate - within 1 hour',
                'escalation_contacts': ['Risk Manager', 'Trading Supervisor']
            })

        elif threshold.level == RiskLevel.CRITICAL:
            action_plan.update({
                'immediate_actions': [
                    'Suspend trading activity immediately',
                    'Freeze account pending review',
                    'Initiate formal risk incident process'
                ],
                'monitoring_actions': [
                    'Complete account audit',
                    'Review all recent trades',
                    'Assess capital adequacy'
                ],
                'timeline': 'Immediate - account suspended',
                'escalation_contacts': ['Chief Risk Officer', 'Compliance Team', 'Legal']
            })

        return action_plan

    @staticmethod
    def validate_thresholds() -> bool:
        """
        Validate that thresholds are properly defined.

        Checks for:
        - Contiguous coverage of 0-100 range
        - No overlapping thresholds
        - Proper boundary conditions

        Returns:
            True if thresholds are valid
        """
        thresholds = sorted(RiskThresholds.THRESHOLDS, key=lambda t: t.min_score)

        # Check coverage starts at 0
        if thresholds[0].min_score != Decimal('0'):
            return False

        # Check coverage ends at 100
        if thresholds[-1].max_score != Decimal('100'):
            return False

        # Check contiguous coverage
        for i in range(len(thresholds) - 1):
            if thresholds[i].max_score != thresholds[i + 1].min_score:
                return False

        return True

    @staticmethod
    def get_threshold_summary() -> str:
        """
        Generate human-readable summary of all thresholds.

        Useful for documentation and regulatory reporting.
        """
        summary = "Risk Threshold Definitions:\n\n"

        for threshold in RiskThresholds.THRESHOLDS:
            summary += f"{threshold.level.value} ({threshold.score_range}):\n"
            summary += f"  Description: {threshold.description}\n"
            summary += f"  Action Required: {threshold.action_required}\n"
            summary += f"  Monitoring: {threshold.monitoring_frequency}\n"

            if threshold.escalation_criteria:
                summary += f"  Escalation Triggers:\n"
                for criterion in threshold.escalation_criteria:
                    summary += f"    - {criterion}\n"

            summary += "\n"

        return summary.strip()


# Validate thresholds on module import
if not RiskThresholds.validate_thresholds():
    raise ValueError("Risk thresholds are improperly defined - must cover 0-100 contiguously")

# Export commonly used functions
__all__ = ['RiskThresholds', 'RiskLevel', 'RiskThreshold']