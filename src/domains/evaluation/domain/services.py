"""Evaluation domain services."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError
from ....shared.utils.money import Money
from .entities import Challenge
from .value_objects import (
    ChallengeParameters,
    ChallengeState,
    ChallengeType,
    RiskRule,
    RiskViolation,
    TradingMetrics,
)


class ChallengeEvaluationService:
    """Domain service for challenge evaluation logic."""
    
    @staticmethod
    def evaluate_challenge_eligibility(
        trader_id: UUID,
        existing_challenges: List[Challenge],
        requested_challenge_type: ChallengeType,
    ) -> None:
        """Evaluate if trader is eligible for a new challenge."""
        # Check for active challenges
        active_challenges = [
            c for c in existing_challenges 
            if c.state == ChallengeState.ACTIVE
        ]
        
        if active_challenges:
            raise BusinessRuleViolationError(
                "Trader already has an active challenge"
            )
        
        # Check for recent failures (cooling off period)
        recent_failures = [
            c for c in existing_challenges
            if c.state == ChallengeState.FAILED and
            c.completed_at and
            c.completed_at > datetime.utcnow() - timedelta(days=30)
        ]
        
        if len(recent_failures) >= 3:
            raise BusinessRuleViolationError(
                "Too many recent failures. Please wait before starting a new challenge."
            )
        
        # Check for existing funding (no multiple funding rule)
        funded_challenges = [
            c for c in existing_challenges
            if c.state == ChallengeState.FUNDED and c.funded_amount
        ]
        
        if funded_challenges:
            raise BusinessRuleViolationError(
                "Trader already has funded account. Multiple funding not allowed."
            )
    
    @staticmethod
    def calculate_risk_score(
        challenge: Challenge,
        recent_trading_data: Dict,
    ) -> int:
        """Calculate risk score based on trading behavior."""
        risk_score = 0
        
        # Base score from current metrics
        if challenge.total_pnl.amount < 0:
            loss_percent = abs(challenge.total_pnl.amount) / challenge.parameters.initial_balance.amount * 100
            risk_score += int(loss_percent * 2)  # 2 points per percent loss
        
        # Risk from violations
        critical_violations = [v for v in challenge.risk_violations if v.is_critical]
        risk_score += len(critical_violations) * 25
        
        # Risk from trading pattern
        if challenge.trading_days > 0:
            avg_daily_trades = challenge._total_trades / challenge.trading_days
            if avg_daily_trades > 50:  # Excessive trading
                risk_score += 20
        
        # Risk from drawdown
        if challenge._max_drawdown.amount > 0:
            drawdown_percent = challenge._max_drawdown.amount / challenge.parameters.initial_balance.amount * 100
            if drawdown_percent > 5:
                risk_score += int(drawdown_percent * 3)
        
        return min(risk_score, 100)  # Cap at 100
    
    @staticmethod
    def recommend_challenge_parameters(
        trader_experience_level: str,
        previous_challenges: List[Challenge],
        requested_balance: Money,
    ) -> ChallengeParameters:
        """Recommend challenge parameters based on trader profile."""
        # Determine challenge type based on experience
        if trader_experience_level == "BEGINNER":
            challenge_type = ChallengeType.PHASE_1
            max_daily_loss_percent = 5.0
            max_total_loss_percent = 10.0
        elif trader_experience_level == "INTERMEDIATE":
            challenge_type = ChallengeType.EXPRESS
            max_daily_loss_percent = 4.0
            max_total_loss_percent = 8.0
        else:  # ADVANCED
            challenge_type = ChallengeType.EXPRESS
            max_daily_loss_percent = 3.0
            max_total_loss_percent = 6.0
        
        # Adjust based on previous performance
        failed_challenges = [c for c in previous_challenges if c.state == ChallengeState.FAILED]
        if len(failed_challenges) > 2:
            # More restrictive rules for traders with multiple failures
            max_daily_loss_percent *= 0.8
            max_total_loss_percent *= 0.8
        
        # Create risk rules
        risk_rules = [
            RiskRule(
                name="Daily Loss Limit",
                description=f"Maximum daily loss of {max_daily_loss_percent}%",
                max_daily_loss_percent=max_daily_loss_percent,
            ),
            RiskRule(
                name="Total Loss Limit",
                description=f"Maximum total loss of {max_total_loss_percent}%",
                max_total_loss_percent=max_total_loss_percent,
            ),
            RiskRule(
                name="Minimum Trading Days",
                description="Must trade for at least 5 days",
                min_trading_days=5,
            ),
        ]
        
        # Create profit target (typically 8-10% of balance)
        from .value_objects import ProfitTarget
        profit_target = ProfitTarget(
            target_amount=Money(requested_balance.amount * 0.08, requested_balance.currency),
            consistency_rule=50.0,  # No single day > 50% of total profit
        )
        
        return ChallengeParameters(
            challenge_type=challenge_type,
            initial_balance=requested_balance,
            profit_target=profit_target,
            risk_rules=risk_rules,
            min_trading_days=5,
        )


class RiskMonitoringService:
    """Domain service for real-time risk monitoring."""
    
    @staticmethod
    def check_real_time_violations(
        challenge: Challenge,
        current_position_size: Money,
        current_daily_pnl: Money,
    ) -> List[RiskViolation]:
        """Check for real-time risk violations."""
        violations = []
        
        # Check position size limits
        max_position_size = challenge.parameters.max_position_size
        if current_position_size > max_position_size:
            violations.append(
                RiskViolation(
                    rule_name="Position Size Limit",
                    violation_type="position_size",
                    description=f"Position size exceeds maximum allowed",
                    severity="HIGH",
                    current_value=str(current_position_size.amount),
                    limit_value=str(max_position_size.amount),
                    timestamp=datetime.utcnow().isoformat(),
                )
            )
        
        # Check daily loss in real-time
        if current_daily_pnl.amount < 0:
            for rule in challenge.parameters.risk_rules:
                if not rule.validate_daily_loss(current_daily_pnl, challenge.current_balance):
                    violations.append(
                        RiskViolation(
                            rule_name=rule.name,
                            violation_type="daily_loss_realtime",
                            description=f"Real-time daily loss violation: {rule.description}",
                            severity="CRITICAL",
                            current_value=str(abs(current_daily_pnl.amount)),
                            limit_value=str(rule.max_daily_loss.amount if rule.max_daily_loss else rule.max_daily_loss_percent),
                            timestamp=datetime.utcnow().isoformat(),
                        )
                    )
        
        return violations
    
    @staticmethod
    def should_halt_trading(violations: List[RiskViolation]) -> bool:
        """Determine if trading should be halted based on violations."""
        return any(v.is_critical for v in violations)
    
    @staticmethod
    def calculate_remaining_risk_budget(
        challenge: Challenge,
    ) -> Dict[str, Money]:
        """Calculate remaining risk budget for the challenge."""
        budget = {}
        
        for rule in challenge.parameters.risk_rules:
            if rule.max_daily_loss:
                current_daily_loss = abs(challenge._daily_pnl.amount) if challenge._daily_pnl.amount < 0 else 0
                remaining_daily = rule.max_daily_loss.amount - current_daily_loss
                budget["daily_loss_remaining"] = Money(max(0, remaining_daily), rule.max_daily_loss.currency)
            
            if rule.max_total_loss:
                current_total_loss = abs(challenge.total_pnl.amount) if challenge.total_pnl.amount < 0 else 0
                remaining_total = rule.max_total_loss.amount - current_total_loss
                budget["total_loss_remaining"] = Money(max(0, remaining_total), rule.max_total_loss.currency)
        
        return budget


class ChallengeProgressService:
    """Domain service for tracking challenge progress."""
    
    @staticmethod
    def calculate_progress_percentage(challenge: Challenge) -> float:
        """Calculate overall progress percentage towards completion."""
        if challenge.state != ChallengeState.ACTIVE:
            return 100.0 if challenge.state == ChallengeState.FUNDED else 0.0
        
        progress_factors = []
        
        # Profit target progress
        if challenge.parameters.profit_target.target_amount.amount > 0:
            profit_progress = min(
                100.0,
                (challenge.total_pnl.amount / challenge.parameters.profit_target.target_amount.amount) * 100
            )
            progress_factors.append(max(0.0, profit_progress))
        
        # Trading days progress
        days_progress = min(
            100.0,
            (challenge.trading_days / challenge.parameters.min_trading_days) * 100
        )
        progress_factors.append(days_progress)
        
        # Time progress (inverse - less time remaining = more progress)
        if challenge.expires_at:
            total_duration = challenge.expires_at - challenge.started_at
            elapsed = datetime.utcnow() - challenge.started_at
            time_progress = min(100.0, (elapsed.total_seconds() / total_duration.total_seconds()) * 100)
            progress_factors.append(time_progress)
        
        # Return weighted average
        return sum(progress_factors) / len(progress_factors) if progress_factors else 0.0
    
    @staticmethod
    def get_completion_requirements_status(challenge: Challenge) -> Dict[str, bool]:
        """Get status of all completion requirements."""
        return {
            "profit_target_met": challenge.parameters.profit_target.is_achieved(
                challenge.total_pnl, 
                challenge._daily_profits
            ),
            "min_trading_days_met": challenge.trading_days >= challenge.parameters.min_trading_days,
            "no_critical_violations": not any(v.is_critical for v in challenge.risk_violations),
            "within_time_limit": (
                not challenge.expires_at or 
                datetime.utcnow() < challenge.expires_at
            ),
        }
    
    @staticmethod
    def estimate_completion_date(challenge: Challenge) -> Optional[datetime]:
        """Estimate when challenge might be completed based on current progress."""
        if challenge.state != ChallengeState.ACTIVE:
            return None
        
        if challenge.trading_days == 0:
            return None
        
        # Calculate average daily profit
        avg_daily_profit = challenge.total_pnl.amount / challenge.trading_days
        
        if avg_daily_profit <= 0:
            return None  # Cannot estimate with negative/zero progress
        
        # Calculate remaining profit needed
        remaining_profit = challenge.parameters.profit_target.target_amount.amount - challenge.total_pnl.amount
        
        if remaining_profit <= 0:
            # Already met profit target, just need to complete minimum days
            remaining_days = max(0, challenge.parameters.min_trading_days - challenge.trading_days)
            return datetime.utcnow() + timedelta(days=remaining_days)
        
        # Estimate days needed based on current performance
        estimated_days_needed = remaining_profit / avg_daily_profit
        estimated_completion = datetime.utcnow() + timedelta(days=estimated_days_needed)
        
        # Ensure it's within the challenge time limit
        if challenge.expires_at and estimated_completion > challenge.expires_at:
            return challenge.expires_at
        
        return estimated_completion