"""Evaluation domain entities."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from ....shared.utils.money import Money
from .events import (
    ChallengeExpired,
    ChallengeFailed,
    ChallengePassed,
    ChallengeRulesUpdated,
    ChallengeStarted,
    ChallengeStateChanged,
    RiskViolationDetected,
    TradingMetricsUpdated,
    TraderFunded,
)
from .value_objects import (
    ChallengeParameters,
    ChallengeState,
    ChallengeType,
    ProfitTarget,
    RiskRule,
    RiskViolation,
    TradingMetrics,
)


class Challenge(AggregateRoot):
    """Challenge aggregate root managing trader evaluation process."""
    
    def __init__(
        self,
        trader_id: UUID,
        parameters: ChallengeParameters,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._trader_id = trader_id
        self._parameters = parameters
        self._state = ChallengeState.PENDING
        
        # Timestamps
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._expires_at: Optional[datetime] = None
        
        # Trading metrics
        self._current_balance = parameters.initial_balance
        self._total_pnl = Money.zero(parameters.initial_balance.currency)
        self._daily_pnl = Money.zero(parameters.initial_balance.currency)
        self._trading_days = 0
        self._total_trades = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._largest_win = Money.zero(parameters.initial_balance.currency)
        self._largest_loss = Money.zero(parameters.initial_balance.currency)
        self._current_drawdown = Money.zero(parameters.initial_balance.currency)
        self._max_drawdown = Money.zero(parameters.initial_balance.currency)
        self._daily_profits: List[Money] = []
        
        # Risk tracking
        self._risk_violations: List[RiskViolation] = []
        self._last_risk_check: Optional[datetime] = None
        
        # Results
        self._failure_reason: Optional[str] = None
        self._funded_amount: Optional[Money] = None
        self._profit_split_percent: Optional[int] = None
    
    def start_challenge(self, started_by: Optional[UUID] = None) -> None:
        """Start the challenge and transition to ACTIVE state."""
        if self._state != ChallengeState.PENDING:
            raise BusinessRuleViolationError(
                f"Cannot start challenge in {self._state.value} state"
            )
        
        # Set timestamps
        self._started_at = datetime.utcnow()
        self._expires_at = self._started_at + timedelta(days=self._parameters.max_duration_days)
        
        # Transition to ACTIVE state
        old_state = self._state
        self._state = ChallengeState.ACTIVE
        self._touch()
        
        # Emit events
        self.add_domain_event(
            ChallengeStarted(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                challenge_type=self._parameters.challenge_type.value,
                initial_balance=str(self._parameters.initial_balance.amount),
                profit_target=str(self._parameters.profit_target.target_amount.amount),
                max_duration_days=self._parameters.max_duration_days,
            )
        )
        
        self.add_domain_event(
            ChallengeStateChanged(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                old_state=old_state.value,
                new_state=self._state.value,
                reason="Challenge started",
                changed_by=started_by,
            )
        )
    
    def update_trading_metrics(
        self,
        new_balance: Money,
        daily_pnl: Money,
        trade_count: int = 0,
        winning_trades: int = 0,
        losing_trades: int = 0,
    ) -> None:
        """Update trading metrics and check for rule violations."""
        if self._state != ChallengeState.ACTIVE:
            raise BusinessRuleViolationError(
                f"Cannot update metrics in {self._state.value} state"
            )
        
        # Update balance and P&L
        old_balance = self._current_balance
        self._current_balance = new_balance
        self._total_pnl = new_balance - self._parameters.initial_balance
        self._daily_pnl = daily_pnl
        
        # Update trade statistics
        self._total_trades += trade_count
        self._winning_trades += winning_trades
        self._losing_trades += losing_trades
        
        # Update daily profits tracking
        if daily_pnl.amount != 0:
            self._daily_profits.append(daily_pnl)
            if len(self._daily_profits) > self._parameters.max_duration_days:
                self._daily_profits = self._daily_profits[-self._parameters.max_duration_days:]
        
        # Update drawdown tracking
        if new_balance < old_balance:
            loss = old_balance - new_balance
            self._current_drawdown = self._current_drawdown + loss
            if self._current_drawdown > self._max_drawdown:
                self._max_drawdown = self._current_drawdown
        else:
            self._current_drawdown = Money.zero(new_balance.currency)
        
        # Update trading days (if there was trading activity)
        if trade_count > 0:
            self._trading_days += 1
        
        self._touch()
        
        # Emit metrics update event
        self.add_domain_event(
            TradingMetricsUpdated(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                total_pnl=str(self._total_pnl.amount),
                daily_pnl=str(daily_pnl.amount),
                trading_days=self._trading_days,
                total_trades=self._total_trades,
                current_balance=str(new_balance.amount),
            )
        )
        
        # Check for risk violations
        self._check_risk_rules()
        
        # Check for challenge completion
        self._check_completion_conditions()
    
    def fail_challenge(self, reason: str, failed_by: Optional[UUID] = None) -> None:
        """Manually fail the challenge."""
        if self._state != ChallengeState.ACTIVE:
            raise BusinessRuleViolationError(
                f"Cannot fail challenge in {self._state.value} state"
            )
        
        self._transition_to_failed(reason, failed_by)
    
    def pass_challenge(self, passed_by: Optional[UUID] = None) -> None:
        """Manually pass the challenge."""
        if self._state != ChallengeState.ACTIVE:
            raise BusinessRuleViolationError(
                f"Cannot pass challenge in {self._state.value} state"
            )
        
        # Verify challenge requirements are met
        if not self._are_pass_requirements_met():
            raise BusinessRuleViolationError(
                "Challenge requirements not met for passing"
            )
        
        self._transition_to_passed(passed_by)
    
    def fund_trader(
        self,
        funded_amount: Money,
        profit_split_percent: int,
        funded_by: UUID,
    ) -> None:
        """Fund the trader after successful challenge completion."""
        if self._state != ChallengeState.FUNDED:
            raise BusinessRuleViolationError(
                f"Cannot fund trader in {self._state.value} state"
            )
        
        if funded_amount.amount <= 0:
            raise ValidationError("Funded amount must be positive")
        
        if profit_split_percent < 0 or profit_split_percent > 100:
            raise ValidationError("Profit split percent must be between 0 and 100")
        
        self._funded_amount = funded_amount
        self._profit_split_percent = profit_split_percent
        self._touch()
        
        # Emit funding event
        self.add_domain_event(
            TraderFunded(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                funded_amount=str(funded_amount.amount),
                profit_split_percent=profit_split_percent,
                funding_date=datetime.utcnow().isoformat(),
            )
        )
    
    def update_rules(
        self,
        new_parameters: ChallengeParameters,
        updated_by: UUID,
        reason: str,
    ) -> None:
        """Update challenge rules (only allowed in PENDING state)."""
        if self._state != ChallengeState.PENDING:
            raise BusinessRuleViolationError(
                f"Cannot update rules in {self._state.value} state"
            )
        
        old_parameters = self._parameters
        self._parameters = new_parameters
        self._touch()
        
        # Determine what rules changed
        updated_rules = []
        if old_parameters.profit_target != new_parameters.profit_target:
            updated_rules.append("profit_target")
        if old_parameters.risk_rules != new_parameters.risk_rules:
            updated_rules.append("risk_rules")
        if old_parameters.max_duration_days != new_parameters.max_duration_days:
            updated_rules.append("max_duration_days")
        
        # Emit rules update event
        self.add_domain_event(
            ChallengeRulesUpdated(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                updated_rules=updated_rules,
                updated_by=updated_by,
                reason=reason,
            )
        )
    
    def check_expiration(self) -> None:
        """Check if challenge has expired and handle accordingly."""
        if self._state != ChallengeState.ACTIVE:
            return
        
        if not self._expires_at:
            return
        
        if datetime.utcnow() >= self._expires_at:
            # Challenge has expired
            if self._are_pass_requirements_met():
                self._transition_to_passed(None)
            else:
                self._transition_to_failed("Challenge expired", None)
            
            # Emit expiration event
            self.add_domain_event(
                ChallengeExpired(
                    aggregate_id=self.id,
                    trader_id=self._trader_id,
                    started_at=self._started_at.isoformat() if self._started_at else "",
                    expired_at=datetime.utcnow().isoformat(),
                    max_duration_days=self._parameters.max_duration_days,
                    final_state=self._state.value,
                )
            )
    
    def _check_risk_rules(self) -> None:
        """Check all risk rules and handle violations."""
        violations = []
        
        for rule in self._parameters.risk_rules:
            # Check daily loss rule
            if not rule.validate_daily_loss(self._daily_pnl, self._current_balance):
                violation = RiskViolation(
                    rule_name=rule.name,
                    violation_type="daily_loss",
                    description=f"Daily loss exceeds limit: {rule.description}",
                    severity="CRITICAL",
                    current_value=str(abs(self._daily_pnl.amount)),
                    limit_value=str(rule.max_daily_loss.amount if rule.max_daily_loss else rule.max_daily_loss_percent),
                    timestamp=datetime.utcnow().isoformat(),
                )
                violations.append(violation)
            
            # Check total loss rule
            if not rule.validate_total_loss(self._total_pnl, self._parameters.initial_balance):
                violation = RiskViolation(
                    rule_name=rule.name,
                    violation_type="total_loss",
                    description=f"Total loss exceeds limit: {rule.description}",
                    severity="CRITICAL",
                    current_value=str(abs(self._total_pnl.amount)),
                    limit_value=str(rule.max_total_loss.amount if rule.max_total_loss else rule.max_total_loss_percent),
                    timestamp=datetime.utcnow().isoformat(),
                )
                violations.append(violation)
        
        # Process violations
        for violation in violations:
            self._risk_violations.append(violation)
            
            # Emit risk violation event
            self.add_domain_event(
                RiskViolationDetected(
                    aggregate_id=self.id,
                    trader_id=self._trader_id,
                    rule_name=violation.rule_name,
                    violation_type=violation.violation_type,
                    severity=violation.severity,
                    description=violation.description,
                    current_value=violation.current_value,
                    limit_value=violation.limit_value,
                    auto_failed=violation.is_critical,
                )
            )
            
            # Auto-fail on critical violations
            if violation.is_critical:
                self._transition_to_failed(
                    f"Risk violation: {violation.description}",
                    None
                )
                break
    
    def _check_completion_conditions(self) -> None:
        """Check if challenge completion conditions are met."""
        if self._state != ChallengeState.ACTIVE:
            return
        
        # Check if profit target is achieved
        if self._parameters.profit_target.is_achieved(self._total_pnl, self._daily_profits):
            # Check if minimum trading days requirement is met
            if self._trading_days >= self._parameters.min_trading_days:
                self._transition_to_passed(None)
    
    def _are_pass_requirements_met(self) -> bool:
        """Check if all requirements for passing are met."""
        # Check profit target
        if not self._parameters.profit_target.is_achieved(self._total_pnl, self._daily_profits):
            return False
        
        # Check minimum trading days
        if self._trading_days < self._parameters.min_trading_days:
            return False
        
        # Check no critical risk violations
        if any(v.is_critical for v in self._risk_violations):
            return False
        
        return True
    
    def _transition_to_failed(self, reason: str, failed_by: Optional[UUID]) -> None:
        """Transition challenge to FAILED state."""
        old_state = self._state
        self._state = ChallengeState.FAILED
        self._failure_reason = reason
        self._completed_at = datetime.utcnow()
        self._touch()
        
        # Emit events
        self.add_domain_event(
            ChallengeStateChanged(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                old_state=old_state.value,
                new_state=self._state.value,
                reason=reason,
                changed_by=failed_by,
            )
        )
        
        self.add_domain_event(
            ChallengeFailed(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                failure_reason=reason,
                risk_violations=[
                    {
                        "rule_name": v.rule_name,
                        "violation_type": v.violation_type,
                        "severity": v.severity,
                        "description": v.description,
                    }
                    for v in self._risk_violations
                ],
                final_balance=str(self._current_balance.amount),
                trading_days=self._trading_days,
            )
        )
    
    def _transition_to_passed(self, passed_by: Optional[UUID]) -> None:
        """Transition challenge to FUNDED state."""
        old_state = self._state
        self._state = ChallengeState.FUNDED
        self._completed_at = datetime.utcnow()
        self._touch()
        
        # Calculate performance metrics
        metrics = self._get_performance_metrics()
        
        # Emit events
        self.add_domain_event(
            ChallengeStateChanged(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                old_state=old_state.value,
                new_state=self._state.value,
                reason="Challenge requirements met",
                changed_by=passed_by,
            )
        )
        
        self.add_domain_event(
            ChallengePassed(
                aggregate_id=self.id,
                trader_id=self._trader_id,
                challenge_type=self._parameters.challenge_type.value,
                final_balance=str(self._current_balance.amount),
                total_profit=str(self._total_pnl.amount),
                trading_days=self._trading_days,
                performance_metrics=metrics,
            )
        )
    
    def _get_performance_metrics(self) -> Dict:
        """Get performance metrics dictionary."""
        trading_metrics = TradingMetrics(
            total_pnl=self._total_pnl,
            daily_pnl=self._daily_pnl,
            trading_days=self._trading_days,
            total_trades=self._total_trades,
            winning_trades=self._winning_trades,
            losing_trades=self._losing_trades,
            largest_win=self._largest_win,
            largest_loss=self._largest_loss,
            current_drawdown=self._current_drawdown,
            max_drawdown=self._max_drawdown,
            daily_profits=self._daily_profits,
        )
        
        return {
            "win_rate": str(trading_metrics.win_rate),
            "profit_factor": str(trading_metrics.profit_factor),
            "max_drawdown": str(self._max_drawdown.amount),
            "average_daily_profit": str(trading_metrics.average_daily_profit.amount),
            "total_trades": self._total_trades,
            "trading_days": self._trading_days,
        }
    
    # Properties
    @property
    def trader_id(self) -> UUID:
        return self._trader_id
    
    @property
    def state(self) -> ChallengeState:
        return self._state
    
    @property
    def parameters(self) -> ChallengeParameters:
        return self._parameters
    
    @property
    def current_balance(self) -> Money:
        return self._current_balance
    
    @property
    def total_pnl(self) -> Money:
        return self._total_pnl
    
    @property
    def trading_days(self) -> int:
        return self._trading_days
    
    @property
    def risk_violations(self) -> List[RiskViolation]:
        return self._risk_violations.copy()
    
    @property
    def is_active(self) -> bool:
        return self._state == ChallengeState.ACTIVE
    
    @property
    def is_completed(self) -> bool:
        return self._state.is_terminal
    
    @property
    def allows_trading(self) -> bool:
        return self._state.allows_trading
    
    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at
    
    @property
    def expires_at(self) -> Optional[datetime]:
        return self._expires_at
    
    @property
    def completed_at(self) -> Optional[datetime]:
        return self._completed_at
    
    @property
    def failure_reason(self) -> Optional[str]:
        return self._failure_reason
    
    @property
    def funded_amount(self) -> Optional[Money]:
        return self._funded_amount