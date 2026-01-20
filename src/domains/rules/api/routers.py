"""Rules engine API routers."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ....infrastructure.database.connection import get_db_session
from ....infrastructure.security.auth import get_current_user
from ....shared.events.event_bus import get_event_bus
from ....shared.utils.money import Money
from ..application.services import (
    RiskEngineIntegrationService,
    RuleEvaluationService,
    RuleViolationService,
)
from ..domain.services import RuleEngineIntegrationService, RuleSetFactory
from ..domain.value_objects import RuleTemplates, RuleType, RuleSeverity
from ..infrastructure.repositories import (
    RuleEngineRepository,
    RuleEvaluationResultRepository,
    RuleViolationTrackerRepository,
)
from .schemas import (
    ActivateRuleSetRequest,
    AddRuleSetRequest,
    CreateChallengeRuleEngineRequest,
    CreateRuleEngineRequest,
    EvaluateRulesRequest,
    HealthCheckResponse,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RuleEvaluationResponse,
    RuleEngineSchema,
    RuleTemplateRequest,
    RuleTemplateResponse,
    ViolationAnalysisRequest,
    ViolationAnalysisResponse,
)

router = APIRouter(prefix="/rules", tags=["Rules Engine"])


@router.post("/engines", response_model=RuleEngineSchema, status_code=status.HTTP_201_CREATED)
async def create_rule_engine(
    request: CreateRuleEngineRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Create a new rule engine."""
    try:
        repo = RuleEngineRepository(db)
        
        # Check if engine with same name exists
        existing = repo.find_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule engine with name '{request.name}' already exists"
            )
        
        # Create rule engine from domain service
        from ..domain.entities import RuleEngine
        from ..domain.value_objects import RuleSet, RuleDefinition, RuleCondition, RuleParameter, RuleType, RuleSeverity, RuleOperator
        
        # Convert schema to domain objects
        rule_sets = []
        for rs_schema in request.rule_sets:
            rules = []
            for rule_schema in rs_schema.rules:
                conditions = []
                for cond_schema in rule_schema.conditions:
                    conditions.append(RuleCondition(
                        field=cond_schema.field,
                        operator=RuleOperator(cond_schema.operator),
                        value=cond_schema.value,
                        secondary_value=cond_schema.secondary_value,
                    ))
                
                parameters = []
                for param_schema in rule_schema.parameters:
                    parameters.append(RuleParameter(
                        name=param_schema.name,
                        value=param_schema.value,
                        data_type=param_schema.data_type,
                        description=param_schema.description,
                    ))
                
                rule = RuleDefinition(
                    rule_id=rule_schema.rule_id,
                    name=rule_schema.name,
                    description=rule_schema.description,
                    rule_type=RuleType(rule_schema.rule_type),
                    severity=RuleSeverity(rule_schema.severity),
                    conditions=conditions,
                    parameters=parameters,
                    enabled=rule_schema.enabled,
                    tags=rule_schema.tags,
                    version=rule_schema.version,
                )
                rules.append(rule)
            
            rule_set = RuleSet(
                name=rs_schema.name,
                description=rs_schema.description,
                rules=rules,
                tags=rs_schema.tags,
                version=rs_schema.version,
            )
            rule_sets.append(rule_set)
        
        engine = RuleEngine(
            name=request.name,
            description=request.description,
            rule_sets=rule_sets,
        )
        
        # Save to repository
        saved_engine = repo.save(engine)
        db.commit()
        
        # Convert to response schema
        return _engine_to_schema(saved_engine)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create rule engine: {str(e)}"
        )


@router.post("/engines/challenge", response_model=RuleEngineSchema, status_code=status.HTTP_201_CREATED)
async def create_challenge_rule_engine(
    request: CreateChallengeRuleEngineRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Create a rule engine for a specific challenge."""
    try:
        repo = RuleEngineRepository(db)
        
        # Check if engine already exists for this challenge
        existing = repo.find_by_challenge_id(request.challenge_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule engine already exists for challenge {request.challenge_id}"
            )
        
        # Create challenge rule engine using domain service
        initial_balance = Money(request.initial_balance, request.currency)
        engine = RuleEngineIntegrationService.create_challenge_rule_engine(
            challenge_id=request.challenge_id,
            challenge_type=request.challenge_type,
            initial_balance=initial_balance,
        )
        
        # Save to repository
        saved_engine = repo.save(engine)
        db.commit()
        
        return _engine_to_schema(saved_engine)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create challenge rule engine: {str(e)}"
        )


@router.get("/engines/{engine_id}", response_model=RuleEngineSchema)
async def get_rule_engine(
    engine_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get rule engine by ID."""
    repo = RuleEngineRepository(db)
    engine = repo.find_by_id(engine_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule engine {engine_id} not found"
        )
    
    return _engine_to_schema(engine)


@router.get("/engines/challenge/{challenge_id}", response_model=RuleEngineSchema)
async def get_challenge_rule_engine(
    challenge_id: UUID,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Get rule engine for a specific challenge."""
    repo = RuleEngineRepository(db)
    engine = repo.find_by_challenge_id(challenge_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule engine not found for challenge {challenge_id}"
        )
    
    return _engine_to_schema(engine)


@router.post("/engines/{engine_id}/rule-sets", response_model=RuleEngineSchema)
async def add_rule_set(
    engine_id: UUID,
    request: AddRuleSetRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Add a rule set to an existing rule engine."""
    try:
        repo = RuleEngineRepository(db)
        engine = repo.find_by_id(engine_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule engine {engine_id} not found"
            )
        
        # Convert schema to domain object
        from ..domain.value_objects import RuleSet, RuleDefinition, RuleCondition, RuleParameter, RuleType, RuleSeverity, RuleOperator
        
        rules = []
        for rule_schema in request.rule_set.rules:
            conditions = []
            for cond_schema in rule_schema.conditions:
                conditions.append(RuleCondition(
                    field=cond_schema.field,
                    operator=RuleOperator(cond_schema.operator),
                    value=cond_schema.value,
                    secondary_value=cond_schema.secondary_value,
                ))
            
            parameters = []
            for param_schema in rule_schema.parameters:
                parameters.append(RuleParameter(
                    name=param_schema.name,
                    value=param_schema.value,
                    data_type=param_schema.data_type,
                    description=param_schema.description,
                ))
            
            rule = RuleDefinition(
                rule_id=rule_schema.rule_id,
                name=rule_schema.name,
                description=rule_schema.description,
                rule_type=RuleType(rule_schema.rule_type),
                severity=RuleSeverity(rule_schema.severity),
                conditions=conditions,
                parameters=parameters,
                enabled=rule_schema.enabled,
                tags=rule_schema.tags,
                version=rule_schema.version,
            )
            rules.append(rule)
        
        rule_set = RuleSet(
            name=request.rule_set.name,
            description=request.rule_set.description,
            rules=rules,
            tags=request.rule_set.tags,
            version=request.rule_set.version,
        )
        
        # Add rule set to engine
        engine.add_rule_set(rule_set)
        
        # Save to repository
        saved_engine = repo.save(engine)
        db.commit()
        
        return _engine_to_schema(saved_engine)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add rule set: {str(e)}"
        )


@router.post("/engines/{engine_id}/activate", response_model=RuleEngineSchema)
async def activate_rule_set(
    engine_id: UUID,
    request: ActivateRuleSetRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Activate a rule set in the engine."""
    try:
        repo = RuleEngineRepository(db)
        engine = repo.find_by_id(engine_id)
        
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule engine {engine_id} not found"
            )
        
        # Activate rule set
        engine.activate_rule_set(request.rule_set_name)
        
        # Save to repository
        saved_engine = repo.save(engine)
        db.commit()
        
        return _engine_to_schema(saved_engine)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate rule set: {str(e)}"
        )


@router.post("/engines/{engine_id}/evaluate", response_model=RuleEvaluationResponse)
async def evaluate_rules(
    engine_id: UUID,
    request: EvaluateRulesRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Evaluate rules against provided context."""
    try:
        repo = RuleEngineRepository(db)
        result_repo = RuleEvaluationResultRepository(db)
        event_bus = get_event_bus()
        
        engine = repo.find_by_id(engine_id)
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule engine {engine_id} not found"
            )
        
        # Convert context schema to dict
        context = request.context.dict(exclude_unset=True)
        context.update(request.context.additional_data)
        
        # Convert rule types if provided
        rule_types = None
        if request.rule_types:
            rule_types = [RuleType(rt) for rt in request.rule_types]
        
        # Evaluate rules using application service
        service = RuleEvaluationService(event_bus)
        
        # Build challenge data for evaluation
        challenge_data = {
            "challenge_id": context.get("challenge_id"),
            "trader_id": context.get("trader_id"),
            "initial_balance": Money(context.get("initial_balance", 0), "USD"),
            "current_balance": Money(context.get("current_balance", 0), "USD"),
            "daily_pnl": Money(context.get("daily_pnl", 0), "USD"),
            "total_pnl": Money(context.get("total_pnl", 0), "USD"),
            "trading_days": context.get("trading_days", 0),
            "daily_trade_count": context.get("daily_trade_count", 0),
            "total_trades": context.get("total_trades", 0),
            "daily_profits": [],
            "max_drawdown": Money(0, "USD"),
            "current_drawdown": Money(0, "USD"),
            "largest_position_size": Money(0, "USD"),
            "additional_data": context,
        }
        
        evaluation_results = await service.evaluate_challenge_rules(
            challenge_id=context.get("challenge_id"),
            rule_engine=engine,
            challenge_data=challenge_data,
        )
        
        # Save evaluation results
        results = engine.evaluate_rules(context, rule_types, request.tags)
        result_repo.save_results(engine_id, results)
        
        # Save updated engine state
        repo.save(engine)
        db.commit()
        
        return RuleEvaluationResponse(**evaluation_results)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate rules: {str(e)}"
        )


@router.post("/engines/{engine_id}/risk-assessment", response_model=RiskAssessmentResponse)
async def assess_risk(
    engine_id: UUID,
    request: RiskAssessmentRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Perform risk assessment using rules engine."""
    try:
        repo = RuleEngineRepository(db)
        event_bus = get_event_bus()
        
        engine = repo.find_by_id(engine_id)
        if not engine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule engine {engine_id} not found"
            )
        
        # Convert context to dict
        trading_context = request.trading_context.dict(exclude_unset=True)
        trading_context.update(request.trading_context.additional_data)
        
        # Perform risk assessment
        service = RiskEngineIntegrationService(event_bus)
        risk_results = await service.evaluate_risk_rules(engine, trading_context)
        
        # Save updated engine state
        repo.save(engine)
        db.commit()
        
        return RiskAssessmentResponse(**risk_results)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assess risk: {str(e)}"
        )


@router.post("/templates/generate", response_model=RuleTemplateResponse)
async def generate_rule_template(
    request: RuleTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a rule from a template."""
    try:
        from decimal import Decimal
        
        template_type = request.template_type.upper()
        params = request.parameters
        
        # Generate rule based on template type
        if template_type == "MAX_DAILY_DRAWDOWN":
            rule = RuleTemplates.max_daily_drawdown(Decimal(str(params["max_drawdown_percent"])))
        elif template_type == "MAX_TOTAL_DRAWDOWN":
            rule = RuleTemplates.max_total_drawdown(Decimal(str(params["max_drawdown_percent"])))
        elif template_type == "PROFIT_TARGET":
            target_amount = Money(params["target_amount"], params.get("currency", "USD"))
            rule = RuleTemplates.profit_target(target_amount)
        elif template_type == "MAX_TRADES_PER_DAY":
            rule = RuleTemplates.max_trades_per_day(int(params["max_trades"]))
        elif template_type == "CONSISTENCY_RULE":
            rule = RuleTemplates.consistency_rule(Decimal(str(params["max_single_day_percent"])))
        elif template_type == "MIN_TRADING_DAYS":
            rule = RuleTemplates.min_trading_days(int(params["min_days"]))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown template type: {template_type}"
            )
        
        # Convert to schema
        rule_schema = _rule_to_schema(rule)
        
        return RuleTemplateResponse(rule=rule_schema)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate rule template: {str(e)}"
        )


@router.post("/violations/analyze", response_model=ViolationAnalysisResponse)
async def analyze_violations(
    request: ViolationAnalysisRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """Analyze rule violations for an entity."""
    try:
        tracker_repo = RuleViolationTrackerRepository(db)
        event_bus = get_event_bus()
        
        # Find violation tracker
        tracker = tracker_repo.find_by_entity(request.entity_id, request.entity_type)
        if not tracker:
            return ViolationAnalysisResponse(
                analysis={"message": "No violations found for entity"},
                recommendations=["No violations detected. Continue current approach."],
                requires_immediate_action=False,
                violations=[],
            )
        
        # Analyze violations
        service = RuleViolationService(event_bus)
        analysis_results = await service.analyze_violation_trends(
            violations=tracker._violations,
            time_window_hours=request.time_window_hours,
        )
        
        # Convert violations to schema
        violation_schemas = []
        for violation in tracker._violations[-50:]:  # Last 50 violations
            violation_schemas.append({
                "rule_id": violation.rule_id,
                "rule_name": violation.rule_name,
                "severity": violation.severity.value,
                "message": violation.message,
                "details": violation.details,
                "evaluation_timestamp": violation.evaluation_timestamp,
                "context_snapshot": violation.context_snapshot,
            })
        
        return ViolationAnalysisResponse(
            analysis=analysis_results["analysis"],
            recommendations=analysis_results["recommendations"],
            requires_immediate_action=analysis_results["requires_immediate_action"],
            violations=violation_schemas,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze violations: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    db: Session = Depends(get_db_session),
):
    """Health check endpoint."""
    try:
        repo = RuleEngineRepository(db)
        result_repo = RuleEvaluationResultRepository(db)
        
        # Count rule engines
        engines_count = db.query(repo.model_class).count()
        
        # Count recent evaluations
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_evaluations = db.query(result_repo.model_class).filter(
            result_repo.model_class.evaluation_timestamp >= cutoff
        ).count()
        
        # Get last evaluation timestamp
        last_result = db.query(result_repo.model_class).order_by(
            result_repo.model_class.evaluation_timestamp.desc()
        ).first()
        
        last_evaluation = None
        if last_result:
            last_evaluation = last_result.evaluation_timestamp.isoformat()
        
        return HealthCheckResponse(
            status="healthy",
            rule_engines_count=engines_count,
            active_evaluations=recent_evaluations,
            last_evaluation=last_evaluation,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


def _engine_to_schema(engine) -> RuleEngineSchema:
    """Convert rule engine entity to schema."""
    from ..domain.entities import RuleEngine
    
    rule_sets = []
    for rule_set in engine.rule_sets:
        rules = []
        for rule in rule_set.rules:
            rule_schema = _rule_to_schema(rule)
            rules.append(rule_schema)
        
        rule_sets.append({
            "name": rule_set.name,
            "description": rule_set.description,
            "rules": rules,
            "tags": rule_set.tags,
            "version": rule_set.version,
        })
    
    return RuleEngineSchema(
        id=engine.id,
        name=engine.name,
        description=engine.description,
        rule_sets=rule_sets,
        active_rule_set_name=engine.active_rule_set_name,
        evaluation_count=engine.evaluation_count,
        last_evaluation_at=engine.last_evaluation_at,
        created_at=engine.created_at,
        updated_at=engine.updated_at,
    )


def _rule_to_schema(rule):
    """Convert rule definition to schema."""
    conditions = []
    for condition in rule.conditions:
        conditions.append({
            "field": condition.field,
            "operator": condition.operator.value,
            "value": condition.value,
            "secondary_value": condition.secondary_value,
        })
    
    parameters = []
    for parameter in rule.parameters:
        parameters.append({
            "name": parameter.name,
            "value": parameter.value,
            "data_type": parameter.data_type,
            "description": parameter.description,
        })
    
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type.value,
        "severity": rule.severity.value,
        "conditions": conditions,
        "parameters": parameters,
        "enabled": rule.enabled,
        "tags": rule.tags,
        "version": rule.version,
    }