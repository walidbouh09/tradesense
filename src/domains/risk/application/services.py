"""Risk Engine application services."""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from ....shared.events.event_bus import EventBus
from ....shared.utils.money import Money
from ..domain.entities import RiskEngine
from ..domain.events import ChallengeRiskAssessment
from ..domain.value_objects import (
    AlertSeverity,
    RiskLevel,
    RiskLimits,
    RiskProfile,
)


class RiskMonitoringService:
    """Service for real-time risk monitoring and event processing."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def process_trade_executed_event(
        self,
        risk_engine: RiskEngine,
        trade_data: Dict,
    ) -> None:
        """Process TradeExecuted event from Trading domain."""
        
        # Extract trade data
        symbol = trade_data.get("symbol", "")
        side = trade_data.get("side", "")
        quantity = Decimal(str(trade_data.get("quantity", "0")))
        price = Decimal(str(trade_data.get("price", "0")))
        trade_value = Money(Decimal(str(trade_data.get("net_value", "0"))), "USD")
        commission = Money(Decimal(str(trade_data.get("commission", "0"))), "USD")
        executed_at = datetime.fromisoformat(trade_data.get("executed_at", datetime.utcnow().isoformat()))
        
        # Process trade in risk engine
        risk_engine.process_trade_event(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            trade_value=trade_value,
            commission=commission,
            executed_at=executed_at,
        )
        
        # Publish domain events
        for event in risk_engine.domain_events:
            await self.event_bus.publish(event)
        risk_engine.clear_domain_events()
    
    async def process_position_event(
        self,
        risk_engine: RiskEngine,
        position_data: Dict,
        event_type: str,
    ) -> None:
        """Process position events from Trading domain."""
        
        # Extract position data
        symbol = position_data.get("symbol", "")
        side = position_data.get("side", "")
        quantity = Decimal(str(position_data.get("quantity", "0")))
        entry_price = Decimal(str(position_data.get("entry_price", "0")))
        current_price = Decimal(str(position_data.get("current_price", entry_price)))
        unrealized_pnl = Money(Decimal(str(position_data.get("unrealized_pnl", "0"))), "USD")
        position_value = Money(Decimal(str(position_data.get("entry_value", "0"))), "USD")
        
        # Process position in risk engine
        risk_engine.process_position_event(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            position_value=position_value,
            event_type=event_type,
        )
        
        # Publish domain events
        for event in risk_engine.domain_events:
            await self.event_bus.publish(event)
        risk_engine.clear_domain_events()
    
    async def process_pnl_event(
        self,
        risk_engine: RiskEngine,
        pnl_data: Dict,
    ) -> None:
        """Process P&L events from Trading domain."""
        
        # Extract P&L data
        current_balance = Money(Decimal(str(pnl_data.get("current_balance", "0"))), "USD")
        daily_pnl = Money(Decimal(str(pnl_data.get("daily_pnl", "0"))), "USD")
        total_pnl = Money(Decimal(str(pnl_data.get("total_pnl", "0"))), "USD")
        unrealized_pnl = Money(Decimal(str(pnl_data.get("total_unrealized_pnl", "0"))), "USD")
        event_date = datetime.fromisoformat(pnl_data.get("date", datetime.utcnow().isoformat()))
        
        # Process P&L in risk engine
        risk_engine.process_pnl_event(
            current_balance=current_balance,
            daily_pnl=daily_pnl,
            total_pnl=total_pnl,
            unrealized_pnl=unrealized_pnl,
            event_date=event_date,
        )
        
        # Publish domain events
        for event in risk_engine.domain_events:
            await self.event_bus.publish(event)
        risk_engine.clear_domain_events()
    
    async def update_market_prices(
        self,
        risk_engine: RiskEngine,
        price_updates: Dict[str, Decimal],
    ) -> None:
        """Update market prices and recalculate position risks."""
        
        # This would trigger position P&L recalculation
        # For now, we'll simulate by processing position updates
        for symbol, price in price_updates.items():
            # Find open position for symbol (simplified)
            if symbol in risk_engine._open_positions:
                position_data = risk_engine._open_positions[symbol]
                
                # Calculate new unrealized P&L (simplified)
                entry_price = position_data["entry_price"]
                quantity = position_data["quantity"]
                side = position_data["side"]
                
                if side == "LONG":
                    pnl_amount = (price - entry_price) * quantity
                else:
                    pnl_amount = (entry_price - price) * quantity
                
                unrealized_pnl = Money(pnl_amount, "USD")
                position_value = Money(abs(price * quantity), "USD")
                
                # Process updated position
                await self.process_position_event(
                    risk_engine=risk_engine,
                    position_data={
                        "symbol": symbol,
                        "side": side,
                        "quantity": str(quantity),
                        "entry_price": str(entry_price),
                        "current_price": str(price),
                        "unrealized_pnl": str(unrealized_pnl.amount),
                        "entry_value": str(position_value.amount),
                    },
                    event_type="UPDATED",
                )


class RiskAssessmentService:
    """Service for comprehensive risk assessment and challenge evaluation."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def assess_challenge_risk(
        self,
        risk_engine: RiskEngine,
        challenge_id: UUID,
    ) -> Dict:
        """Perform comprehensive risk assessment for a challenge."""
        
        # Get current risk state
        risk_score = risk_engine.current_risk_score
        active_alerts = risk_engine.active_alerts
        
        # Determine actions based on risk level
        should_halt_trading = risk_engine.is_trading_halted
        should_fail_challenge = False
        critical_violations = []
        recommendations = []
        
        if risk_score:
            # Check for emergency conditions
            emergency_alerts = [a for a in active_alerts if a.severity == AlertSeverity.EMERGENCY]
            critical_alerts = [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]
            
            if emergency_alerts:
                should_halt_trading = True
                should_fail_challenge = True
                critical_violations.extend([a.message for a in emergency_alerts])
                recommendations.append("IMMEDIATE ACTION REQUIRED: Challenge should be failed due to emergency risk violations")
            
            elif critical_alerts:
                should_halt_trading = True
                critical_violations.extend([a.message for a in critical_alerts])
                recommendations.append("Trading should be halted until risk conditions improve")
            
            # Risk level recommendations
            if risk_score.risk_level == RiskLevel.EXTREME:
                recommendations.append("Extreme risk detected - consider immediate position reduction")
                should_halt_trading = True
            elif risk_score.risk_level == RiskLevel.HIGH:
                recommendations.append("High risk detected - reduce position sizes and trading frequency")
            elif risk_score.risk_level == RiskLevel.MEDIUM:
                recommendations.append("Medium risk detected - monitor positions closely")
            
            # Specific metric recommendations
            if "DAILY_DRAWDOWN" in risk_score.component_scores:
                dd_score = risk_score.component_scores["DAILY_DRAWDOWN"]
                if dd_score > 20:
                    recommendations.append("Daily drawdown is high - avoid new positions today")
            
            if "POSITION_CONCENTRATION" in risk_score.component_scores:
                pc_score = risk_score.component_scores["POSITION_CONCENTRATION"]
                if pc_score > 15:
                    recommendations.append("Position concentration is high - diversify holdings")
            
            if "TRADING_VELOCITY" in risk_score.component_scores:
                tv_score = risk_score.component_scores["TRADING_VELOCITY"]
                if tv_score > 15:
                    recommendations.append("Trading velocity is high - reduce trade frequency")
        
        # Create assessment result
        assessment = {
            "risk_score": risk_score.overall_score if risk_score else Decimal("0"),
            "risk_level": risk_score.risk_level.value if risk_score else RiskLevel.MINIMAL.value,
            "should_halt_trading": should_halt_trading,
            "should_fail_challenge": should_fail_challenge,
            "critical_violations": critical_violations,
            "recommendations": recommendations,
            "active_alerts_count": len(active_alerts),
            "critical_alerts_count": len([a for a in active_alerts if a.is_critical]),
            "emergency_alerts_count": len([a for a in active_alerts if a.severity == AlertSeverity.EMERGENCY]),
            "current_balance": str(risk_engine.current_balance.amount),
            "daily_pnl": str(risk_engine.daily_pnl.amount),
            "current_drawdown": str(risk_engine.current_drawdown.amount),
            "max_drawdown": str(risk_engine.max_drawdown.amount),
            "daily_trades": risk_engine.daily_trades,
            "open_positions": risk_engine.open_positions_count,
        }
        
        # Emit comprehensive risk assessment event
        self.add_domain_event(
            ChallengeRiskAssessment(
                aggregate_id=risk_engine.id,
                user_id=risk_engine.user_id,
                challenge_id=challenge_id,
                risk_score=assessment["risk_score"],
                risk_level=assessment["risk_level"],
                should_halt_trading=should_halt_trading,
                should_fail_challenge=should_fail_challenge,
                critical_violations=critical_violations,
                recommendations=recommendations,
                assessment_timestamp=datetime.utcnow().isoformat(),
            )
        )
        
        # Publish domain events
        for event in risk_engine.domain_events:
            await self.event_bus.publish(event)
        risk_engine.clear_domain_events()
        
        return assessment
    
    async def evaluate_trading_permission(
        self,
        risk_engine: RiskEngine,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> Dict:
        """Evaluate if a trade should be allowed based on risk conditions."""
        
        # Check if trading is halted
        if risk_engine.is_trading_halted:
            return {
                "allowed": False,
                "reason": f"Trading is halted: {risk_engine.halt_reason}",
                "severity": "EMERGENCY",
            }
        
        # Check symbol restrictions
        if not risk_engine.risk_profile.is_symbol_allowed(symbol):
            return {
                "allowed": False,
                "reason": f"Symbol {symbol} is not allowed for trading",
                "severity": "CRITICAL",
            }
        
        # Check trading hours
        if not risk_engine.risk_profile.is_within_trading_hours(datetime.utcnow()):
            return {
                "allowed": False,
                "reason": "Trading outside allowed hours",
                "severity": "WARNING",
            }
        
        # Check daily trade limits
        if (risk_engine.risk_profile.max_daily_trades and 
            risk_engine.daily_trades >= risk_engine.risk_profile.max_daily_trades):
            return {
                "allowed": False,
                "reason": f"Daily trade limit ({risk_engine.risk_profile.max_daily_trades}) exceeded",
                "severity": "CRITICAL",
            }
        
        # Check position size limits
        trade_value = Money(abs(quantity * price), "USD")
        if risk_engine.risk_limits.is_position_size_exceeded(trade_value, risk_engine.current_balance):
            return {
                "allowed": False,
                "reason": "Position size would exceed limits",
                "severity": "CRITICAL",
            }
        
        # Check risk score
        if risk_engine.current_risk_score:
            if risk_engine.current_risk_score.risk_level == RiskLevel.EXTREME:
                return {
                    "allowed": False,
                    "reason": f"Risk level is EXTREME ({risk_engine.current_risk_score.overall_score})",
                    "severity": "EMERGENCY",
                }
            elif risk_engine.current_risk_score.risk_level == RiskLevel.HIGH:
                return {
                    "allowed": True,
                    "reason": f"Risk level is HIGH ({risk_engine.current_risk_score.overall_score}) - trade with caution",
                    "severity": "WARNING",
                }
        
        # Trade is allowed
        return {
            "allowed": True,
            "reason": "Trade meets all risk criteria",
            "severity": "INFO",
        }


class RiskProfileService:
    """Service for managing risk profiles and configurations."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def create_challenge_risk_profile(
        self,
        user_id: UUID,
        challenge_id: UUID,
        challenge_type: str,
        initial_balance: Money,
    ) -> RiskProfile:
        """Create risk profile for a specific challenge type."""
        
        from ..domain.value_objects import RiskThreshold, RiskMetricType, ThresholdType
        
        # Define thresholds based on challenge type
        if challenge_type == "PHASE_1":
            thresholds = [
                RiskThreshold(
                    RiskMetricType.DAILY_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("3"),
                    critical_level=Decimal("5"),
                    emergency_level=Decimal("6"),
                    description="Phase 1 daily drawdown limit",
                ),
                RiskThreshold(
                    RiskMetricType.TOTAL_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("8"),
                    critical_level=Decimal("10"),
                    emergency_level=Decimal("12"),
                    description="Phase 1 total drawdown limit",
                ),
                RiskThreshold(
                    RiskMetricType.POSITION_SIZE,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("10"),
                    critical_level=Decimal("15"),
                    emergency_level=Decimal("20"),
                    description="Phase 1 position size limit",
                ),
                RiskThreshold(
                    RiskMetricType.TRADING_VELOCITY,
                    ThresholdType.ABSOLUTE,
                    warning_level=Decimal("8"),
                    critical_level=Decimal("15"),
                    emergency_level=Decimal("25"),
                    description="Phase 1 trading velocity limit",
                ),
            ]
            
            max_daily_trades = 50
            max_position_size_percent = Decimal("15")
            max_leverage = Decimal("5")
            
        elif challenge_type == "PHASE_2":
            thresholds = [
                RiskThreshold(
                    RiskMetricType.DAILY_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("3"),
                    critical_level=Decimal("5"),
                    emergency_level=Decimal("6"),
                    description="Phase 2 daily drawdown limit",
                ),
                RiskThreshold(
                    RiskMetricType.TOTAL_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("8"),
                    critical_level=Decimal("10"),
                    emergency_level=Decimal("12"),
                    description="Phase 2 total drawdown limit",
                ),
                RiskThreshold(
                    RiskMetricType.POSITION_SIZE,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("8"),
                    critical_level=Decimal("12"),
                    emergency_level=Decimal("15"),
                    description="Phase 2 position size limit (stricter)",
                ),
            ]
            
            max_daily_trades = 40
            max_position_size_percent = Decimal("12")
            max_leverage = Decimal("3")
            
        else:  # FUNDED
            thresholds = [
                RiskThreshold(
                    RiskMetricType.DAILY_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("3"),
                    critical_level=Decimal("5"),
                    emergency_level=Decimal("6"),
                    description="Funded account daily drawdown limit",
                ),
                RiskThreshold(
                    RiskMetricType.TOTAL_DRAWDOWN,
                    ThresholdType.PERCENTAGE,
                    warning_level=Decimal("8"),
                    critical_level=Decimal("10"),
                    emergency_level=Decimal("12"),
                    description="Funded account total drawdown limit",
                ),
            ]
            
            max_daily_trades = None  # No limit for funded accounts
            max_position_size_percent = Decimal("20")
            max_leverage = Decimal("10")
        
        # Create risk profile
        profile = RiskProfile(
            user_id=user_id,
            challenge_id=challenge_id,
            thresholds=thresholds,
            max_daily_trades=max_daily_trades,
            max_position_size_percent=max_position_size_percent,
            max_leverage=max_leverage,
            profile_name=f"{challenge_type}_Profile",
        )
        
        return profile
    
    async def create_risk_limits(
        self,
        challenge_type: str,
        initial_balance: Money,
    ) -> RiskLimits:
        """Create risk limits for a challenge type."""
        
        if challenge_type == "PHASE_1":
            return RiskLimits(
                max_daily_loss_percent=Decimal("5"),
                max_total_loss_percent=Decimal("10"),
                max_position_size_percent=Decimal("15"),
                max_leverage=Decimal("5"),
                max_trades_per_day=50,
                max_trades_per_hour=10,
                currency=initial_balance.currency,
            )
        
        elif challenge_type == "PHASE_2":
            return RiskLimits(
                max_daily_loss_percent=Decimal("5"),
                max_total_loss_percent=Decimal("10"),
                max_position_size_percent=Decimal("12"),
                max_leverage=Decimal("3"),
                max_trades_per_day=40,
                max_trades_per_hour=8,
                currency=initial_balance.currency,
            )
        
        else:  # FUNDED
            return RiskLimits(
                max_daily_loss_percent=Decimal("5"),
                max_total_loss_percent=Decimal("10"),
                max_position_size_percent=Decimal("20"),
                max_leverage=Decimal("10"),
                currency=initial_balance.currency,
            )


class RiskEventHandler:
    """Service for handling risk events and triggering appropriate actions."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def handle_trading_halted(self, event_data: Dict) -> None:
        """Handle trading halted event."""
        # This would typically:
        # 1. Notify challenge engine to halt trading
        # 2. Send alerts to risk management team
        # 3. Log critical event for audit
        # 4. Update challenge status if needed
        
        print(f"🚨 TRADING HALTED for user {event_data['user_id']}: {event_data['reason']}")
    
    async def handle_emergency_risk_event(self, event_data: Dict) -> None:
        """Handle emergency risk event."""
        # This would typically:
        # 1. Immediately fail the challenge
        # 2. Send emergency notifications
        # 3. Escalate to senior risk management
        # 4. Create incident report
        
        print(f"🆘 EMERGENCY RISK EVENT for user {event_data['user_id']}: {event_data['description']}")
    
    async def handle_risk_alert_triggered(self, event_data: Dict) -> None:
        """Handle risk alert triggered event."""
        # This would typically:
        # 1. Send notification to trader
        # 2. Log alert for monitoring
        # 3. Update risk dashboard
        # 4. Trigger automated responses if configured
        
        severity = event_data['severity']
        message = event_data['message']
        print(f"⚠️  RISK ALERT ({severity}): {message}")
    
    async def handle_challenge_risk_assessment(self, event_data: Dict) -> None:
        """Handle comprehensive challenge risk assessment."""
        # This would typically:
        # 1. Update challenge engine with risk assessment
        # 2. Trigger challenge state changes if needed
        # 3. Send risk reports to stakeholders
        # 4. Update risk monitoring dashboards
        
        should_fail = event_data['should_fail_challenge']
        should_halt = event_data['should_halt_trading']
        risk_score = event_data['risk_score']
        
        print(f"📊 RISK ASSESSMENT - Score: {risk_score}, Halt: {should_halt}, Fail: {should_fail}")
        
        if should_fail:
            print("🔴 RECOMMENDATION: Challenge should be FAILED due to critical risk violations")
        elif should_halt:
            print("🟡 RECOMMENDATION: Trading should be HALTED until risk conditions improve")