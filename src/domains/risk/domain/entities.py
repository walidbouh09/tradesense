"""Risk Engine domain entities."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from ....shared.utils.money import Money
from .events import (
    RiskAlertTriggered,
    RiskAlertResolved,
    RiskScoreCalculated,
    RiskThresholdViolated,
    TradingHalted,
    TradingResumed,
    EmergencyRiskEvent,
    RiskProfileUpdated,
)
from .value_objects import (
    AlertSeverity,
    DrawdownMetric,
    PositionRiskMetric,
    RiskAlert,
    RiskLevel,
    RiskLimits,
    RiskMetric,
    RiskMetricType,
    RiskProfile,
    RiskScore,
    RiskThreshold,
    ThresholdType,
    TradingVelocityMetric,
    VolatilityMetric,
)


class RiskEngine(AggregateRoot):
    """Risk Engine aggregate managing risk assessment and monitoring."""
    
    def __init__(
        self,
        user_id: UUID,
        challenge_id: Optional[UUID] = None,
        risk_profile: Optional[RiskProfile] = None,
        risk_limits: Optional[RiskLimits] = None,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._user_id = user_id
        self._challenge_id = challenge_id
        self._risk_profile = risk_profile or self._create_default_profile()
        self._risk_limits = risk_limits or RiskLimits()
        
        # Risk state
        self._current_risk_score: Optional[RiskScore] = None
        self._active_alerts: Dict[str, RiskAlert] = {}
        self._risk_metrics_history: List[RiskMetric] = []
        self._is_trading_halted = False
        self._halt_reason: Optional[str] = None
        self._halted_at: Optional[datetime] = None
        
        # Trading data cache (from events)
        self._current_balance = Money.zero()
        self._daily_pnl = Money.zero()
        self._total_pnl = Money.zero()
        self._open_positions: Dict[str, Dict] = {}  # symbol -> position data
        self._daily_trades = 0
        self._total_trades = 0
        self._last_trade_time: Optional[datetime] = None
        self._daily_reset_time: Optional[datetime] = None
        
        # Performance tracking
        self._peak_balance = Money.zero()
        self._max_drawdown = Money.zero()
        self._current_drawdown = Money.zero()
        self._daily_returns: List[Decimal] = []
        
        self._touch()
    
    def update_risk_profile(self, new_profile: RiskProfile) -> None:
        """Update risk profile configuration."""
        if new_profile.user_id != self._user_id:
            raise BusinessRuleViolationError("Risk profile user ID must match engine user ID")
        
        old_profile = self._risk_profile
        self._risk_profile = new_profile
        self._touch()
        
        # Emit profile update event
        self.add_domain_event(
            RiskProfileUpdated(
                aggregate_id=self.id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                old_profile_name=old_profile.profile_name,
                new_profile_name=new_profile.profile_name,
                threshold_changes=self._compare_thresholds(old_profile, new_profile),
            )
        )
    
    def process_trade_event(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        trade_value: Money,
        commission: Money,
        executed_at: datetime,
    ) -> None:
        """Process incoming trade event and update risk metrics."""
        
        # Update trading statistics
        self._total_trades += 1
        self._last_trade_time = executed_at
        
        # Reset daily counters if new day
        if self._is_new_trading_day(executed_at):
            self._reset_daily_metrics(executed_at)
        
        self._daily_trades += 1
        
        # Check trading velocity
        velocity_metric = self._calculate_trading_velocity()
        if velocity_metric:
            self._check_velocity_thresholds(velocity_metric)
        
        # Check symbol restrictions
        if not self._risk_profile.is_symbol_allowed(symbol):
            self._trigger_alert(
                f"FORBIDDEN_SYMBOL_{symbol}",
                RiskMetric(RiskMetricType.POSITION_SIZE, Decimal("0")),
                AlertSeverity.CRITICAL,
                f"Trading in forbidden symbol: {symbol}",
            )
        
        # Check trading hours
        if not self._risk_profile.is_within_trading_hours(executed_at):
            self._trigger_alert(
                f"OUTSIDE_HOURS_{executed_at.hour}",
                RiskMetric(RiskMetricType.TRADING_HOURS, Decimal(executed_at.hour)),
                AlertSeverity.WARNING,
                f"Trading outside allowed hours: {executed_at.time()}",
            )
        
        self._touch()
    
    def process_position_event(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        entry_price: Decimal,
        current_price: Decimal,
        unrealized_pnl: Money,
        position_value: Money,
        event_type: str,  # OPENED, UPDATED, CLOSED
    ) -> None:
        """Process position event and update position risk metrics."""
        
        if event_type == "CLOSED":
            # Remove closed position
            if symbol in self._open_positions:
                del self._open_positions[symbol]
        else:
            # Update or add position
            self._open_positions[symbol] = {
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "position_value": position_value,
                "updated_at": datetime.utcnow(),
            }
        
        # Calculate position risk metrics
        if event_type != "CLOSED":
            position_metric = self._calculate_position_risk(symbol, position_value, unrealized_pnl)
            self._check_position_thresholds(position_metric)
        
        # Calculate total exposure
        total_exposure = self._calculate_total_exposure()
        exposure_metric = RiskMetric(
            RiskMetricType.EXPOSURE,
            total_exposure.amount,
            total_exposure.currency,
        )
        self._check_exposure_thresholds(exposure_metric)
        
        self._touch()
    
    def process_pnl_event(
        self,
        current_balance: Money,
        daily_pnl: Money,
        total_pnl: Money,
        unrealized_pnl: Money,
        event_date: datetime,
    ) -> None:
        """Process P&L event and update risk metrics."""
        
        # Update balance and P&L
        old_balance = self._current_balance
        self._current_balance = current_balance
        self._daily_pnl = daily_pnl
        self._total_pnl = total_pnl
        
        # Update peak balance and drawdown
        if current_balance > self._peak_balance:
            self._peak_balance = current_balance
            self._current_drawdown = Money.zero(current_balance.currency)
        else:
            self._current_drawdown = self._peak_balance - current_balance
            if self._current_drawdown > self._max_drawdown:
                self._max_drawdown = self._current_drawdown
        
        # Calculate drawdown metrics
        daily_drawdown = self._calculate_daily_drawdown(daily_pnl, current_balance)
        total_drawdown = self._calculate_total_drawdown(current_balance)
        
        # Check drawdown thresholds
        self._check_drawdown_thresholds(daily_drawdown, total_drawdown)
        
        # Calculate P&L volatility if we have enough data
        if len(self._daily_returns) >= 5:
            volatility_metric = self._calculate_volatility()
            self._check_volatility_thresholds(volatility_metric)
        
        # Add daily return for volatility calculation
        if old_balance.amount > 0:
            daily_return = (current_balance.amount - old_balance.amount) / old_balance.amount
            self._daily_returns.append(daily_return)
            
            # Keep only last 30 days of returns
            if len(self._daily_returns) > 30:
                self._daily_returns = self._daily_returns[-30:]
        
        # Calculate overall risk score
        self._calculate_risk_score()
        
        self._touch()
    
    def halt_trading(self, reason: str, severity: AlertSeverity = AlertSeverity.EMERGENCY) -> None:
        """Halt trading due to risk violation."""
        if self._is_trading_halted:
            return  # Already halted
        
        self._is_trading_halted = True
        self._halt_reason = reason
        self._halted_at = datetime.utcnow()
        self._touch()
        
        # Emit trading halt event
        self.add_domain_event(
            TradingHalted(
                aggregate_id=self.id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                reason=reason,
                severity=severity.value,
                halted_at=self._halted_at.isoformat(),
                current_risk_score=self._current_risk_score.overall_score if self._current_risk_score else Decimal("0"),
                active_alerts_count=len(self._active_alerts),
            )
        )
        
        # Emit emergency event if severity is emergency
        if severity == AlertSeverity.EMERGENCY:
            self.add_domain_event(
                EmergencyRiskEvent(
                    aggregate_id=self.id,
                    user_id=self._user_id,
                    challenge_id=self._challenge_id,
                    event_type="TRADING_HALT",
                    description=reason,
                    risk_score=self._current_risk_score.overall_score if self._current_risk_score else Decimal("0"),
                    requires_manual_intervention=True,
                )
            )
    
    def resume_trading(self, reason: str) -> None:
        """Resume trading after risk conditions are resolved."""
        if not self._is_trading_halted:
            return  # Not halted
        
        self._is_trading_halted = False
        resumed_at = datetime.utcnow()
        halt_duration = (resumed_at - self._halted_at).total_seconds() if self._halted_at else 0
        
        self._halt_reason = None
        self._halted_at = None
        self._touch()
        
        # Emit trading resume event
        self.add_domain_event(
            TradingResumed(
                aggregate_id=self.id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                reason=reason,
                resumed_at=resumed_at.isoformat(),
                halt_duration_seconds=int(halt_duration),
                current_risk_score=self._current_risk_score.overall_score if self._current_risk_score else Decimal("0"),
            )
        )
    
    def _calculate_trading_velocity(self) -> Optional[TradingVelocityMetric]:
        """Calculate trading velocity metrics."""
        if not self._last_trade_time:
            return None
        
        # Calculate trades in last 24 hours
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        
        # For simplicity, use daily trades (would need trade history for accurate calculation)
        trades_per_hour = Decimal(self._daily_trades) / 24 if self._daily_trades > 0 else Decimal("0")
        
        # Calculate average trade size (simplified)
        avg_trade_size = Money.zero()  # Would need trade value history
        total_volume = Money.zero()    # Would need trade volume history
        
        return TradingVelocityMetric(
            trades_per_hour=trades_per_hour,
            trades_per_day=self._daily_trades,
            average_trade_size=avg_trade_size,
            total_volume=total_volume,
        )
    
    def _calculate_position_risk(self, symbol: str, position_value: Money, unrealized_pnl: Money) -> PositionRiskMetric:
        """Calculate position-specific risk metrics."""
        # Calculate leverage (simplified)
        leverage = Decimal("1")  # Would need margin requirements
        
        return PositionRiskMetric(
            symbol=symbol,
            position_size=position_value,
            account_balance=self._current_balance,
            leverage=leverage,
            unrealized_pnl=unrealized_pnl,
        )
    
    def _calculate_daily_drawdown(self, daily_pnl: Money, current_balance: Money) -> DrawdownMetric:
        """Calculate daily drawdown metric."""
        if daily_pnl.amount >= 0:
            # No drawdown if positive P&L
            return DrawdownMetric(
                drawdown_amount=Money.zero(daily_pnl.currency),
                drawdown_percentage=Decimal("0"),
                peak_balance=current_balance,
                current_balance=current_balance,
                is_daily=True,
            )
        
        # Calculate daily drawdown
        drawdown_amount = Money(abs(daily_pnl.amount), daily_pnl.currency)
        drawdown_percentage = (abs(daily_pnl.amount) / current_balance.amount * 100) if current_balance.amount > 0 else Decimal("0")
        
        return DrawdownMetric(
            drawdown_amount=drawdown_amount,
            drawdown_percentage=drawdown_percentage,
            peak_balance=current_balance + drawdown_amount,
            current_balance=current_balance,
            is_daily=True,
        )
    
    def _calculate_total_drawdown(self, current_balance: Money) -> DrawdownMetric:
        """Calculate total drawdown metric."""
        drawdown_percentage = (self._current_drawdown.amount / self._peak_balance.amount * 100) if self._peak_balance.amount > 0 else Decimal("0")
        
        return DrawdownMetric(
            drawdown_amount=self._current_drawdown,
            drawdown_percentage=drawdown_percentage,
            peak_balance=self._peak_balance,
            current_balance=current_balance,
            is_daily=False,
        )
    
    def _calculate_volatility(self) -> VolatilityMetric:
        """Calculate P&L volatility metric."""
        if len(self._daily_returns) < 2:
            return VolatilityMetric(
                volatility=Decimal("0"),
                returns=self._daily_returns,
                time_period_days=len(self._daily_returns),
            )
        
        # Calculate standard deviation of returns
        mean_return = sum(self._daily_returns) / len(self._daily_returns)
        variance = sum((r - mean_return) ** 2 for r in self._daily_returns) / (len(self._daily_returns) - 1)
        volatility = variance.sqrt()
        
        # Annualize volatility
        annualized_volatility = volatility * (Decimal("252").sqrt())  # 252 trading days per year
        
        return VolatilityMetric(
            volatility=volatility,
            returns=self._daily_returns.copy(),
            time_period_days=len(self._daily_returns),
            annualized_volatility=annualized_volatility,
        )
    
    def _calculate_total_exposure(self) -> Money:
        """Calculate total position exposure."""
        total_exposure = Money.zero()
        
        for position_data in self._open_positions.values():
            position_value = position_data["position_value"]
            total_exposure += position_value
        
        return total_exposure
    
    def _calculate_risk_score(self) -> None:
        """Calculate overall risk score."""
        component_scores = {}
        total_score = Decimal("0")
        weight_sum = Decimal("0")
        
        # Drawdown component (30% weight)
        if self._current_drawdown.amount > 0:
            drawdown_score = min(self._current_drawdown.amount / self._peak_balance.amount * 100 * 3, Decimal("30"))
            component_scores[RiskMetricType.TOTAL_DRAWDOWN] = drawdown_score
            total_score += drawdown_score
            weight_sum += Decimal("30")
        
        # Position concentration component (25% weight)
        if self._open_positions:
            max_position_percent = Decimal("0")
            for position_data in self._open_positions.values():
                position_value = position_data["position_value"]
                position_percent = (position_value.amount / self._current_balance.amount * 100) if self._current_balance.amount > 0 else Decimal("0")
                max_position_percent = max(max_position_percent, position_percent)
            
            concentration_score = min(max_position_percent, Decimal("25"))
            component_scores[RiskMetricType.POSITION_CONCENTRATION] = concentration_score
            total_score += concentration_score
            weight_sum += Decimal("25")
        
        # Trading velocity component (20% weight)
        if self._daily_trades > 0:
            # Normalize daily trades (assume 100+ trades per day is maximum risk)
            velocity_score = min(Decimal(self._daily_trades) / 100 * 20, Decimal("20"))
            component_scores[RiskMetricType.TRADING_VELOCITY] = velocity_score
            total_score += velocity_score
            weight_sum += Decimal("20")
        
        # Volatility component (15% weight)
        if len(self._daily_returns) >= 5:
            volatility_metric = self._calculate_volatility()
            # Normalize volatility (assume 5% daily volatility is maximum risk)
            volatility_score = min(volatility_metric.volatility * 100 / 5 * 15, Decimal("15"))
            component_scores[RiskMetricType.PNL_VOLATILITY] = volatility_score
            total_score += volatility_score
            weight_sum += Decimal("15")
        
        # Active alerts component (10% weight)
        alert_score = min(len(self._active_alerts) * 2, Decimal("10"))
        component_scores[RiskMetricType.DAILY_PNL] = alert_score  # Use as placeholder
        total_score += alert_score
        weight_sum += Decimal("10")
        
        # Normalize score to 0-100
        if weight_sum > 0:
            final_score = min(total_score, Decimal("100"))
        else:
            final_score = Decimal("0")
        
        # Create risk score
        risk_level = RiskScore.calculate_risk_level(final_score)
        active_alerts = list(self._active_alerts.values())
        
        self._current_risk_score = RiskScore(
            user_id=self._user_id,
            overall_score=final_score,
            risk_level=risk_level,
            component_scores=component_scores,
            active_alerts=active_alerts,
        )
        
        # Emit risk score event
        self.add_domain_event(
            RiskScoreCalculated(
                aggregate_id=self.id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                risk_score=final_score,
                risk_level=risk_level.value,
                component_scores=component_scores,
                active_alerts_count=len(active_alerts),
                critical_alerts_count=len([a for a in active_alerts if a.is_critical]),
            )
        )
    
    def _check_drawdown_thresholds(self, daily_drawdown: DrawdownMetric, total_drawdown: DrawdownMetric) -> None:
        """Check drawdown against thresholds."""
        # Check daily drawdown
        daily_threshold = self._risk_profile.get_threshold(RiskMetricType.DAILY_DRAWDOWN)
        if daily_threshold:
            severity = daily_threshold.evaluate_level(daily_drawdown.drawdown_percentage)
            if severity != AlertSeverity.INFO:
                alert_id = f"DAILY_DRAWDOWN_{datetime.utcnow().strftime('%Y%m%d')}"
                message = f"Daily drawdown {daily_drawdown.drawdown_percentage:.2f}% exceeds threshold"
                self._trigger_alert(alert_id, daily_drawdown, severity, message)
                
                if severity == AlertSeverity.EMERGENCY:
                    self.halt_trading(f"Emergency daily drawdown: {daily_drawdown.drawdown_percentage:.2f}%")
        
        # Check total drawdown
        total_threshold = self._risk_profile.get_threshold(RiskMetricType.TOTAL_DRAWDOWN)
        if total_threshold:
            severity = total_threshold.evaluate_level(total_drawdown.drawdown_percentage)
            if severity != AlertSeverity.INFO:
                alert_id = f"TOTAL_DRAWDOWN_{self._user_id}"
                message = f"Total drawdown {total_drawdown.drawdown_percentage:.2f}% exceeds threshold"
                self._trigger_alert(alert_id, total_drawdown, severity, message)
                
                if severity == AlertSeverity.EMERGENCY:
                    self.halt_trading(f"Emergency total drawdown: {total_drawdown.drawdown_percentage:.2f}%")
    
    def _check_position_thresholds(self, position_metric: PositionRiskMetric) -> None:
        """Check position size against thresholds."""
        threshold = self._risk_profile.get_threshold(RiskMetricType.POSITION_SIZE)
        if threshold:
            severity = threshold.evaluate_level(position_metric.percentage or Decimal("0"))
            if severity != AlertSeverity.INFO:
                alert_id = f"POSITION_SIZE_{position_metric.symbol}"
                message = f"Position size {position_metric.percentage:.2f}% in {position_metric.symbol} exceeds threshold"
                self._trigger_alert(alert_id, position_metric, severity, message)
    
    def _check_velocity_thresholds(self, velocity_metric: TradingVelocityMetric) -> None:
        """Check trading velocity against thresholds."""
        threshold = self._risk_profile.get_threshold(RiskMetricType.TRADING_VELOCITY)
        if threshold:
            severity = threshold.evaluate_level(velocity_metric.trades_per_hour)
            if severity != AlertSeverity.INFO:
                alert_id = f"TRADING_VELOCITY_{datetime.utcnow().strftime('%Y%m%d_%H')}"
                message = f"Trading velocity {velocity_metric.trades_per_hour:.1f} trades/hour exceeds threshold"
                self._trigger_alert(alert_id, velocity_metric, severity, message)
    
    def _check_volatility_thresholds(self, volatility_metric: VolatilityMetric) -> None:
        """Check P&L volatility against thresholds."""
        threshold = self._risk_profile.get_threshold(RiskMetricType.PNL_VOLATILITY)
        if threshold:
            severity = threshold.evaluate_level(volatility_metric.volatility * 100)
            if severity != AlertSeverity.INFO:
                alert_id = f"PNL_VOLATILITY_{self._user_id}"
                message = f"P&L volatility {volatility_metric.volatility * 100:.2f}% exceeds threshold"
                self._trigger_alert(alert_id, volatility_metric, severity, message)
    
    def _check_exposure_thresholds(self, exposure_metric: RiskMetric) -> None:
        """Check total exposure against thresholds."""
        threshold = self._risk_profile.get_threshold(RiskMetricType.EXPOSURE)
        if threshold:
            exposure_percent = (exposure_metric.value / self._current_balance.amount * 100) if self._current_balance.amount > 0 else Decimal("0")
            severity = threshold.evaluate_level(exposure_percent)
            if severity != AlertSeverity.INFO:
                alert_id = f"TOTAL_EXPOSURE_{self._user_id}"
                message = f"Total exposure {exposure_percent:.2f}% exceeds threshold"
                self._trigger_alert(alert_id, exposure_metric, severity, message)
    
    def _trigger_alert(self, alert_id: str, metric: RiskMetric, severity: AlertSeverity, message: str) -> None:
        """Trigger a risk alert."""
        # Check if alert already exists
        if alert_id in self._active_alerts:
            existing_alert = self._active_alerts[alert_id]
            if existing_alert.severity == severity:
                return  # Same severity, don't duplicate
        
        # Find threshold for metric
        threshold = self._risk_profile.get_threshold(metric.metric_type)
        
        # Create alert
        alert = RiskAlert(
            alert_id=alert_id,
            user_id=self._user_id,
            metric=metric,
            threshold=threshold,
            severity=severity,
            message=message,
        )
        
        # Store alert
        self._active_alerts[alert_id] = alert
        
        # Emit alert event
        self.add_domain_event(
            RiskAlertTriggered(
                aggregate_id=self.id,
                alert_id=alert_id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                metric_type=metric.metric_type.value,
                metric_value=str(metric.value),
                severity=severity.value,
                message=message,
                requires_action=alert.requires_immediate_action,
            )
        )
        
        # Emit threshold violation event
        if threshold:
            self.add_domain_event(
                RiskThresholdViolated(
                    aggregate_id=self.id,
                    user_id=self._user_id,
                    challenge_id=self._challenge_id,
                    threshold_type=threshold.metric_type.value,
                    threshold_level=str(threshold.warning_level),
                    actual_value=str(metric.value),
                    severity=severity.value,
                    violation_percentage=str((abs(metric.value) / abs(threshold.warning_level) - 1) * 100) if threshold.warning_level != 0 else "0",
                )
            )
    
    def _resolve_alert(self, alert_id: str, reason: str) -> None:
        """Resolve an active alert."""
        if alert_id not in self._active_alerts:
            return
        
        alert = self._active_alerts[alert_id]
        del self._active_alerts[alert_id]
        
        # Emit alert resolved event
        self.add_domain_event(
            RiskAlertResolved(
                aggregate_id=self.id,
                alert_id=alert_id,
                user_id=self._user_id,
                challenge_id=self._challenge_id,
                metric_type=alert.metric.metric_type.value,
                resolution_reason=reason,
                alert_duration_seconds=int((datetime.utcnow() - alert.triggered_at).total_seconds()),
            )
        )
    
    def _is_new_trading_day(self, timestamp: datetime) -> bool:
        """Check if timestamp represents a new trading day."""
        if not self._daily_reset_time:
            return True
        
        return timestamp.date() > self._daily_reset_time.date()
    
    def _reset_daily_metrics(self, timestamp: datetime) -> None:
        """Reset daily metrics for new trading day."""
        self._daily_trades = 0
        self._daily_pnl = Money.zero()
        self._daily_reset_time = timestamp
        
        # Resolve daily alerts
        daily_alerts = [aid for aid in self._active_alerts.keys() if "DAILY" in aid]
        for alert_id in daily_alerts:
            self._resolve_alert(alert_id, "New trading day")
    
    def _create_default_profile(self) -> RiskProfile:
        """Create default risk profile."""
        default_thresholds = [
            RiskThreshold(
                RiskMetricType.DAILY_DRAWDOWN,
                ThresholdType.PERCENTAGE,
                warning_level=Decimal("3"),
                critical_level=Decimal("5"),
                emergency_level=Decimal("8"),
                description="Daily drawdown percentage threshold",
            ),
            RiskThreshold(
                RiskMetricType.TOTAL_DRAWDOWN,
                ThresholdType.PERCENTAGE,
                warning_level=Decimal("8"),
                critical_level=Decimal("10"),
                emergency_level=Decimal("12"),
                description="Total drawdown percentage threshold",
            ),
            RiskThreshold(
                RiskMetricType.POSITION_SIZE,
                ThresholdType.PERCENTAGE,
                warning_level=Decimal("15"),
                critical_level=Decimal("20"),
                emergency_level=Decimal("25"),
                description="Position size percentage threshold",
            ),
            RiskThreshold(
                RiskMetricType.TRADING_VELOCITY,
                ThresholdType.ABSOLUTE,
                warning_level=Decimal("10"),
                critical_level=Decimal("20"),
                emergency_level=Decimal("30"),
                description="Trading velocity (trades per hour) threshold",
            ),
        ]
        
        return RiskProfile(
            user_id=self._user_id,
            challenge_id=self._challenge_id,
            thresholds=default_thresholds,
            max_daily_trades=100,
            max_position_size_percent=Decimal("20"),
            max_leverage=Decimal("10"),
            profile_name="Default",
        )
    
    def _compare_thresholds(self, old_profile: RiskProfile, new_profile: RiskProfile) -> List[str]:
        """Compare threshold changes between profiles."""
        changes = []
        
        old_thresholds = {t.metric_type: t for t in old_profile.thresholds}
        new_thresholds = {t.metric_type: t for t in new_profile.thresholds}
        
        for metric_type, new_threshold in new_thresholds.items():
            if metric_type in old_thresholds:
                old_threshold = old_thresholds[metric_type]
                if (old_threshold.warning_level != new_threshold.warning_level or
                    old_threshold.critical_level != new_threshold.critical_level):
                    changes.append(f"{metric_type.value}: {old_threshold.warning_level} -> {new_threshold.warning_level}")
            else:
                changes.append(f"Added {metric_type.value} threshold")
        
        return changes
    
    # Properties
    @property
    def user_id(self) -> UUID:
        return self._user_id
    
    @property
    def challenge_id(self) -> Optional[UUID]:
        return self._challenge_id
    
    @property
    def risk_profile(self) -> RiskProfile:
        return self._risk_profile
    
    @property
    def current_risk_score(self) -> Optional[RiskScore]:
        return self._current_risk_score
    
    @property
    def active_alerts(self) -> List[RiskAlert]:
        return list(self._active_alerts.values())
    
    @property
    def is_trading_halted(self) -> bool:
        return self._is_trading_halted
    
    @property
    def halt_reason(self) -> Optional[str]:
        return self._halt_reason
    
    @property
    def current_balance(self) -> Money:
        return self._current_balance
    
    @property
    def daily_pnl(self) -> Money:
        return self._daily_pnl
    
    @property
    def total_pnl(self) -> Money:
        return self._total_pnl
    
    @property
    def current_drawdown(self) -> Money:
        return self._current_drawdown
    
    @property
    def max_drawdown(self) -> Money:
        return self._max_drawdown
    
    @property
    def daily_trades(self) -> int:
        return self._daily_trades
    
    @property
    def total_trades(self) -> int:
        return self._total_trades
    
    @property
    def open_positions_count(self) -> int:
        return len(self._open_positions)