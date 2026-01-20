"""Rules engine domain events."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from ....shared.kernel.domain_event import DomainEvent


class RuleSetCreated(DomainEvent):
    """Event emitted when a rule set is created."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_set_name: str,
        rule_count: int,
        version: str,
    ):
        super().__init__(aggregate_id)
        self.rule_set_name = rule_set_name
        self.rule_count = rule_count
        self.version = version


class RuleSetActivated(DomainEvent):
    """Event emitted when a rule set is activated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_set_name: str,
        previous_rule_set: Optional[str],
        rule_count: int,
    ):
        super().__init__(aggregate_id)
        self.rule_set_name = rule_set_name
        self.previous_rule_set = previous_rule_set
        self.rule_count = rule_count


class RuleSetDeactivated(DomainEvent):
    """Event emitted when a rule set is deactivated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_set_name: str,
    ):
        super().__init__(aggregate_id)
        self.rule_set_name = rule_set_name


class RuleEvaluated(DomainEvent):
    """Event emitted when a rule is evaluated."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_id: str,
        rule_name: str,
        passed: bool,
        severity: str,
        message: str,
    ):
        super().__init__(aggregate_id)
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.severity = severity
        self.message = message


class RuleViolationDetected(DomainEvent):
    """Event emitted when a rule violation is detected."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_id: str,
        rule_name: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
        context_snapshot: Dict[str, Any],
    ):
        super().__init__(aggregate_id)
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.details = details
        self.context_snapshot = context_snapshot


class RuleViolationResolved(DomainEvent):
    """Event emitted when a rule violation is resolved."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_id: str,
        rule_name: str,
        resolution_message: str,
    ):
        super().__init__(aggregate_id)
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.resolution_message = resolution_message


class CriticalViolationDetected(DomainEvent):
    """Event emitted when a critical rule violation is detected."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rule_id: str,
        rule_name: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
        context_snapshot: Dict[str, Any],
        requires_immediate_action: bool = True,
    ):
        super().__init__(aggregate_id)
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.details = details
        self.context_snapshot = context_snapshot
        self.requires_immediate_action = requires_immediate_action


class RuleEngineStateChanged(DomainEvent):
    """Event emitted when rule engine state changes."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        change_type: str,
        old_value: Any,
        new_value: Any,
        reason: str,
    ):
        super().__init__(aggregate_id)
        self.change_type = change_type
        self.old_value = old_value
        self.new_value = new_value
        self.reason = reason


class RuleEvaluationBatchCompleted(DomainEvent):
    """Event emitted when a batch of rule evaluations is completed."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        rules_evaluated: int,
        violations_detected: int,
        critical_violations: int,
        evaluation_duration_ms: int,
        context_type: str,
    ):
        super().__init__(aggregate_id)
        self.rules_evaluated = rules_evaluated
        self.violations_detected = violations_detected
        self.critical_violations = critical_violations
        self.evaluation_duration_ms = evaluation_duration_ms
        self.context_type = context_type