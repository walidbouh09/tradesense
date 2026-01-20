"""Rules engine application services."""

from typing import Dict, List, Optional
from uuid import UUID

from ...shared.events.event_bus import EventBus
from ..domain.entities import RuleEngine, RuleViolationTracker
from ..domain.services import RuleEngineIntegrationService, RuleViolationAnalyzer
from ..domain.value_objects import RuleEvaluationResult, RuleSeverity, RuleType


class RuleEvaluationService:
    """Application service for rule evaluation orchestration."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def evaluate_challenge_rules(
        self,
        challenge_id: UUID,
        rule_engine: RuleEngine,
        challenge_data: Dict[str, any],
    ) -> Dict[str, any]:
        """Evaluate challenge rules and handle results."""
        
        # Perform rule evaluation
        evaluation_results = RuleEngineIntegrationService.evaluate_challenge_rules(
            rule_engine=rule_engine,
            challenge_data=challenge_data,
        )
        
        # Publish domain events (already handled by RuleEngine entity)
        for event in rule_engine.domain_events:
            await self.event_bus.publish(event)
        rule_engine.clear_domain_events()
        
        return evaluation_results
    
    async def evaluate_real_time_rules(
        self,
        rule_engine: RuleEngine,
        context: Dict[str, any],
        rule_types: Optional[List[RuleType]] = None,
    ) -> List[RuleEvaluationResult]:
        """Evaluate specific rule types for real-time monitoring."""
        
        # Focus on critical rules for real-time evaluation
        if rule_types is None:
            rule_types = [
                RuleType.MAX_DAILY_DRAWDOWN,
                RuleType.MAX_TOTAL_DRAWDOWN,
                RuleType.MAX_POSITION_SIZE,
                RuleType.MAX_TRADES_PER_DAY,
            ]
        
        results = rule_engine.evaluate_rules(
            context=context,
            rule_types=rule_types,
            tags=["realtime", "critical"],
        )
        
        # Publish events
        for event in rule_engine.domain_events:
            await self.event_bus.publish(event)
        rule_engine.clear_domain_events()
        
        return results


class RuleViolationService:
    """Application service for managing rule violations."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def track_violations(
        self,
        entity_id: UUID,
        entity_type: str,
        violations: List[RuleEvaluationResult],
    ) -> RuleViolationTracker:
        """Track violations for an entity."""
        
        tracker = RuleViolationTracker(
            entity_id=entity_id,
            entity_type=entity_type,
        )
        
        for violation in violations:
            if violation.is_violation:
                tracker.record_violation(violation)
        
        # Publish events
        for event in tracker.domain_events:
            await self.event_bus.publish(event)
        tracker.clear_domain_events()
        
        return tracker
    
    async def analyze_violation_trends(
        self,
        violations: List[RuleEvaluationResult],
        time_window_hours: int = 24,
    ) -> Dict[str, any]:
        """Analyze violation trends and patterns."""
        
        analysis = RuleViolationAnalyzer.analyze_violation_patterns(
            violations=violations,
            time_window_hours=time_window_hours,
        )
        
        recommendations = RuleViolationAnalyzer.get_violation_recommendations(violations)
        
        return {
            "analysis": analysis,
            "recommendations": recommendations,
            "requires_immediate_action": any(
                v.severity == RuleSeverity.FATAL for v in violations
            ),
        }


class RiskEngineIntegrationService:
    """Service for integrating rules engine with risk management system."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def evaluate_risk_rules(
        self,
        rule_engine: RuleEngine,
        trading_context: Dict[str, any],
    ) -> Dict[str, any]:
        """Evaluate risk-related rules and return risk assessment."""
        
        # Focus on risk-related rule types
        risk_rule_types = [
            RuleType.MAX_DAILY_DRAWDOWN,
            RuleType.MAX_TOTAL_DRAWDOWN,
            RuleType.MAX_DAILY_LOSS,
            RuleType.MAX_TOTAL_LOSS,
            RuleType.MAX_POSITION_SIZE,
            RuleType.MAX_LEVERAGE,
        ]
        
        results = rule_engine.evaluate_rules(
            context=trading_context,
            rule_types=risk_rule_types,
            tags=["risk", "critical"],
        )
        
        # Analyze risk violations
        risk_violations = [r for r in results if r.is_violation]
        critical_violations = [r for r in risk_violations if r.is_critical]
        
        # Determine risk actions
        should_halt_trading = any(v.severity == RuleSeverity.FATAL for v in risk_violations)
        should_reduce_exposure = any(v.severity == RuleSeverity.CRITICAL for v in risk_violations)
        should_warn_trader = any(v.severity == RuleSeverity.VIOLATION for v in risk_violations)
        
        # Calculate risk score (0-100)
        risk_score = self._calculate_risk_score(risk_violations)
        
        # Publish events
        for event in rule_engine.domain_events:
            await self.event_bus.publish(event)
        rule_engine.clear_domain_events()
        
        return {
            "risk_assessment": {
                "risk_score": risk_score,
                "risk_level": self._get_risk_level(risk_score),
                "should_halt_trading": should_halt_trading,
                "should_reduce_exposure": should_reduce_exposure,
                "should_warn_trader": should_warn_trader,
            },
            "risk_violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity.value,
                    "message": v.message,
                    "impact": self._get_violation_impact(v),
                }
                for v in risk_violations
            ],
            "recommended_actions": self._get_risk_actions(risk_violations),
            "context_snapshot": trading_context,
        }
    
    def _calculate_risk_score(self, violations: List[RuleEvaluationResult]) -> int:
        """Calculate risk score based on violations."""
        if not violations:
            return 0
        
        score = 0
        severity_weights = {
            RuleSeverity.INFO: 1,
            RuleSeverity.WARNING: 5,
            RuleSeverity.VIOLATION: 15,
            RuleSeverity.CRITICAL: 35,
            RuleSeverity.FATAL: 50,
        }
        
        for violation in violations:
            score += severity_weights.get(violation.severity, 0)
        
        return min(score, 100)  # Cap at 100
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level description."""
        if risk_score >= 80:
            return "EXTREME"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "LOW"
        else:
            return "MINIMAL"
    
    def _get_violation_impact(self, violation: RuleEvaluationResult) -> str:
        """Get impact description for violation."""
        impact_map = {
            RuleSeverity.FATAL: "Challenge termination",
            RuleSeverity.CRITICAL: "Immediate risk management required",
            RuleSeverity.VIOLATION: "Trading restrictions may apply",
            RuleSeverity.WARNING: "Monitor closely",
            RuleSeverity.INFO: "Informational only",
        }
        return impact_map.get(violation.severity, "Unknown impact")
    
    def _get_risk_actions(self, violations: List[RuleEvaluationResult]) -> List[str]:
        """Get recommended risk management actions."""
        actions = []
        
        fatal_violations = [v for v in violations if v.severity == RuleSeverity.FATAL]
        critical_violations = [v for v in violations if v.severity == RuleSeverity.CRITICAL]
        
        if fatal_violations:
            actions.append("HALT ALL TRADING IMMEDIATELY")
            actions.append("Review challenge status")
            actions.append("Contact risk management team")
        
        elif critical_violations:
            actions.append("Reduce position sizes by 50%")
            actions.append("Implement stricter stop-loss orders")
            actions.append("Limit new position entries")
        
        elif violations:
            actions.append("Monitor positions closely")
            actions.append("Consider reducing exposure")
            actions.append("Review trading strategy")
        
        return actions