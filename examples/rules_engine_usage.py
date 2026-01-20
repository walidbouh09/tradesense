"""
Rules Engine Usage Examples

This file demonstrates how to use the Rules Engine for prop firm challenges,
including rule creation, evaluation, and integration with the Challenge Engine.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domains.rules.domain.entities import RuleEngine, RuleViolationTracker
from src.domains.rules.domain.services import (
    RuleContextBuilder,
    RuleEngineIntegrationService,
    RuleSetFactory,
    RuleViolationAnalyzer,
)
from src.domains.rules.domain.value_objects import (
    RuleDefinition,
    RuleSet,
    RuleTemplates,
    RuleType,
    RuleSeverity,
)
from src.domains.rules.application.services import (
    RiskEngineIntegrationService,
    RuleEvaluationService,
    RuleViolationService,
)
from src.shared.utils.money import Money
from src.shared.events.event_bus import InMemoryEventBus


async def example_1_create_challenge_rule_engine():
    """Example 1: Create a rule engine for a Phase 1 challenge."""
    
    print("=== Example 1: Create Challenge Rule Engine ===")
    
    # Challenge parameters
    challenge_id = uuid4()
    initial_balance = Money(100000, "USD")
    challenge_type = "PHASE_1"
    
    # Create rule engine using domain service
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge_id,
        challenge_type=challenge_type,
        initial_balance=initial_balance,
    )
    
    print(f"Created rule engine: {rule_engine.name}")
    print(f"Active rule set: {rule_engine.active_rule_set_name}")
    print(f"Number of rules: {len(rule_engine.active_rule_set.rules) if rule_engine.active_rule_set else 0}")
    
    # Display active rules
    if rule_engine.active_rule_set:
        print("\nActive Rules:")
        for rule in rule_engine.active_rule_set.rules:
            print(f"  - {rule.name} ({rule.severity.value})")
    
    return rule_engine


async def example_2_evaluate_trading_scenario():
    """Example 2: Evaluate rules against a trading scenario."""
    
    print("\n=== Example 2: Evaluate Trading Scenario ===")
    
    # Create rule engine
    challenge_id = uuid4()
    trader_id = uuid4()
    initial_balance = Money(100000, "USD")
    
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge_id,
        challenge_type="PHASE_1",
        initial_balance=initial_balance,
    )
    
    # Simulate trading scenario - trader has lost 6% in one day (exceeds 5% limit)
    current_balance = Money(94000, "USD")  # 6% loss
    daily_pnl = Money(-6000, "USD")
    total_pnl = Money(-6000, "USD")
    
    # Build evaluation context
    context = RuleContextBuilder.build_challenge_context(
        challenge_id=challenge_id,
        trader_id=trader_id,
        initial_balance=initial_balance,
        current_balance=current_balance,
        daily_pnl=daily_pnl,
        total_pnl=total_pnl,
        trading_days=1,
        daily_trade_count=10,
        total_trades=10,
        daily_profits=[daily_pnl],
        max_drawdown=Money(6000, "USD"),
        current_drawdown=Money(6000, "USD"),
        largest_position_size=Money(15000, "USD"),
    )
    
    # Evaluate rules
    results = rule_engine.evaluate_rules(context)
    
    print(f"Evaluated {len(results)} rules")
    print(f"Rules passed: {len([r for r in results if r.passed])}")
    print(f"Violations detected: {len([r for r in results if r.is_violation])}")
    
    # Display violations
    violations = [r for r in results if r.is_violation]
    if violations:
        print("\nRule Violations:")
        for violation in violations:
            print(f"  - {violation.rule_name} ({violation.severity.value})")
            print(f"    Message: {violation.message}")
            print(f"    Critical: {violation.is_critical}")
    
    # Check if challenge should be failed
    fatal_violations = [r for r in violations if r.severity == RuleSeverity.FATAL]
    if fatal_violations:
        print(f"\n⚠️  CHALLENGE SHOULD BE FAILED due to {len(fatal_violations)} fatal violations")
    
    return rule_engine, results


async def example_3_custom_rule_creation():
    """Example 3: Create custom rules using templates."""
    
    print("\n=== Example 3: Custom Rule Creation ===")
    
    # Create custom rules using templates
    rules = [
        # Stricter daily drawdown limit (3% instead of 5%)
        RuleTemplates.max_daily_drawdown(Decimal("3.0")),
        
        # Higher profit target (12% instead of 8%)
        RuleTemplates.profit_target(Money(12000, "USD")),
        
        # More restrictive trading activity
        RuleTemplates.max_trades_per_day(50),  # Max 50 trades per day
        
        # Stricter consistency rule
        RuleTemplates.consistency_rule(Decimal("30")),  # Max 30% from single day
        
        # Minimum trading days requirement
        RuleTemplates.min_trading_days(10),  # Must trade for 10 days
    ]
    
    # Create custom rule set
    custom_rule_set = RuleSet(
        name="Strict_Phase1",
        description="Stricter Phase 1 rules for experienced traders",
        rules=rules,
        tags=["strict", "experienced", "phase1"],
        version="1.0",
    )
    
    # Create rule engine with custom rules
    rule_engine = RuleEngine(
        name="Strict_Challenge_Engine",
        description="Rule engine with stricter requirements",
        rule_sets=[custom_rule_set],
    )
    
    rule_engine.activate_rule_set(custom_rule_set.name)
    
    print(f"Created custom rule set: {custom_rule_set.name}")
    print(f"Number of rules: {len(custom_rule_set.rules)}")
    
    # Display custom rules
    print("\nCustom Rules:")
    for rule in custom_rule_set.rules:
        print(f"  - {rule.name}")
        print(f"    Type: {rule.rule_type.value}")
        print(f"    Severity: {rule.severity.value}")
        
        # Display rule parameters
        if rule.parameters:
            print("    Parameters:")
            for param in rule.parameters:
                print(f"      {param.name}: {param.value}")
    
    return rule_engine


async def example_4_risk_assessment():
    """Example 4: Perform risk assessment using rules engine."""
    
    print("\n=== Example 4: Risk Assessment ===")
    
    # Create rule engine
    challenge_id = uuid4()
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge_id,
        challenge_type="PHASE_1",
        initial_balance=Money(100000, "USD"),
    )
    
    # Create risk assessment service
    event_bus = InMemoryEventBus()
    risk_service = RiskEngineIntegrationService(event_bus)
    
    # Simulate high-risk trading scenario
    trading_context = {
        "challenge_id": str(challenge_id),
        "trader_id": str(uuid4()),
        "initial_balance": 100000,
        "current_balance": 96000,  # 4% loss
        "daily_pnl": -4000,        # 4% daily loss
        "total_pnl": -4000,
        "trading_days": 1,
        "daily_trade_count": 80,   # High trading activity
        "total_trades": 80,
        "daily_drawdown_percent": 4.0,
        "total_drawdown_percent": 4.0,
        "largest_position_size": 20000,  # 20% position size
        "position_size_percent": 20.0,
    }
    
    # Perform risk assessment
    risk_results = await risk_service.evaluate_risk_rules(rule_engine, trading_context)
    
    print("Risk Assessment Results:")
    print(f"  Risk Score: {risk_results['risk_assessment']['risk_score']}/100")
    print(f"  Risk Level: {risk_results['risk_assessment']['risk_level']}")
    print(f"  Should Halt Trading: {risk_results['risk_assessment']['should_halt_trading']}")
    print(f"  Should Reduce Exposure: {risk_results['risk_assessment']['should_reduce_exposure']}")
    print(f"  Should Warn Trader: {risk_results['risk_assessment']['should_warn_trader']}")
    
    # Display risk violations
    if risk_results['risk_violations']:
        print("\nRisk Violations:")
        for violation in risk_results['risk_violations']:
            print(f"  - {violation['rule_name']} ({violation['severity']})")
            print(f"    Impact: {violation['impact']}")
    
    # Display recommended actions
    if risk_results['recommended_actions']:
        print("\nRecommended Actions:")
        for action in risk_results['recommended_actions']:
            print(f"  - {action}")
    
    return risk_results


async def example_5_violation_tracking():
    """Example 5: Track and analyze rule violations over time."""
    
    print("\n=== Example 5: Violation Tracking ===")
    
    # Create violation tracker
    challenge_id = uuid4()
    tracker = RuleViolationTracker(
        entity_id=challenge_id,
        entity_type="CHALLENGE",
    )
    
    # Create rule engine and simulate multiple violations
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge_id,
        challenge_type="PHASE_1",
        initial_balance=Money(100000, "USD"),
    )
    
    # Simulate trading scenarios with violations
    scenarios = [
        {
            "day": 1,
            "current_balance": 96000,
            "daily_pnl": -4000,
            "description": "High daily loss"
        },
        {
            "day": 2,
            "current_balance": 95000,
            "daily_pnl": -1000,
            "description": "Continued losses"
        },
        {
            "day": 3,
            "current_balance": 89000,
            "daily_pnl": -6000,
            "description": "Severe daily loss (exceeds limit)"
        },
    ]
    
    all_violations = []
    
    for scenario in scenarios:
        print(f"\nDay {scenario['day']}: {scenario['description']}")
        
        # Build context
        context = RuleContextBuilder.build_challenge_context(
            challenge_id=challenge_id,
            trader_id=uuid4(),
            initial_balance=Money(100000, "USD"),
            current_balance=Money(scenario["current_balance"], "USD"),
            daily_pnl=Money(scenario["daily_pnl"], "USD"),
            total_pnl=Money(scenario["current_balance"] - 100000, "USD"),
            trading_days=scenario["day"],
            daily_trade_count=10,
            total_trades=scenario["day"] * 10,
            daily_profits=[Money(scenario["daily_pnl"], "USD")],
            max_drawdown=Money(100000 - scenario["current_balance"], "USD"),
            current_drawdown=Money(abs(scenario["daily_pnl"]), "USD"),
            largest_position_size=Money(15000, "USD"),
        )
        
        # Evaluate rules
        results = rule_engine.evaluate_rules(context)
        violations = [r for r in results if r.is_violation]
        
        # Track violations
        for violation in violations:
            tracker.record_violation(violation)
            all_violations.append(violation)
        
        print(f"  Violations detected: {len(violations)}")
    
    # Analyze violation patterns
    analysis = RuleViolationAnalyzer.analyze_violation_patterns(all_violations)
    
    print(f"\nViolation Analysis:")
    print(f"  Total violations: {tracker.total_violations}")
    print(f"  Unique rules violated: {tracker.unique_rules_violated}")
    print(f"  First violation: {tracker.first_violation_at}")
    print(f"  Last violation: {tracker.last_violation_at}")
    
    # Most violated rules
    most_violated = tracker.get_most_violated_rules(3)
    if most_violated:
        print("\nMost Violated Rules:")
        for rule_id, count in most_violated:
            print(f"  - {rule_id}: {count} violations")
    
    # Pattern analysis
    print(f"\nPattern Analysis:")
    print(f"  Violation rate per hour: {analysis.get('violation_rate_per_hour', 0):.2f}")
    print(f"  Critical violations: {analysis.get('critical_violations', 0)}")
    
    # Recommendations
    recommendations = RuleViolationAnalyzer.get_violation_recommendations(all_violations)
    if recommendations:
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
    
    return tracker, analysis


async def example_6_rule_set_factory():
    """Example 6: Use rule set factory for different challenge types."""
    
    print("\n=== Example 6: Rule Set Factory ===")
    
    initial_balance = Money(100000, "USD")
    
    # Create different rule sets for different challenge phases
    phase1_rules = RuleSetFactory.create_phase1_rules(
        initial_balance=initial_balance,
        profit_target_percent=Decimal("8"),
        max_daily_drawdown_percent=Decimal("5"),
        max_total_drawdown_percent=Decimal("10"),
        min_trading_days=5,
        max_trades_per_day=100,
    )
    
    phase2_rules = RuleSetFactory.create_phase2_rules(
        initial_balance=initial_balance,
        profit_target_percent=Decimal("5"),
        max_daily_drawdown_percent=Decimal("5"),
        max_total_drawdown_percent=Decimal("10"),
        min_trading_days=5,
    )
    
    funded_rules = RuleSetFactory.create_funded_account_rules(
        account_balance=initial_balance,
        max_daily_drawdown_percent=Decimal("5"),
        max_total_drawdown_percent=Decimal("10"),
    )
    
    # Display rule sets
    rule_sets = [
        ("Phase 1", phase1_rules),
        ("Phase 2", phase2_rules),
        ("Funded Account", funded_rules),
    ]
    
    for name, rule_set in rule_sets:
        print(f"\n{name} Rules ({rule_set.name}):")
        print(f"  Description: {rule_set.description}")
        print(f"  Number of rules: {len(rule_set.rules)}")
        print(f"  Tags: {', '.join(rule_set.tags)}")
        
        print("  Rules:")
        for rule in rule_set.rules:
            print(f"    - {rule.name} ({rule.severity.value})")
    
    return phase1_rules, phase2_rules, funded_rules


async def example_7_comprehensive_challenge_evaluation():
    """Example 7: Comprehensive challenge evaluation workflow."""
    
    print("\n=== Example 7: Comprehensive Challenge Evaluation ===")
    
    # Setup
    challenge_id = uuid4()
    trader_id = uuid4()
    initial_balance = Money(100000, "USD")
    
    # Create rule engine
    rule_engine = RuleEngineIntegrationService.create_challenge_rule_engine(
        challenge_id=challenge_id,
        challenge_type="PHASE_1",
        initial_balance=initial_balance,
    )
    
    # Create application services
    event_bus = InMemoryEventBus()
    evaluation_service = RuleEvaluationService(event_bus)
    
    # Simulate successful challenge progression
    trading_scenarios = [
        # Week 1: Steady progress
        {"day": 1, "balance": 101000, "daily_pnl": 1000, "trades": 5},
        {"day": 2, "balance": 102500, "daily_pnl": 1500, "trades": 8},
        {"day": 3, "balance": 103200, "daily_pnl": 700, "trades": 6},
        {"day": 4, "balance": 104800, "daily_pnl": 1600, "trades": 10},
        {"day": 5, "balance": 105500, "daily_pnl": 700, "trades": 4},
        
        # Week 2: Reaching profit target
        {"day": 6, "balance": 106200, "daily_pnl": 700, "trades": 7},
        {"day": 7, "balance": 107800, "daily_pnl": 1600, "trades": 9},
        {"day": 8, "balance": 108000, "daily_pnl": 200, "trades": 3},  # Profit target reached (8%)
    ]
    
    print("Simulating challenge progression...")
    
    for scenario in trading_scenarios:
        print(f"\nDay {scenario['day']}:")
        
        # Build challenge data
        challenge_data = {
            "challenge_id": challenge_id,
            "trader_id": trader_id,
            "initial_balance": initial_balance,
            "current_balance": Money(scenario["balance"], "USD"),
            "daily_pnl": Money(scenario["daily_pnl"], "USD"),
            "total_pnl": Money(scenario["balance"] - 100000, "USD"),
            "trading_days": scenario["day"],
            "daily_trade_count": scenario["trades"],
            "total_trades": sum(s["trades"] for s in trading_scenarios[:scenario["day"]]),
            "daily_profits": [Money(s["daily_pnl"], "USD") for s in trading_scenarios[:scenario["day"]]],
            "max_drawdown": Money(0, "USD"),  # No drawdown in this scenario
            "current_drawdown": Money(0, "USD"),
            "largest_position_size": Money(10000, "USD"),
        }
        
        # Evaluate challenge rules
        evaluation_results = await evaluation_service.evaluate_challenge_rules(
            challenge_id=challenge_id,
            rule_engine=rule_engine,
            challenge_data=challenge_data,
        )
        
        # Display results
        summary = evaluation_results["evaluation_summary"]
        print(f"  Balance: ${scenario['balance']:,}")
        print(f"  Daily P&L: ${scenario['daily_pnl']:,}")
        print(f"  Total P&L: ${scenario['balance'] - 100000:,}")
        print(f"  Rules evaluated: {summary['rules_evaluated']}")
        print(f"  Rules passed: {summary['rules_passed']}")
        print(f"  Violations: {summary['violations_detected']}")
        
        # Check if challenge should be completed
        if evaluation_results["should_halt_trading"]:
            print("  ⚠️  CHALLENGE FAILED - Trading halted")
            break
        
        # Check profit target achievement
        profit_percent = (scenario["balance"] - 100000) / 100000 * 100
        if profit_percent >= 8 and scenario["day"] >= 5:
            print(f"  ✅ CHALLENGE PASSED - Profit target achieved ({profit_percent:.1f}%)")
            break
    
    # Final evaluation summary
    print(f"\nFinal Challenge Status:")
    print(f"  Total evaluations performed: {rule_engine.evaluation_count}")
    print(f"  Active violations: {len(rule_engine.get_active_violations())}")
    print(f"  Critical violations: {len(rule_engine.get_critical_violations())}")
    
    return rule_engine, evaluation_results


async def main():
    """Run all examples."""
    
    print("🚀 Rules Engine Usage Examples")
    print("=" * 50)
    
    try:
        # Run examples
        await example_1_create_challenge_rule_engine()
        await example_2_evaluate_trading_scenario()
        await example_3_custom_rule_creation()
        await example_4_risk_assessment()
        await example_5_violation_tracking()
        await example_6_rule_set_factory()
        await example_7_comprehensive_challenge_evaluation()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())