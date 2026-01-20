"""Rules engine repository implementations."""

import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from ....infrastructure.database.base import BaseRepository
from ..domain.entities import RuleEngine, RuleViolationTracker
from ..domain.value_objects import (
    RuleCondition,
    RuleDefinition,
    RuleEvaluationResult,
    RuleOperator,
    RuleParameter,
    RuleSet,
    RuleSeverity,
    RuleType,
)
from .models import (
    RuleDefinitionModel,
    RuleEngineModel,
    RuleEvaluationResultModel,
    RuleSetModel,
    RuleViolationModel,
    RuleViolationTrackerModel,
)


class RuleEngineRepository(BaseRepository[RuleEngine, RuleEngineModel]):
    """Repository for rule engine aggregate."""
    
    def __init__(self, session: Session):
        super().__init__(session, RuleEngineModel)
    
    def find_by_name(self, name: str) -> Optional[RuleEngine]:
        """Find rule engine by name."""
        model = self.session.query(RuleEngineModel).filter(
            RuleEngineModel.name == name
        ).options(
            joinedload(RuleEngineModel.rule_sets).joinedload(RuleSetModel.rules)
        ).first()
        
        return self._to_entity(model) if model else None
    
    def find_by_challenge_id(self, challenge_id: UUID) -> Optional[RuleEngine]:
        """Find rule engine by challenge ID (naming convention)."""
        name = f"Challenge_{challenge_id}"
        return self.find_by_name(name)
    
    def save(self, entity: RuleEngine) -> RuleEngine:
        """Save rule engine entity."""
        model = self._find_or_create_model(entity.id)
        
        # Update basic fields
        model.name = entity.name
        model.description = entity.description
        model.active_rule_set_name = entity.active_rule_set_name
        model.evaluation_count = str(entity.evaluation_count)
        model.last_evaluation_at = entity.last_evaluation_at
        
        # Handle rule sets
        self._sync_rule_sets(model, entity.rule_sets)
        
        self.session.add(model)
        self.session.flush()
        
        return self._to_entity(model)
    
    def _sync_rule_sets(self, model: RuleEngineModel, rule_sets: List[RuleSet]) -> None:
        """Synchronize rule sets with database."""
        # Remove rule sets not in entity
        existing_names = {rs.name for rs in rule_sets}
        for rule_set_model in list(model.rule_sets):
            if rule_set_model.name not in existing_names:
                self.session.delete(rule_set_model)
        
        # Add or update rule sets
        existing_rule_sets = {rs.name: rs for rs in model.rule_sets}
        
        for rule_set in rule_sets:
            if rule_set.name in existing_rule_sets:
                rule_set_model = existing_rule_sets[rule_set.name]
            else:
                rule_set_model = RuleSetModel(
                    id=UUID(),
                    rule_engine_id=model.id,
                    name=rule_set.name,
                )
                model.rule_sets.append(rule_set_model)
            
            # Update rule set fields
            rule_set_model.description = rule_set.description
            rule_set_model.version = rule_set.version
            rule_set_model.tags = rule_set.tags
            
            # Sync rules
            self._sync_rules(rule_set_model, rule_set.rules)
    
    def _sync_rules(self, rule_set_model: RuleSetModel, rules: List[RuleDefinition]) -> None:
        """Synchronize rules with database."""
        # Remove rules not in entity
        existing_rule_ids = {rule.rule_id for rule in rules}
        for rule_model in list(rule_set_model.rules):
            if rule_model.rule_id not in existing_rule_ids:
                self.session.delete(rule_model)
        
        # Add or update rules
        existing_rules = {r.rule_id: r for r in rule_set_model.rules}
        
        for rule in rules:
            if rule.rule_id in existing_rules:
                rule_model = existing_rules[rule.rule_id]
            else:
                rule_model = RuleDefinitionModel(
                    id=UUID(),
                    rule_set_id=rule_set_model.id,
                    rule_id=rule.rule_id,
                )
                rule_set_model.rules.append(rule_model)
            
            # Update rule fields
            rule_model.name = rule.name
            rule_model.description = rule.description
            rule_model.rule_type = rule.rule_type.value
            rule_model.severity = rule.severity.value
            rule_model.enabled = rule.enabled
            rule_model.version = rule.version
            rule_model.tags = rule.tags
            rule_model.conditions = [self._serialize_condition(c) for c in rule.conditions]
            rule_model.parameters = [self._serialize_parameter(p) for p in rule.parameters]
    
    def _serialize_condition(self, condition: RuleCondition) -> Dict:
        """Serialize rule condition to JSON."""
        return {
            "field": condition.field,
            "operator": condition.operator.value,
            "value": condition.value,
            "secondary_value": condition.secondary_value,
        }
    
    def _serialize_parameter(self, parameter: RuleParameter) -> Dict:
        """Serialize rule parameter to JSON."""
        return {
            "name": parameter.name,
            "value": parameter.value,
            "data_type": parameter.data_type,
            "description": parameter.description,
        }
    
    def _to_entity(self, model: RuleEngineModel) -> RuleEngine:
        """Convert model to entity."""
        rule_sets = []
        
        for rule_set_model in model.rule_sets:
            rules = []
            
            for rule_model in rule_set_model.rules:
                # Deserialize conditions
                conditions = []
                for cond_data in rule_model.conditions:
                    conditions.append(RuleCondition(
                        field=cond_data["field"],
                        operator=RuleOperator(cond_data["operator"]),
                        value=cond_data["value"],
                        secondary_value=cond_data.get("secondary_value"),
                    ))
                
                # Deserialize parameters
                parameters = []
                for param_data in rule_model.parameters:
                    parameters.append(RuleParameter(
                        name=param_data["name"],
                        value=param_data["value"],
                        data_type=param_data["data_type"],
                        description=param_data.get("description", ""),
                    ))
                
                rule = RuleDefinition(
                    rule_id=rule_model.rule_id,
                    name=rule_model.name,
                    description=rule_model.description,
                    rule_type=RuleType(rule_model.rule_type),
                    severity=RuleSeverity(rule_model.severity),
                    conditions=conditions,
                    parameters=parameters,
                    enabled=rule_model.enabled,
                    tags=rule_model.tags,
                    version=rule_model.version,
                )
                rules.append(rule)
            
            rule_set = RuleSet(
                name=rule_set_model.name,
                description=rule_set_model.description,
                rules=rules,
                tags=rule_set_model.tags,
                version=rule_set_model.version,
            )
            rule_sets.append(rule_set)
        
        entity = RuleEngine(
            name=model.name,
            description=model.description,
            rule_sets=rule_sets,
            id=model.id,
        )
        
        # Set internal state
        if model.active_rule_set_name:
            entity.activate_rule_set(model.active_rule_set_name)
        
        entity._evaluation_count = int(model.evaluation_count)
        entity._last_evaluation_at = model.last_evaluation_at
        
        return entity


class RuleEvaluationResultRepository(BaseRepository[RuleEvaluationResult, RuleEvaluationResultModel]):
    """Repository for rule evaluation results."""
    
    def __init__(self, session: Session):
        super().__init__(session, RuleEvaluationResultModel)
    
    def save_results(self, rule_engine_id: UUID, results: List[RuleEvaluationResult]) -> None:
        """Save multiple evaluation results."""
        for result in results:
            model = RuleEvaluationResultModel(
                id=UUID(),
                rule_engine_id=rule_engine_id,
                rule_id=result.rule_id,
                rule_name=result.rule_name,
                passed=result.passed,
                severity=result.severity.value,
                message=result.message,
                details=result.details,
                condition_results=result.condition_results,
                evaluation_timestamp=datetime.fromisoformat(result.evaluation_timestamp),
                context_snapshot=result.context_snapshot,
            )
            self.session.add(model)
    
    def find_violations_by_engine(
        self,
        rule_engine_id: UUID,
        limit: int = 100,
        severity_filter: Optional[RuleSeverity] = None,
    ) -> List[RuleEvaluationResult]:
        """Find violations for a rule engine."""
        query = self.session.query(RuleEvaluationResultModel).filter(
            and_(
                RuleEvaluationResultModel.rule_engine_id == rule_engine_id,
                RuleEvaluationResultModel.passed == False,
            )
        )
        
        if severity_filter:
            query = query.filter(RuleEvaluationResultModel.severity == severity_filter.value)
        
        models = query.order_by(desc(RuleEvaluationResultModel.evaluation_timestamp)).limit(limit).all()
        
        return [self._to_entity(model) for model in models]
    
    def find_recent_results(
        self,
        rule_engine_id: UUID,
        hours: int = 24,
        limit: int = 1000,
    ) -> List[RuleEvaluationResult]:
        """Find recent evaluation results."""
        cutoff_time = datetime.utcnow() - datetime.timedelta(hours=hours)
        
        models = self.session.query(RuleEvaluationResultModel).filter(
            and_(
                RuleEvaluationResultModel.rule_engine_id == rule_engine_id,
                RuleEvaluationResultModel.evaluation_timestamp >= cutoff_time,
            )
        ).order_by(desc(RuleEvaluationResultModel.evaluation_timestamp)).limit(limit).all()
        
        return [self._to_entity(model) for model in models]
    
    def _to_entity(self, model: RuleEvaluationResultModel) -> RuleEvaluationResult:
        """Convert model to entity."""
        return RuleEvaluationResult(
            rule_id=model.rule_id,
            rule_name=model.rule_name,
            passed=model.passed,
            severity=RuleSeverity(model.severity),
            message=model.message,
            details=model.details,
            condition_results=model.condition_results,
            evaluation_timestamp=model.evaluation_timestamp.isoformat(),
            context_snapshot=model.context_snapshot,
        )


class RuleViolationTrackerRepository(BaseRepository[RuleViolationTracker, RuleViolationTrackerModel]):
    """Repository for rule violation tracker."""
    
    def __init__(self, session: Session):
        super().__init__(session, RuleViolationTrackerModel)
    
    def find_by_entity(self, entity_id: UUID, entity_type: str) -> Optional[RuleViolationTracker]:
        """Find tracker by entity ID and type."""
        model = self.session.query(RuleViolationTrackerModel).filter(
            and_(
                RuleViolationTrackerModel.entity_id == entity_id,
                RuleViolationTrackerModel.entity_type == entity_type,
            )
        ).options(joinedload(RuleViolationTrackerModel.violations)).first()
        
        return self._to_entity(model) if model else None
    
    def save(self, entity: RuleViolationTracker) -> RuleViolationTracker:
        """Save violation tracker entity."""
        model = self._find_or_create_model(entity.id)
        
        # Update basic fields
        model.entity_id = entity.entity_id
        model.entity_type = entity.entity_type
        model.total_violations = str(entity.total_violations)
        model.unique_rules_violated = str(entity.unique_rules_violated)
        model.first_violation_at = entity.first_violation_at
        model.last_violation_at = entity.last_violation_at
        model.violation_counts = entity._violation_counts
        
        # Handle violations (append-only for audit trail)
        existing_count = len(model.violations)
        new_violations = entity._violations[existing_count:]
        
        for violation in new_violations:
            violation_model = RuleViolationModel(
                id=UUID(),
                tracker_id=model.id,
                rule_id=violation.rule_id,
                rule_name=violation.rule_name,
                severity=violation.severity.value,
                message=violation.message,
                details=violation.details,
                condition_results=violation.condition_results,
                evaluation_timestamp=datetime.fromisoformat(violation.evaluation_timestamp),
                context_snapshot=violation.context_snapshot,
            )
            model.violations.append(violation_model)
        
        self.session.add(model)
        self.session.flush()
        
        return self._to_entity(model)
    
    def _to_entity(self, model: RuleViolationTrackerModel) -> RuleViolationTracker:
        """Convert model to entity."""
        entity = RuleViolationTracker(
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            id=model.id,
        )
        
        # Restore violations
        violations = []
        for violation_model in model.violations:
            violation = RuleEvaluationResult(
                rule_id=violation_model.rule_id,
                rule_name=violation_model.rule_name,
                passed=False,  # All stored violations are failures
                severity=RuleSeverity(violation_model.severity),
                message=violation_model.message,
                details=violation_model.details,
                condition_results=violation_model.condition_results,
                evaluation_timestamp=violation_model.evaluation_timestamp.isoformat(),
                context_snapshot=violation_model.context_snapshot,
            )
            violations.append(violation)
        
        # Set internal state
        entity._violations = violations
        entity._violation_counts = model.violation_counts
        entity._first_violation_at = model.first_violation_at
        entity._last_violation_at = model.last_violation_at
        
        return entity