# Rules Engine Integration with Challenge Engine

## Overview

The Rules Engine provides a comprehensive, configurable system for evaluating trading rules and risk violations in prop firm challenges. It integrates seamlessly with the existing Challenge Engine to provide real-time rule evaluation, violation detection, and automated challenge state transitions.

## Architecture Integration

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Challenge     │    │  Rules Engine   │    │  Risk Engine    │
│   Engine        │◄──►│                 │◄──►│                 │
│                 │    │                 │    │                 │
│ - State Machine │    │ - Rule Sets     │    │ - Risk Rules    │
│ - Transitions   │    │ - Evaluation    │    │ - Violations    │
│ - Events        │    │ - Violations    │    │ - Actions       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Event Bus     │
                    │                 │
                    │ - Domain Events │
                    │ - Integration   │
                    │ - Audit Trail   │
                    └─────────────────┘
```

## Key Integration Points

### 1. Challenge Creation → Rule Engine Setup

When a challenge is created, a corresponding rule engine is automatically configured:

```python
# Challenge creation triggers rule engine setup
async def create_challenge(challenge_data: CreateChallengeRequest) -> Challenge:
    # 1. Create challenge entity
    challenge = Challenge(
        trader_id=challenge_data.trader_id,
        parameters=challenge_data.parameters,
    )
    
    # 2. Create rule engine for challenge
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge.id,
        challenge_type=challenge_data.challenge_type,
        initial_balance=challenge_data.initial_balance,
    )
    
    # 3. Save both entities
    challenge_repo.save(challenge)
    rule_engine_repo.save(rule_engine)
    
    return challenge
```

### 2. Trading Updates → Rule Evaluation

Every trading update triggers rule evaluation:

```python
# Trading update flow
async def update_challenge_metrics(
    challenge_id: UUID,
    trading_update: TradingUpdateRequest,
) -> ChallengeUpdateResponse:
    
    # 1. Update challenge metrics
    challenge = challenge_repo.find_by_id(challenge_id)
    challenge.update_trading_metrics(
        new_balance=trading_update.new_balance,
        daily_pnl=trading_update.daily_pnl,
        trade_count=trading_update.trade_count,
    )
    
    # 2. Evaluate rules in real-time
    rule_engine = rule_engine_repo.find_by_challenge_id(challenge_id)
    context = RuleContextBuilder.build_challenge_context(
        challenge_id=challenge_id,
        trader_id=challenge.trader_id,
        initial_balance=challenge.parameters.initial_balance,
        current_balance=challenge.current_balance,
        daily_pnl=challenge.daily_pnl,
        total_pnl=challenge.total_pnl,
        trading_days=challenge.trading_days,
        daily_trade_count=trading_update.trade_count,
        total_trades=challenge.total_trades,
        daily_profits=challenge.daily_profits,
        max_drawdown=challenge.max_drawdown,
        current_drawdown=challenge.current_drawdown,
        largest_position_size=trading_update.largest_position_size,
    )
    
    # 3. Evaluate critical rules for real-time monitoring
    evaluation_service = RuleEvaluationService(event_bus)
    results = await evaluation_service.evaluate_real_time_rules(
        rule_engine=rule_engine,
        context=context,
        rule_types=[
            RuleType.MAX_DAILY_DRAWDOWN,
            RuleType.MAX_TOTAL_DRAWDOWN,
            RuleType.MAX_TRADES_PER_DAY,
        ]
    )
    
    # 4. Process violations and trigger challenge state changes
    violations = [r for r in results if r.is_violation]
    fatal_violations = [r for r in violations if r.severity == RuleSeverity.FATAL]
    
    if fatal_violations:
        # Auto-fail challenge on fatal violations
        violation_messages = [v.message for v in fatal_violations]
        challenge.fail_challenge(f"Fatal rule violations: {'; '.join(violation_messages)}")
    
    # 5. Save updates
    challenge_repo.save(challenge)
    rule_engine_repo.save(rule_engine)
    
    return ChallengeUpdateResponse(
        challenge_state=challenge.state,
        violations=violations,
        should_halt_trading=rule_engine.has_fatal_violations(),
    )
```

### 3. Rule Violations → Challenge State Transitions

Rule violations automatically trigger challenge state changes:

```python
# Event handler for rule violations
@event_handler(RuleViolationDetected)
async def handle_rule_violation(event: RuleViolationDetected):
    """Handle rule violation and update challenge state if needed."""
    
    # Find associated challenge
    challenge_id = event.context_snapshot.get("challenge_id")
    if not challenge_id:
        return
    
    challenge = challenge_repo.find_by_id(UUID(challenge_id))
    if not challenge or not challenge.is_active:
        return
    
    # Process violation based on severity
    if event.severity == RuleSeverity.FATAL.value:
        # Fatal violations immediately fail the challenge
        challenge.fail_challenge(
            reason=f"Fatal rule violation: {event.message}",
            failed_by=None,  # Automatic failure
        )
        
        # Emit challenge failed event
        await event_bus.publish(ChallengeFailed(
            aggregate_id=challenge.id,
            trader_id=challenge.trader_id,
            failure_reason=f"Rule violation: {event.rule_name}",
            risk_violations=[{
                "rule_name": event.rule_name,
                "violation_type": "rule_engine",
                "severity": event.severity,
                "description": event.message,
            }],
            final_balance=str(challenge.current_balance.amount),
            trading_days=challenge.trading_days,
        ))
    
    elif event.severity == RuleSeverity.CRITICAL.value:
        # Critical violations trigger warnings and restrictions
        await event_bus.publish(TradingRestrictionApplied(
            challenge_id=challenge.id,
            trader_id=challenge.trader_id,
            restriction_type="POSITION_SIZE_LIMIT",
            reason=f"Critical rule violation: {event.message}",
        ))
    
    # Save challenge state
    challenge_repo.save(challenge)
```

## Rule Configuration by Challenge Type

### Phase 1 Challenge Rules

```python
def create_phase1_rules(initial_balance: Money) -> RuleSet:
    """Standard Phase 1 evaluation rules."""
    
    rules = [
        # Fatal violations (immediate challenge failure)
        RuleTemplates.max_daily_drawdown(Decimal("5.0")),      # 5% max daily loss
        RuleTemplates.max_total_drawdown(Decimal("10.0")),     # 10% max total loss
        
        # Completion requirements
        RuleTemplates.profit_target(Money(initial_balance.amount * Decimal("0.08"), "USD")),  # 8% profit target
        RuleTemplates.min_trading_days(5),                     # Minimum 5 trading days
        
        # Trading behavior rules
        RuleTemplates.max_trades_per_day(100),                 # Max 100 trades per day
        RuleTemplates.consistency_rule(Decimal("50")),         # Max 50% profit from single day
    ]
    
    return RuleSet(
        name="Phase1_Standard",
        description="Standard Phase 1 evaluation rules",
        rules=rules,
        tags=["phase1", "evaluation", "standard"],
        version="1.0",
    )
```

### Phase 2 (Verification) Rules

```python
def create_phase2_rules(initial_balance: Money) -> RuleSet:
    """Phase 2 verification rules (stricter)."""
    
    rules = [
        # Same risk limits as Phase 1
        RuleTemplates.max_daily_drawdown(Decimal("5.0")),
        RuleTemplates.max_total_drawdown(Decimal("10.0")),
        
        # Lower profit target
        RuleTemplates.profit_target(Money(initial_balance.amount * Decimal("0.05"), "USD")),  # 5% profit target
        RuleTemplates.min_trading_days(5),
        
        # Stricter consistency requirement
        RuleTemplates.consistency_rule(Decimal("40")),         # Max 40% profit from single day
    ]
    
    return RuleSet(
        name="Phase2_Verification",
        description="Phase 2 verification rules",
        rules=rules,
        tags=["phase2", "verification", "funded"],
        version="1.0",
    )
```

### Funded Account Rules

```python
def create_funded_account_rules(account_balance: Money) -> RuleSet:
    """Funded account rules (ongoing risk management)."""
    
    rules = [
        # Core risk limits only
        RuleTemplates.max_daily_drawdown(Decimal("5.0")),
        RuleTemplates.max_total_drawdown(Decimal("10.0")),
        
        # No profit targets or minimum days for funded accounts
    ]
    
    return RuleSet(
        name="Funded_Account",
        description="Funded account risk management rules",
        rules=rules,
        tags=["funded", "live", "risk"],
        version="1.0",
    )
```

## Real-Time Rule Evaluation

### High-Frequency Monitoring

```python
# Real-time rule evaluation for critical rules
async def evaluate_critical_rules(
    challenge_id: UUID,
    trading_context: Dict[str, Any],
) -> RiskAssessment:
    """Evaluate critical rules for real-time risk monitoring."""
    
    rule_engine = rule_engine_repo.find_by_challenge_id(challenge_id)
    
    # Focus on critical rules that can trigger immediate actions
    critical_rule_types = [
        RuleType.MAX_DAILY_DRAWDOWN,
        RuleType.MAX_TOTAL_DRAWDOWN,
        RuleType.MAX_POSITION_SIZE,
        RuleType.MAX_LEVERAGE,
    ]
    
    results = rule_engine.evaluate_rules(
        context=trading_context,
        rule_types=critical_rule_types,
        tags=["critical", "realtime"],
    )
    
    # Analyze risk level
    violations = [r for r in results if r.is_violation]
    fatal_violations = [r for r in violations if r.severity == RuleSeverity.FATAL]
    critical_violations = [r for r in violations if r.severity == RuleSeverity.CRITICAL]
    
    # Calculate risk score
    risk_score = calculate_risk_score(violations)
    
    return RiskAssessment(
        risk_level=get_risk_level(risk_score),
        should_halt_trading=len(fatal_violations) > 0,
        should_reduce_exposure=len(critical_violations) > 0,
        violations=violations,
        recommendations=get_risk_recommendations(violations),
    )
```

### Batch Evaluation for Reporting

```python
# Daily/periodic comprehensive rule evaluation
async def evaluate_all_challenge_rules(challenge_id: UUID) -> ComprehensiveEvaluation:
    """Comprehensive evaluation of all rules for reporting and analysis."""
    
    challenge = challenge_repo.find_by_id(challenge_id)
    rule_engine = rule_engine_repo.find_by_challenge_id(challenge_id)
    
    # Build complete context
    context = RuleContextBuilder.build_challenge_context(
        challenge_id=challenge.id,
        trader_id=challenge.trader_id,
        initial_balance=challenge.parameters.initial_balance,
        current_balance=challenge.current_balance,
        daily_pnl=challenge.daily_pnl,
        total_pnl=challenge.total_pnl,
        trading_days=challenge.trading_days,
        daily_trade_count=get_daily_trade_count(challenge_id),
        total_trades=challenge.total_trades,
        daily_profits=challenge.daily_profits,
        max_drawdown=challenge.max_drawdown,
        current_drawdown=challenge.current_drawdown,
        largest_position_size=get_largest_position_size(challenge_id),
    )
    
    # Evaluate all rules
    results = rule_engine.evaluate_rules(context)
    
    # Generate comprehensive report
    return ComprehensiveEvaluation(
        challenge_id=challenge_id,
        evaluation_timestamp=datetime.utcnow(),
        rules_evaluated=len(results),
        rules_passed=len([r for r in results if r.passed]),
        violations=len([r for r in results if r.is_violation]),
        critical_violations=len([r for r in results if r.is_critical]),
        completion_status=assess_completion_status(challenge, results),
        performance_metrics=calculate_performance_metrics(challenge),
        recommendations=generate_recommendations(results),
        detailed_results=results,
    )
```

## Event-Driven Integration

### Domain Events Flow

```
Trading Update → Rule Evaluation → Violation Detection → Challenge State Change

1. TradingMetricsUpdated (Challenge Domain)
   ↓
2. RuleEvaluationTriggered (Rules Domain)
   ↓
3. RuleViolationDetected (Rules Domain)
   ↓
4. ChallengeStateChanged (Challenge Domain)
   ↓
5. ChallengeFailed/ChallengePassed (Challenge Domain)
```

### Event Handlers

```python
# Challenge domain event handlers
@event_handler(RuleViolationDetected)
async def handle_rule_violation_in_challenge(event: RuleViolationDetected):
    """Handle rule violations in challenge context."""
    
    challenge_id = event.context_snapshot.get("challenge_id")
    if not challenge_id:
        return
    
    challenge = challenge_repo.find_by_id(UUID(challenge_id))
    if not challenge:
        return
    
    # Process violation based on severity
    if event.severity == RuleSeverity.FATAL.value:
        challenge.fail_challenge(f"Fatal rule violation: {event.message}")
    elif event.severity == RuleSeverity.CRITICAL.value:
        # Apply trading restrictions
        await apply_trading_restrictions(challenge_id, event)
    
    challenge_repo.save(challenge)

@event_handler(ChallengePassed)
async def handle_challenge_passed(event: ChallengePassed):
    """Handle challenge completion."""
    
    # Deactivate rule engine or switch to funded account rules
    rule_engine = rule_engine_repo.find_by_challenge_id(event.aggregate_id)
    if rule_engine:
        # Switch to funded account rule set
        funded_rules = RuleSetFactory.create_funded_account_rules(
            Money(float(event.final_balance), "USD")
        )
        rule_engine.add_rule_set(funded_rules)
        rule_engine.activate_rule_set(funded_rules.name)
        rule_engine_repo.save(rule_engine)

@event_handler(ChallengeFailed)
async def handle_challenge_failed(event: ChallengeFailed):
    """Handle challenge failure."""
    
    # Deactivate rule engine
    rule_engine = rule_engine_repo.find_by_challenge_id(event.aggregate_id)
    if rule_engine:
        rule_engine.deactivate_rule_set()
        rule_engine_repo.save(rule_engine)
```

## API Integration Examples

### Challenge Management with Rules

```python
# Create challenge with automatic rule engine setup
POST /challenges
{
    "trader_id": "123e4567-e89b-12d3-a456-426614174000",
    "challenge_type": "PHASE_1",
    "initial_balance": 100000,
    "currency": "USD"
}

# Response includes rule engine information
{
    "challenge_id": "456e7890-e89b-12d3-a456-426614174001",
    "rule_engine_id": "789e0123-e89b-12d3-a456-426614174002",
    "active_rules": [
        "MAX_DAILY_DRAWDOWN",
        "MAX_TOTAL_DRAWDOWN", 
        "PROFIT_TARGET",
        "MIN_TRADING_DAYS",
        "CONSISTENCY_RULE"
    ]
}
```

### Real-Time Trading Updates

```python
# Update trading metrics with automatic rule evaluation
POST /challenges/{challenge_id}/trading-update
{
    "new_balance": 98500,
    "daily_pnl": -1500,
    "trade_count": 5,
    "largest_position_size": 10000
}

# Response includes rule evaluation results
{
    "challenge_state": "ACTIVE",
    "rule_violations": [
        {
            "rule_id": "MAX_DAILY_DRAWDOWN",
            "rule_name": "Maximum Daily Drawdown",
            "severity": "FATAL",
            "message": "Daily drawdown of 1.5% exceeds limit of 5%",
            "should_halt_trading": false
        }
    ],
    "risk_assessment": {
        "risk_level": "MEDIUM",
        "risk_score": 35,
        "recommendations": [
            "Monitor position sizes closely",
            "Consider reducing exposure"
        ]
    }
}
```

### Rule Violation Analysis

```python
# Analyze violation patterns for a challenge
POST /rules/violations/analyze
{
    "entity_id": "456e7890-e89b-12d3-a456-426614174001",
    "entity_type": "CHALLENGE",
    "time_window_hours": 24
}

# Response with detailed analysis
{
    "analysis": {
        "total_violations": 12,
        "recent_violations": 3,
        "violation_types": 4,
        "most_common_types": [
            {"type": "MAX_DAILY_DRAWDOWN", "count": 5},
            {"type": "MAX_TRADES_PER_DAY", "count": 4}
        ],
        "violation_rate_per_hour": 0.125
    },
    "recommendations": [
        "Reduce position sizes to control drawdown",
        "Limit trading frequency to avoid overtrading",
        "Focus on higher-quality trade setups"
    ],
    "requires_immediate_action": false
}
```

## Audit Trail and Compliance

### Complete Rule Evaluation History

```python
# Every rule evaluation is stored for audit purposes
class RuleEvaluationAuditTrail:
    """Complete audit trail of rule evaluations."""
    
    evaluation_id: UUID
    rule_engine_id: UUID
    challenge_id: UUID
    trader_id: UUID
    rule_id: str
    rule_name: str
    evaluation_timestamp: datetime
    context_snapshot: Dict[str, Any]  # Complete trading context
    rule_conditions: List[str]        # All condition evaluations
    result: bool                      # Pass/fail
    severity: RuleSeverity
    message: str
    details: Dict[str, Any]
    
    # Immutable - no updates allowed
    created_at: datetime
```

### Regulatory Compliance Features

```python
# Compliance reporting
async def generate_compliance_report(
    challenge_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> ComplianceReport:
    """Generate regulatory compliance report."""
    
    # Get all rule evaluations in period
    evaluations = rule_evaluation_repo.find_by_challenge_and_period(
        challenge_id, start_date, end_date
    )
    
    # Get all violations
    violations = [e for e in evaluations if not e.passed]
    
    # Generate compliance metrics
    return ComplianceReport(
        challenge_id=challenge_id,
        period_start=start_date,
        period_end=end_date,
        total_evaluations=len(evaluations),
        total_violations=len(violations),
        critical_violations=len([v for v in violations if v.is_critical]),
        auto_actions_taken=count_auto_actions(violations),
        manual_overrides=count_manual_overrides(challenge_id, start_date, end_date),
        audit_trail_complete=True,
        regulatory_compliance_status="COMPLIANT",
        detailed_violations=violations,
    )
```

## Performance Considerations

### Optimized Rule Evaluation

```python
# Efficient rule evaluation strategies
class RuleEvaluationOptimizer:
    """Optimize rule evaluation performance."""
    
    @staticmethod
    def get_evaluation_strategy(context_type: str) -> EvaluationStrategy:
        """Get optimized evaluation strategy based on context."""
        
        if context_type == "REAL_TIME":
            # Only evaluate critical rules for real-time
            return EvaluationStrategy(
                rule_types=[
                    RuleType.MAX_DAILY_DRAWDOWN,
                    RuleType.MAX_TOTAL_DRAWDOWN,
                ],
                tags=["critical", "realtime"],
                max_evaluation_time_ms=100,
            )
        
        elif context_type == "BATCH":
            # Comprehensive evaluation for batch processing
            return EvaluationStrategy(
                rule_types=None,  # All rules
                tags=None,        # All tags
                max_evaluation_time_ms=5000,
            )
        
        elif context_type == "PERIODIC":
            # Balanced evaluation for periodic checks
            return EvaluationStrategy(
                rule_types=[
                    RuleType.MAX_DAILY_DRAWDOWN,
                    RuleType.MAX_TOTAL_DRAWDOWN,
                    RuleType.PROFIT_TARGET,
                    RuleType.MIN_TRADING_DAYS,
                ],
                tags=["important"],
                max_evaluation_time_ms=1000,
            )
```

## Summary

The Rules Engine provides a comprehensive, configurable, and auditable system for managing prop firm challenge rules. Key benefits:

1. **Seamless Integration**: Automatic setup and integration with challenge lifecycle
2. **Real-Time Monitoring**: Immediate rule evaluation and violation detection
3. **Configurable Rules**: Different rule sets for different challenge types
4. **Event-Driven**: Automatic challenge state transitions based on rule violations
5. **Complete Audit Trail**: Full regulatory compliance with immutable audit logs
6. **Performance Optimized**: Efficient evaluation strategies for different use cases
7. **Extensible**: Easy to add new rule types and evaluation logic

The integration ensures that all trading activity is continuously monitored against configurable rules, with automatic enforcement of risk limits and challenge requirements, while maintaining complete auditability for regulatory compliance.