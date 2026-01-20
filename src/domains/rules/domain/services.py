"""Rules engine domain services."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.utils.money import Money
from .entities import RuleEngine, RuleViolationTracker
from .value_objects import (
    RuleDefinition,
    RuleEvaluationResult,
    RuleSet,
    RuleSeverity,
    RuleTemplates,
    RuleType,
)


class RuleContextBuilder:
    """Service for building rule evaluation context from trading data."""
    
    @staticmethod
    def build_challenge_context(
        challenge_id: UUID,
        trader_id: UUID,
        initial_balance: Money,
        current_balance: Money,
        daily_pnl: Money,
        total_pnl: Money,
        trading_days: int,
        daily_trade_count: int,
        total_trades: int,
        daily_profits: List[Money],
        max_drawdown: Money,
        current_drawdown: Money,
        largest_position_size: Money,
        additional_data: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """Build context for challenge rule evaluation."""
        
        # Calculate derived metrics
        daily_drawdown_percent = (
            abs(daily_pnl.amount) / current_balance.amount * 100
            if daily_pnl.amount < 0 and current_balance.amount > 0
            else Decimal("0")
        )
        
        total_drawdown_percent = (
            max_drawdown.amount / initial_balance.amount * 100
            if max_drawdown.amount > 0 and initial_balance.amount > 0
            else Decimal("0")
        )
        
        profit_percent = (
            total_pnl.amount / initial_balance.amount * 100
            if initial_balance.amount > 0
            else Decimal("0")
        )
        
        # Calculate consistency metrics
        max_single_day_profit = Money.zero(initial_balance.currency)
        if daily_profits:
            max_single_day_profit = max(daily_profits, key=lambda x: x.amount)
        
        max_single_day_profit_percent = Decimal("0")
        if total_pnl.amount > 0 and max_single_day_profit.amount > 0:
            max_single_day_profit_percent = (
                max_single_day_profit.amount / total_pnl.amount * 100
            )
        
        # Build context dictionary
        context = {
            # Identifiers
            "challenge_id": str(challenge_id),
            "trader_id": str(trader_id),
            
            # Balance and P&L
            "initial_balance": initial_balance.amount,
            "current_balance": current_balance.amount,
            "daily_pnl": daily_pnl.amount,
            "total_pnl": total_pnl.amount,
            "total_profit": max(Decimal("0"), total_pnl.amount),
            "total_loss": abs(min(Decimal("0"), total_pnl.amount)),
            
            # Percentages
            "daily_drawdown_percent": daily_drawdown_percent,
            "total_drawdown_percent": total_drawdown_percent,
            "profit_percent": profit_percent,
            "max_single_day_profit_percent": max_single_day_profit_percent,
            
            # Trading activity
            "trading_days": trading_days,
            "daily_trade_count": daily_trade_count,
            "total_trades": total_trades,
            "avg_trades_per_day": (
                total_trades / trading_days if trading_days > 0 else 0
            ),
            
            # Risk metrics
            "max_drawdown": max_drawdown.amount,
            "current_drawdown": current_drawdown.amount,
            "largest_position_size": largest_position_size.amount,
            "position_size_percent": (
                largest_position_size.amount / current_balance.amount * 100
                if current_balance.amount > 0
                else Decimal("0")
            ),
            
            # Time-based
            "evaluation_timestamp": datetime.utcnow().isoformat(),
            "evaluation_date": datetime.utcnow().date().isoformat(),
        }
        
        # Add additional data if provided
        if additional_data:
            context.update(additional_data)
        
        return context


class RuleSetFactory:
    """Factory for creating standard rule sets for prop firm challenges."""
    
    @staticmethod
    def create_phase1_rules(
        initial_balance: Money,
        profit_target_percent: Decimal = Decimal("8"),
        max_daily_drawdown_percent: Decimal = Decimal("5"),
        max_total_drawdown_percent: Decimal = Decimal("10"),
        min_trading_days: int = 5,
        max_trades_per_day: int = 100,
    ) -> RuleSet:
        """Create Phase 1 challenge rule set."""
        
        profit_target_amount = Money(
            initial_balance.amount * (profit_target_percent / 100),
            initial_balance.currency
        )
        
        rules = [
            RuleTemplates.max_daily_drawdown(max_daily_drawdown_percent),
            RuleTemplates.max_total_drawdown(max_total_drawdown_percent),
            RuleTemplates.profit_target(profit_target_amount),
            RuleTemplates.min_trading_days(min_trading_days),
            RuleTemplates.max_trades_per_day(max_trades_per_day),
            RuleTemplates.consistency_rule(Decimal("50")),  # 50% max from single day
        ]
        
        return RuleSet(
            name="Phase1_Standard",
            description=f"Standard Phase 1 rules for {initial_balance} account",
            rules=rules,
            tags=["phase1", "standard", "evaluation"],
            version="1.0",
        )
    
    @staticmethod
    def create_phase2_rules(
        initial_balance: Money,
        profit_target_percent: Decimal = Decimal("5"),
        max_daily_drawdown_percent: Decimal = Decimal("5"),
        max_total_drawdown_percent: Decimal = Decimal("10"),
        min_trading_days: int = 5,
    ) -> RuleSet:
        """Create Phase 2 (verification) challenge rule set."""
        
        profit_target_amount = Money(
            initial_balance.amount * (profit_target_percent / 100),
            initial_balance.currency
        )
        
        rules = [
            RuleTemplates.max_daily_drawdown(max_daily_drawdown_percent),
            RuleTemplates.max_total_drawdown(max_total_drawdown_percent),
            RuleTemplates.profit_target(profit_target_amount),
            RuleTemplates.min_trading_days(min_trading_days),
            RuleTemplates.consistency_rule(Decimal("40")),  # Stricter consistency
        ]
        
        return RuleSet(
            name="Phase2_Verification",
            description=f"Phase 2 verification rules for {initial_balance} account",
            rules=rules,
            tags=["phase2", "verification", "funded"],
            version="1.0",
        )
    
    @staticmethod
    def create_funded_account_rules(
        account_balance: Money,
        max_daily_drawdown_percent: Decimal = Decimal("5"),
        max_total_drawdown_percent: Decimal = Decimal("10"),
    ) -> RuleSet:
        """Create funded account rule set."""
        
        rules = [
            RuleTemplates.max_daily_drawdown(max_daily_drawdown_percent),
            RuleTemplates.max_total_drawdown(max_total_drawdown_percent),
        ]
        
        return RuleSet(
            name="Funded_Account",
            description=f"Funded account rules for {account_balance} account",
            rules=rules,
            tags=["funded", "live", "trading"],
            version="1.0",
        )


class RuleViolationAnalyzer:
    """Service for analyzing rule violations and providing insights."""
    
    @staticmethod
    def analyze_violation_patterns(
        violations: List[RuleEvaluationResult],
        time_window_hours: int = 24,
    ) -> Dict[str, any]:
        """Analyze patterns in rule violations."""
        
        if not violations:
            return {"pattern_analysis": "No violations to analyze"}
        
        # Group violations by rule type
        violations_by_type = {}
        for violation in violations:
            rule_type = violation.details.get("rule_type", "unknown")
            if rule_type not in violations_by_type:
                violations_by_type[rule_type] = []
            violations_by_type[rule_type].append(violation)
        
        # Analyze severity distribution
        severity_counts = {}
        for violation in violations:
            severity = violation.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Find most common violation types
        most_common_types = sorted(
            violations_by_type.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        # Calculate violation frequency
        recent_violations = [
            v for v in violations
            if datetime.fromisoformat(v.evaluation_timestamp) > 
            datetime.utcnow() - timedelta(hours=time_window_hours)
        ]
        
        return {
            "total_violations": len(violations),
            "recent_violations": len(recent_violations),
            "violation_types": len(violations_by_type),
            "severity_distribution": severity_counts,
            "most_common_types": [
                {"type": type_name, "count": len(type_violations)}
                for type_name, type_violations in most_common_types[:5]
            ],
            "violation_rate_per_hour": len(recent_violations) / max(1, time_window_hours),
            "critical_violations": len([
                v for v in violations 
                if v.severity in [RuleSeverity.CRITICAL, RuleSeverity.FATAL]
            ]),
        }
    
    @staticmethod
    def get_violation_recommendations(
        violations: List[RuleEvaluationResult],
    ) -> List[str]:
        """Get recommendations based on violation patterns."""
        
        recommendations = []
        
        if not violations:
            return ["No violations detected. Continue following current trading strategy."]
        
        # Analyze violation types
        drawdown_violations = [
            v for v in violations
            if "drawdown" in v.rule_name.lower()
        ]
        
        trading_activity_violations = [
            v for v in violations
            if "trades" in v.rule_name.lower()
        ]
        
        consistency_violations = [
            v for v in violations
            if "consistency" in v.rule_name.lower()
        ]
        
        # Generate specific recommendations
        if drawdown_violations:
            recommendations.append(
                "Reduce position sizes and implement stricter stop-loss orders to control drawdown."
            )
        
        if trading_activity_violations:
            recommendations.append(
                "Reduce trading frequency and focus on higher-quality setups."
            )
        
        if consistency_violations:
            recommendations.append(
                "Avoid over-concentration of profits in single trading sessions. "
                "Distribute profits more evenly across trading days."
            )
        
        # Check for fatal violations
        fatal_violations = [v for v in violations if v.severity == RuleSeverity.FATAL]
        if fatal_violations:
            recommendations.insert(0, 
                "CRITICAL: Fatal rule violations detected. Trading should be halted immediately."
            )
        
        return recommendations


class RuleEngineIntegrationService:
    """Service for integrating rules engine with other domain services."""
    
    @staticmethod
    def create_challenge_rule_engine(
        challenge_id: UUID,
        challenge_type: str,
        initial_balance: Money,
    ) -> RuleEngine:
        """Create rule engine for a specific challenge."""
        
        engine = RuleEngine(
            name=f"Challenge_{challenge_id}",
            description=f"{challenge_type} challenge rule engine",
        )
        
        # Add appropriate rule set based on challenge type
        if challenge_type == "PHASE_1":
            rule_set = RuleSetFactory.create_phase1_rules(initial_balance)
        elif challenge_type == "PHASE_2":
            rule_set = RuleSetFactory.create_phase2_rules(initial_balance)
        elif challenge_type == "FUNDED":
            rule_set = RuleSetFactory.create_funded_account_rules(initial_balance)
        else:
            # Default to Phase 1 rules
            rule_set = RuleSetFactory.create_phase1_rules(initial_balance)
        
        engine.add_rule_set(rule_set)
        engine.activate_rule_set(rule_set.name)
        
        return engine
    
    @staticmethod
    def evaluate_challenge_rules(
        rule_engine: RuleEngine,
        challenge_data: Dict[str, any],
    ) -> Dict[str, any]:
        """Evaluate challenge rules and return comprehensive results."""
        
        # Build evaluation context
        context = RuleContextBuilder.build_challenge_context(**challenge_data)
        
        # Evaluate rules
        results = rule_engine.evaluate_rules(context)
        
        # Analyze results
        violations = [r for r in results if r.is_violation]
        critical_violations = [r for r in violations if r.is_critical]
        
        # Get recommendations
        recommendations = RuleViolationAnalyzer.get_violation_recommendations(violations)
        
        # Get violation analysis
        analysis = RuleViolationAnalyzer.analyze_violation_patterns(violations)
        
        return {
            "evaluation_summary": {
                "rules_evaluated": len(results),
                "rules_passed": len([r for r in results if r.passed]),
                "violations_detected": len(violations),
                "critical_violations": len(critical_violations),
                "fatal_violations": len([r for r in violations if r.severity == RuleSeverity.FATAL]),
            },
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity.value,
                    "message": v.message,
                    "details": v.details,
                }
                for v in violations
            ],
            "recommendations": recommendations,
            "violation_analysis": analysis,
            "should_halt_trading": rule_engine.has_fatal_violations(),
            "context_snapshot": context,
        }