"""Rules engine domain entities."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from .events import (
    RuleEvaluated,
    RuleSetActivated,
    RuleSetCreated,
    RuleSetDeactivated,
    RuleViolationDetected,
    RuleViolationResolved,
)
from .value_objects import (
    RuleDefinition,
    RuleEvaluationResult,
    RuleSet,
    RuleSeverity,
    RuleType,
)


class RuleEngine(AggregateRoot):
    """Rule engine aggregate managing rule evaluation and violations."""
    
    def __init__(
        self,
        name: str,
        description: str,
        rule_sets: Optional[List[RuleSet]] = None,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        if not name or not name.strip():
            raise ValidationError("Rule engine name cannot be empty")
        
        self._name = name.strip()
        self._description = description.strip()
        self._rule_sets: List[RuleSet] = rule_sets or []
        self._active_rule_set_name: Optional[str] = None
        self._evaluation_history: List[RuleEvaluationResult] = []
        self._active_violations: Dict[str, RuleEvaluationResult] = {}
        self._evaluation_count = 0
        self._last_evaluation_at: Optional[datetime] = None
    
    def add_rule_set(self, rule_set: RuleSet) -> None:
        """Add a rule set to the engine."""
        # Check for duplicate names
        existing_names = [rs.name for rs in self._rule_sets]
        if rule_set.name in existing_names:
            raise BusinessRuleViolationError(f"Rule set '{rule_set.name}' already exists")
        
        self._rule_sets.append(rule_set)
        self._touch()
        
        # Emit event
        self.add_domain_event(
            RuleSetCreated(
                aggregate_id=self.id,
                rule_set_name=rule_set.name,
                rule_count=len(rule_set.rules),
                version=rule_set.version,
            )
        )
    
    def activate_rule_set(self, rule_set_name: str) -> None:
        """Activate a specific rule set."""
        # Verify rule set exists
        rule_set = self._get_rule_set_by_name(rule_set_name)
        if not rule_set:
            raise BusinessRuleViolationError(f"Rule set '{rule_set_name}' not found")
        
        old_active = self._active_rule_set_name
        self._active_rule_set_name = rule_set_name
        self._touch()
        
        # Clear active violations when switching rule sets
        self._active_violations.clear()
        
        # Emit event
        self.add_domain_event(
            RuleSetActivated(
                aggregate_id=self.id,
                rule_set_name=rule_set_name,
                previous_rule_set=old_active,
                rule_count=len(rule_set.rules),
            )
        )
    
    def deactivate_rule_set(self) -> None:
        """Deactivate current rule set."""
        if not self._active_rule_set_name:
            return
        
        old_active = self._active_rule_set_name
        self._active_rule_set_name = None
        self._active_violations.clear()
        self._touch()
        
        # Emit event
        self.add_domain_event(
            RuleSetDeactivated(
                aggregate_id=self.id,
                rule_set_name=old_active,
            )
        )
    
    def evaluate_rules(
        self,
        context: Dict[str, any],
        rule_types: Optional[List[RuleType]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[RuleEvaluationResult]:
        """Evaluate rules against provided context."""
        if not self._active_rule_set_name:
            raise BusinessRuleViolationError("No active rule set")
        
        active_rule_set = self._get_rule_set_by_name(self._active_rule_set_name)
        if not active_rule_set:
            raise BusinessRuleViolationError("Active rule set not found")
        
        # Filter rules based on criteria
        rules_to_evaluate = active_rule_set.get_enabled_rules()
        
        if rule_types:
            rules_to_evaluate = [
                rule for rule in rules_to_evaluate 
                if rule.rule_type in rule_types
            ]
        
        if tags:
            rules_to_evaluate = [
                rule for rule in rules_to_evaluate
                if any(tag in rule.tags for tag in tags)
            ]
        
        # Evaluate each rule
        results = []
        evaluation_timestamp = datetime.utcnow().isoformat()
        
        for rule in rules_to_evaluate:
            result = self._evaluate_single_rule(rule, context, evaluation_timestamp)
            results.append(result)
            
            # Update evaluation history
            self._evaluation_history.append(result)
            
            # Manage active violations
            if result.is_violation:
                self._active_violations[result.rule_id] = result
                
                # Emit violation event
                self.add_domain_event(
                    RuleViolationDetected(
                        aggregate_id=self.id,
                        rule_id=result.rule_id,
                        rule_name=result.rule_name,
                        severity=result.severity.value,
                        message=result.message,
                        details=result.details,
                        context_snapshot=result.context_snapshot,
                    )
                )
            else:
                # Check if this resolves a previous violation
                if result.rule_id in self._active_violations:
                    del self._active_violations[result.rule_id]
                    
                    # Emit resolution event
                    self.add_domain_event(
                        RuleViolationResolved(
                            aggregate_id=self.id,
                            rule_id=result.rule_id,
                            rule_name=result.rule_name,
                            resolution_message=f"Rule {result.rule_name} now passes",
                        )
                    )
            
            # Emit evaluation event
            self.add_domain_event(
                RuleEvaluated(
                    aggregate_id=self.id,
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    passed=result.passed,
                    severity=result.severity.value,
                    message=result.message,
                )
            )
        
        # Update evaluation statistics
        self._evaluation_count += 1
        self._last_evaluation_at = datetime.utcnow()
        self._touch()
        
        # Limit history size
        if len(self._evaluation_history) > 1000:
            self._evaluation_history = self._evaluation_history[-500:]
        
        return results
    
    def get_active_violations(
        self,
        severity_filter: Optional[RuleSeverity] = None,
    ) -> List[RuleEvaluationResult]:
        """Get current active violations."""
        violations = list(self._active_violations.values())
        
        if severity_filter:
            violations = [v for v in violations if v.severity == severity_filter]
        
        return violations
    
    def get_critical_violations(self) -> List[RuleEvaluationResult]:
        """Get critical and fatal violations."""
        return [
            v for v in self._active_violations.values()
            if v.severity in [RuleSeverity.CRITICAL, RuleSeverity.FATAL]
        ]
    
    def has_fatal_violations(self) -> bool:
        """Check if there are any fatal violations."""
        return any(
            v.severity == RuleSeverity.FATAL 
            for v in self._active_violations.values()
        )
    
    def get_evaluation_summary(self) -> Dict[str, any]:
        """Get evaluation summary statistics."""
        if not self._evaluation_history:
            return {
                "total_evaluations": 0,
                "violations": 0,
                "critical_violations": 0,
                "fatal_violations": 0,
                "last_evaluation": None,
            }
        
        recent_results = self._evaluation_history[-100:]  # Last 100 evaluations
        
        violations = [r for r in recent_results if r.is_violation]
        critical_violations = [r for r in violations if r.severity == RuleSeverity.CRITICAL]
        fatal_violations = [r for r in violations if r.severity == RuleSeverity.FATAL]
        
        return {
            "total_evaluations": len(recent_results),
            "violations": len(violations),
            "critical_violations": len(critical_violations),
            "fatal_violations": len(fatal_violations),
            "violation_rate": len(violations) / len(recent_results) * 100,
            "last_evaluation": self._last_evaluation_at.isoformat() if self._last_evaluation_at else None,
            "active_violations": len(self._active_violations),
        }
    
    def _evaluate_single_rule(
        self,
        rule: RuleDefinition,
        context: Dict[str, any],
        evaluation_timestamp: str,
    ) -> RuleEvaluationResult:
        """Evaluate a single rule against context."""
        condition_results = []
        all_conditions_passed = True
        
        # Evaluate each condition
        for condition in rule.conditions:
            condition_passed = condition.evaluate(context)
            condition_explanation = condition.explain(context)
            condition_results.append(condition_explanation)
            
            if not condition_passed:
                all_conditions_passed = False
        
        # Determine overall result
        rule_passed = all_conditions_passed
        
        # Generate message
        if rule_passed:
            message = f"Rule '{rule.name}' passed all conditions"
        else:
            failed_conditions = [
                result for result in condition_results 
                if "= False" in result
            ]
            message = f"Rule '{rule.name}' failed: {'; '.join(failed_conditions)}"
        
        # Create details
        details = {
            "rule_type": rule.rule_type.value,
            "conditions_evaluated": len(rule.conditions),
            "conditions_passed": sum(1 for result in condition_results if "= True" in result),
            "parameters": {param.name: param.value for param in rule.parameters},
        }
        
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            passed=rule_passed,
            severity=rule.severity,
            message=message,
            details=details,
            condition_results=condition_results,
            evaluation_timestamp=evaluation_timestamp,
            context_snapshot=context.copy(),
        )
    
    def _get_rule_set_by_name(self, name: str) -> Optional[RuleSet]:
        """Get rule set by name."""
        for rule_set in self._rule_sets:
            if rule_set.name == name:
                return rule_set
        return None
    
    # Properties
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def rule_sets(self) -> List[RuleSet]:
        return self._rule_sets.copy()
    
    @property
    def active_rule_set_name(self) -> Optional[str]:
        return self._active_rule_set_name
    
    @property
    def active_rule_set(self) -> Optional[RuleSet]:
        if not self._active_rule_set_name:
            return None
        return self._get_rule_set_by_name(self._active_rule_set_name)
    
    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count
    
    @property
    def last_evaluation_at(self) -> Optional[datetime]:
        return self._last_evaluation_at
    
    @property
    def has_active_violations(self) -> bool:
        return len(self._active_violations) > 0


class RuleViolationTracker(AggregateRoot):
    """Tracks rule violations over time for analysis and reporting."""
    
    def __init__(
        self,
        entity_id: UUID,  # Challenge ID, Trader ID, etc.
        entity_type: str,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._entity_id = entity_id
        self._entity_type = entity_type
        self._violations: List[RuleEvaluationResult] = []
        self._violation_counts: Dict[str, int] = {}
        self._first_violation_at: Optional[datetime] = None
        self._last_violation_at: Optional[datetime] = None
    
    def record_violation(self, violation: RuleEvaluationResult) -> None:
        """Record a rule violation."""
        if violation.passed:
            return  # Not a violation
        
        self._violations.append(violation)
        
        # Update counts
        rule_id = violation.rule_id
        self._violation_counts[rule_id] = self._violation_counts.get(rule_id, 0) + 1
        
        # Update timestamps
        now = datetime.utcnow()
        if not self._first_violation_at:
            self._first_violation_at = now
        self._last_violation_at = now
        
        self._touch()
    
    def get_violations_by_severity(self, severity: RuleSeverity) -> List[RuleEvaluationResult]:
        """Get violations by severity level."""
        return [v for v in self._violations if v.severity == severity]
    
    def get_violations_by_rule_type(self, rule_type: RuleType) -> List[RuleEvaluationResult]:
        """Get violations by rule type."""
        return [
            v for v in self._violations 
            if v.details.get("rule_type") == rule_type.value
        ]
    
    def get_violation_frequency(self, rule_id: str) -> int:
        """Get violation frequency for specific rule."""
        return self._violation_counts.get(rule_id, 0)
    
    def get_most_violated_rules(self, limit: int = 5) -> List[tuple[str, int]]:
        """Get most frequently violated rules."""
        sorted_violations = sorted(
            self._violation_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_violations[:limit]
    
    # Properties
    @property
    def entity_id(self) -> UUID:
        return self._entity_id
    
    @property
    def entity_type(self) -> str:
        return self._entity_type
    
    @property
    def total_violations(self) -> int:
        return len(self._violations)
    
    @property
    def unique_rules_violated(self) -> int:
        return len(self._violation_counts)
    
    @property
    def first_violation_at(self) -> Optional[datetime]:
        return self._first_violation_at
    
    @property
    def last_violation_at(self) -> Optional[datetime]:
        return self._last_violation_at