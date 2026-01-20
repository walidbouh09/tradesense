# Risk Engine Design - Independent Risk Management System

## Overview

The Risk Engine is an **independent domain** that reacts to trading events, computes risk metrics in real-time, triggers alerts, and provides challenge status recommendations. It operates as a **pure risk assessment system** that is fully decoupled from the Trading domain and provides risk intelligence to other domains through events.

## Core Principles

### 1. Event-Driven Architecture
- **Reactive System**: Responds to events from Trading domain without direct coupling
- **Event Emission**: Publishes risk events for other domains to consume
- **Asynchronous Processing**: Non-blocking real-time risk calculations

### 2. Independent Risk Intelligence
- **No Trading Logic**: Contains zero trading execution or order management logic
- **Pure Risk Assessment**: Focuses solely on risk calculation and violation detection
- **Advisory Role**: Provides recommendations but doesn't enforce trading decisions

### 3. Real-Time Monitoring
- **Continuous Assessment**: Updates risk metrics with every trading event
- **Threshold Monitoring**: Constantly evaluates risk against configurable thresholds
- **Immediate Alerts**: Triggers alerts and recommendations in real-time

## Risk Metrics Definitions

### 1. Drawdown Metrics

#### Daily Drawdown
```python
class DrawdownMetric:
    """Daily drawdown calculation."""
    
    # Formula: Daily Drawdown % = |Daily P&L| / Current Balance * 100
    # Triggers: 3% Warning, 5% Critical, 6% Emergency
    
    drawdown_amount: Money      # Absolute drawdown amount
    drawdown_percentage: Decimal # Percentage of account
    peak_balance: Money         # Peak balance for the day
    current_balance: Money      # Current account balance
    is_daily: bool = True       # Daily vs total drawdown
```

#### Total Drawdown
```python
class TotalDrawdown:
    """Total drawdown from peak balance."""
    
    # Formula: Total Drawdown % = (Peak Balance - Current Balance) / Peak Balance * 100
    # Triggers: 8% Warning, 10% Critical, 12% Emergency
    
    max_drawdown: Money         # Maximum drawdown experienced
    current_drawdown: Money     # Current drawdown from peak
    peak_balance: Money         # All-time peak balance
    drawdown_duration: timedelta # How long in drawdown
```

### 2. Position Risk Metrics

#### Position Size Risk
```python
class PositionRiskMetric:
    """Individual position risk assessment."""
    
    # Formula: Position Size % = Position Value / Account Balance * 100
    # Triggers: 10% Warning, 15% Critical, 20% Emergency
    
    symbol: str                 # Trading symbol
    position_size: Money        # Position value
    account_balance: Money      # Current account balance
    leverage: Decimal           # Position leverage
    unrealized_pnl: Money       # Current unrealized P&L
    size_percentage: Decimal    # Position as % of account
```

#### Position Concentration
```python
class ConcentrationRisk:
    """Portfolio concentration risk."""
    
    # Formula: Concentration = Largest Position / Total Portfolio * 100
    # Triggers: 25% Warning, 35% Critical, 50% Emergency
    
    largest_position_percent: Decimal    # Largest single position %
    top_3_positions_percent: Decimal     # Top 3 positions combined %
    symbol_count: int                    # Number of different symbols
    sector_concentration: Dict[str, Decimal] # Sector exposure breakdown
```

### 3. Trading Activity Metrics

#### Trading Velocity
```python
class TradingVelocityMetric:
    """Trading frequency and velocity assessment."""
    
    # Formula: Velocity = Trades per Hour over rolling window
    # Triggers: 8/hour Warning, 15/hour Critical, 25/hour Emergency
    
    trades_per_hour: Decimal    # Current trading rate
    trades_per_day: int         # Daily trade count
    average_trade_size: Money   # Average trade value
    total_volume: Money         # Total trading volume
    time_window_hours: int      # Measurement window
```

#### Trading Pattern Risk
```python
class TradingPatternRisk:
    """Unusual trading pattern detection."""
    
    # Detects: Revenge trading, overtrading, pattern deviations
    
    consecutive_losses: int     # Consecutive losing trades
    trade_size_deviation: Decimal # Deviation from normal size
    time_concentration: Dict    # Trading time distribution
    symbol_switching_rate: Decimal # Frequency of symbol changes
```

### 4. Volatility Metrics

#### P&L Volatility
```python
class VolatilityMetric:
    """P&L volatility assessment."""
    
    # Formula: Volatility = Standard Deviation of Daily Returns
    # Triggers: 2% Warning, 4% Critical, 6% Emergency (daily)
    
    volatility: Decimal         # Daily volatility
    annualized_volatility: Decimal # Annualized volatility
    returns: List[Decimal]      # Historical daily returns
    time_period_days: int       # Calculation period
    sharpe_ratio: Optional[Decimal] # Risk-adjusted returns
```

### 5. Correlation and Exposure Metrics

#### Symbol Correlation Risk
```python
class CorrelationRisk:
    """Cross-position correlation risk."""
    
    # Measures correlation between open positions
    # Triggers: 0.7 Warning, 0.8 Critical, 0.9 Emergency
    
    correlation_matrix: Dict    # Symbol correlation matrix
    max_correlation: Decimal    # Highest correlation between positions
    correlated_exposure: Money  # Total exposure in correlated positions
    diversification_ratio: Decimal # Portfolio diversification measure
```

## Event Consumption Flow

### 1. Trading Domain Events → Risk Engine

```
Trading Domain Events:
├── TradeExecuted
├── PositionOpened
├── PositionClosed
├── PositionUpdated
├── DailyPnLCalculated
└── PriceUpdated

↓ Event Bus ↓

Risk Engine Processing:
├── process_trade_event()
├── process_position_event()
├── process_pnl_event()
└── update_market_prices()

↓ Risk Calculations ↓

Risk Metrics Updated:
├── Drawdown calculations
├── Position risk assessment
├── Trading velocity analysis
├── Volatility calculations
└── Overall risk score
```

### 2. Event Processing Pipeline

```python
# Event consumption flow
async def handle_trade_executed(event: TradeExecuted):
    """Process trade execution event."""
    
    # 1. Extract trade data
    trade_data = {
        "symbol": event.symbol,
        "side": event.side,
        "quantity": event.quantity,
        "price": event.price,
        "net_value": event.net_value,
        "commission": event.commission,
        "executed_at": event.executed_at,
    }
    
    # 2. Update risk engine
    risk_engine = get_risk_engine(event.user_id)
    await risk_monitoring_service.process_trade_executed_event(
        risk_engine, trade_data
    )
    
    # 3. Risk engine automatically:
    #    - Updates trading velocity metrics
    #    - Checks symbol restrictions
    #    - Validates trading hours
    #    - Triggers alerts if thresholds violated
    #    - Emits risk events

async def handle_position_updated(event: PositionUpdated):
    """Process position update event."""
    
    # 1. Extract position data
    position_data = {
        "symbol": event.symbol,
        "side": event.side,
        "quantity": event.new_quantity,
        "entry_price": event.new_entry_price,
        "unrealized_pnl": event.unrealized_pnl,
    }
    
    # 2. Update risk engine
    risk_engine = get_risk_engine(event.user_id)
    await risk_monitoring_service.process_position_event(
        risk_engine, position_data, "UPDATED"
    )
    
    # 3. Risk engine automatically:
    #    - Recalculates position risk metrics
    #    - Updates concentration risk
    #    - Checks position size limits
    #    - Updates total exposure
    #    - Emits position risk events

async def handle_daily_pnl_calculated(event: DailyPnLCalculated):
    """Process daily P&L event."""
    
    # 1. Extract P&L data
    pnl_data = {
        "current_balance": event.current_balance,
        "daily_pnl": event.daily_pnl,
        "total_pnl": event.total_pnl,
        "total_unrealized_pnl": event.total_unrealized_pnl,
        "date": event.date,
    }
    
    # 2. Update risk engine
    risk_engine = get_risk_engine(event.user_id)
    await risk_monitoring_service.process_pnl_event(
        risk_engine, pnl_data
    )
    
    # 3. Risk engine automatically:
    #    - Calculates drawdown metrics
    #    - Updates volatility calculations
    #    - Recalculates overall risk score
    #    - Checks drawdown thresholds
    #    - Emits risk assessment events
```

## Violation Detection Logic

### 1. Threshold-Based Detection

```python
class ThresholdViolationDetector:
    """Detects when risk metrics exceed thresholds."""
    
    def evaluate_metric(self, metric: RiskMetric, threshold: RiskThreshold) -> AlertSeverity:
        """Evaluate metric against threshold levels."""
        
        value = abs(metric.value)
        
        # Emergency level (immediate action required)
        if threshold.emergency_level and value >= threshold.emergency_level:
            return AlertSeverity.EMERGENCY
        
        # Critical level (significant risk)
        elif value >= threshold.critical_level:
            return AlertSeverity.CRITICAL
        
        # Warning level (elevated risk)
        elif value >= threshold.warning_level:
            return AlertSeverity.WARNING
        
        # Normal level
        else:
            return AlertSeverity.INFO
    
    def check_drawdown_violation(self, drawdown: DrawdownMetric) -> Optional[RiskAlert]:
        """Check drawdown against limits."""
        
        threshold = get_threshold(RiskMetricType.DAILY_DRAWDOWN if drawdown.is_daily else RiskMetricType.TOTAL_DRAWDOWN)
        severity = self.evaluate_metric(drawdown, threshold)
        
        if severity != AlertSeverity.INFO:
            return RiskAlert(
                alert_id=f"DRAWDOWN_{drawdown.metric_type}_{datetime.now().strftime('%Y%m%d')}",
                metric=drawdown,
                threshold=threshold,
                severity=severity,
                message=f"{'Daily' if drawdown.is_daily else 'Total'} drawdown {drawdown.drawdown_percentage:.2f}% exceeds {threshold.warning_level}% threshold",
            )
        
        return None
```

### 2. Pattern-Based Detection

```python
class PatternViolationDetector:
    """Detects risky trading patterns."""
    
    def detect_revenge_trading(self, recent_trades: List[Trade]) -> Optional[RiskAlert]:
        """Detect revenge trading pattern."""
        
        # Look for increasing position sizes after losses
        consecutive_losses = 0
        size_increases = 0
        
        for i, trade in enumerate(recent_trades[-10:]):  # Last 10 trades
            if trade.realized_pnl < 0:
                consecutive_losses += 1
                
                # Check if next trade has larger size
                if i < len(recent_trades) - 1:
                    next_trade = recent_trades[i + 1]
                    if next_trade.quantity > trade.quantity * 1.5:  # 50% size increase
                        size_increases += 1
        
        # Trigger alert if pattern detected
        if consecutive_losses >= 3 and size_increases >= 2:
            return RiskAlert(
                alert_id=f"REVENGE_TRADING_{datetime.now().strftime('%Y%m%d_%H%M')}",
                severity=AlertSeverity.CRITICAL,
                message=f"Revenge trading pattern detected: {consecutive_losses} consecutive losses with increasing position sizes",
            )
        
        return None
    
    def detect_overtrading(self, trading_velocity: TradingVelocityMetric) -> Optional[RiskAlert]:
        """Detect overtrading pattern."""
        
        # Check if trading velocity is significantly above normal
        if trading_velocity.trades_per_hour > 15:  # More than 15 trades per hour
            return RiskAlert(
                alert_id=f"OVERTRADING_{datetime.now().strftime('%Y%m%d_%H')}",
                severity=AlertSeverity.WARNING,
                message=f"Overtrading detected: {trading_velocity.trades_per_hour:.1f} trades per hour",
            )
        
        return None
```

### 3. Correlation-Based Detection

```python
class CorrelationViolationDetector:
    """Detects correlation-based risks."""
    
    def detect_concentration_risk(self, positions: List[Position]) -> Optional[RiskAlert]:
        """Detect portfolio concentration risk."""
        
        if not positions:
            return None
        
        # Calculate position sizes as percentage of total
        total_exposure = sum(pos.position_value.amount for pos in positions)
        position_percentages = [(pos.symbol, pos.position_value.amount / total_exposure * 100) for pos in positions]
        
        # Find largest position
        largest_position = max(position_percentages, key=lambda x: x[1])
        
        # Check concentration threshold
        if largest_position[1] > 35:  # More than 35% in single position
            return RiskAlert(
                alert_id=f"CONCENTRATION_{largest_position[0]}",
                severity=AlertSeverity.CRITICAL,
                message=f"High concentration risk: {largest_position[1]:.1f}% in {largest_position[0]}",
            )
        
        return None
```

## Events Emitted by Risk Engine

### 1. Alert Events

```python
# Risk alert triggered
RiskAlertTriggered(
    alert_id: str,              # Unique alert identifier
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID (if applicable)
    metric_type: str,           # Type of risk metric
    metric_value: str,          # Current metric value
    severity: str,              # Alert severity level
    message: str,               # Human-readable alert message
    requires_action: bool,      # Whether immediate action is required
)

# Risk alert resolved
RiskAlertResolved(
    alert_id: str,              # Alert that was resolved
    user_id: UUID,              # Trader ID
    resolution_reason: str,     # Why alert was resolved
    alert_duration_seconds: int, # How long alert was active
)
```

### 2. Risk Assessment Events

```python
# Overall risk score calculated
RiskScoreCalculated(
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID
    risk_score: Decimal,        # Overall risk score (0-100)
    risk_level: str,            # Risk level (MINIMAL/LOW/MEDIUM/HIGH/EXTREME)
    component_scores: Dict,     # Individual component scores
    active_alerts_count: int,   # Number of active alerts
    critical_alerts_count: int, # Number of critical alerts
)

# Comprehensive challenge risk assessment
ChallengeRiskAssessment(
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID
    risk_score: Decimal,        # Current risk score
    risk_level: str,            # Risk level
    should_halt_trading: bool,  # Recommendation to halt trading
    should_fail_challenge: bool, # Recommendation to fail challenge
    critical_violations: List[str], # List of critical violations
    recommendations: List[str], # Risk management recommendations
)
```

### 3. Trading Control Events

```python
# Trading halted due to risk
TradingHalted(
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID
    reason: str,                # Reason for halt
    severity: str,              # Severity level
    halted_at: str,             # Halt timestamp
    current_risk_score: Decimal, # Risk score at halt
    active_alerts_count: int,   # Number of active alerts
)

# Trading resumed after risk resolution
TradingResumed(
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID
    reason: str,                # Reason for resumption
    resumed_at: str,            # Resume timestamp
    halt_duration_seconds: int, # How long trading was halted
    current_risk_score: Decimal, # Risk score at resume
)

# Emergency risk event
EmergencyRiskEvent(
    user_id: UUID,              # Trader ID
    challenge_id: UUID,         # Challenge ID
    event_type: str,            # Type of emergency
    description: str,           # Emergency description
    risk_score: Decimal,        # Current risk score
    requires_manual_intervention: bool, # Needs human intervention
)
```

### 4. Specific Risk Events

```python
# Drawdown limit exceeded
DrawdownLimitExceeded(
    user_id: UUID,              # Trader ID
    drawdown_type: str,         # DAILY or TOTAL
    drawdown_amount: str,       # Drawdown amount
    drawdown_percentage: str,   # Drawdown percentage
    limit_percentage: str,      # Limit that was exceeded
    peak_balance: str,          # Peak balance
    current_balance: str,       # Current balance
    severity: str,              # Violation severity
)

# Position risk exceeded
PositionRiskExceeded(
    user_id: UUID,              # Trader ID
    symbol: str,                # Trading symbol
    position_size: str,         # Position size
    position_percentage: str,   # Position as % of account
    limit_percentage: str,      # Limit that was exceeded
    account_balance: str,       # Current account balance
    severity: str,              # Violation severity
)

# Trading velocity exceeded
TradingVelocityExceeded(
    user_id: UUID,              # Trader ID
    trades_per_hour: str,       # Current trading rate
    trades_per_day: int,        # Daily trade count
    limit_per_hour: str,        # Hourly limit exceeded
    severity: str,              # Violation severity
)
```

## Integration with Other Domains

### 1. Challenge Engine Integration

```python
# Risk Engine → Challenge Engine
@event_handler(ChallengeRiskAssessment)
async def handle_risk_assessment(event: ChallengeRiskAssessment):
    """Challenge engine responds to risk assessment."""
    
    challenge = find_challenge(event.challenge_id)
    
    if event.should_fail_challenge:
        # Fail challenge due to critical risk violations
        challenge.fail_challenge(
            reason=f"Risk violations: {'; '.join(event.critical_violations)}",
            failed_by=None,  # Automatic failure
        )
    
    elif event.should_halt_trading:
        # Update challenge to halt trading
        challenge.halt_trading(
            reason=f"Risk level {event.risk_level} (score: {event.risk_score})"
        )

@event_handler(TradingHalted)
async def handle_trading_halted(event: TradingHalted):
    """Challenge engine responds to trading halt."""
    
    challenge = find_challenge(event.challenge_id)
    challenge.set_trading_status("HALTED", event.reason)

@event_handler(EmergencyRiskEvent)
async def handle_emergency_risk(event: EmergencyRiskEvent):
    """Challenge engine responds to emergency risk."""
    
    challenge = find_challenge(event.challenge_id)
    challenge.fail_challenge(
        reason=f"Emergency risk event: {event.description}",
        failed_by=None,  # Automatic failure
    )
```

### 2. Rules Engine Integration

```python
# Risk Engine → Rules Engine
@event_handler(RiskThresholdViolated)
async def handle_threshold_violation(event: RiskThresholdViolated):
    """Rules engine evaluates threshold violations."""
    
    rule_engine = get_rule_engine(event.user_id)
    
    # Create rule evaluation context from risk data
    context = {
        "risk_score": event.actual_value,
        "threshold_type": event.threshold_type,
        "violation_severity": event.severity,
        "violation_percentage": event.violation_percentage,
    }
    
    # Evaluate risk-related rules
    await rule_engine.evaluate_rules(
        context=context,
        rule_types=[RuleType.MAX_DAILY_DRAWDOWN, RuleType.MAX_TOTAL_DRAWDOWN],
        tags=["risk", "critical"],
    )
```

### 3. Notification System Integration

```python
# Risk Engine → Notification System
@event_handler(RiskAlertTriggered)
async def handle_risk_alert(event: RiskAlertTriggered):
    """Send notifications for risk alerts."""
    
    if event.severity in ["CRITICAL", "EMERGENCY"]:
        # Send immediate notification to trader
        await notification_service.send_immediate_alert(
            user_id=event.user_id,
            title=f"Risk Alert: {event.metric_type}",
            message=event.message,
            severity=event.severity,
        )
        
        # Notify risk management team for critical alerts
        if event.severity == "EMERGENCY":
            await notification_service.send_emergency_alert(
                recipients=["risk-team@tradesense.ai"],
                title=f"Emergency Risk Alert - User {event.user_id}",
                message=event.message,
                challenge_id=event.challenge_id,
            )
```

## Risk Engine Architecture

### 1. Domain Structure

```
src/domains/risk/
├── domain/
│   ├── entities.py          # RiskEngine aggregate
│   ├── value_objects.py     # Risk metrics, thresholds, alerts
│   └── events.py           # Risk domain events
├── application/
│   └── services.py         # Risk monitoring, assessment services
├── infrastructure/
│   ├── models.py           # Database models
│   └── repositories.py     # Risk data persistence
└── api/
    ├── schemas.py          # API request/response schemas
    └── routers.py          # Risk management endpoints
```

### 2. Event Flow Architecture

```
External Events → Risk Engine → Risk Events → Other Domains

Trading Domain:
├── TradeExecuted ────────┐
├── PositionOpened ───────┤
├── PositionClosed ───────┤
├── DailyPnLCalculated ───┤
└── PriceUpdated ─────────┤
                          │
                          ▼
                    Risk Engine:
                    ├── Process Events
                    ├── Calculate Metrics
                    ├── Check Thresholds
                    ├── Generate Alerts
                    └── Emit Risk Events
                          │
                          ▼
                    Risk Events:
                    ├── RiskAlertTriggered ──────► Challenge Engine
                    ├── TradingHalted ───────────► Challenge Engine
                    ├── EmergencyRiskEvent ──────► Challenge Engine
                    ├── RiskScoreCalculated ─────► Rules Engine
                    └── ChallengeRiskAssessment ─► Challenge Engine
```

### 3. Real-Time Processing Pipeline

```
Event Received → Risk Calculation → Threshold Check → Alert Generation → Event Emission

1. Event Processing:
   ├── Validate event data
   ├── Extract relevant metrics
   ├── Update risk engine state
   └── Trigger calculations

2. Risk Calculation:
   ├── Update drawdown metrics
   ├── Recalculate position risks
   ├── Update trading velocity
   ├── Calculate volatility
   └── Compute overall risk score

3. Threshold Evaluation:
   ├── Compare metrics to thresholds
   ├── Determine alert severity
   ├── Check for pattern violations
   └── Evaluate correlation risks

4. Alert Management:
   ├── Create risk alerts
   ├── Resolve outdated alerts
   ├── Escalate critical alerts
   └── Log all alert activity

5. Event Emission:
   ├── Publish risk events
   ├── Send to event bus
   ├── Notify subscribed domains
   └── Update monitoring systems
```

## Summary

The Risk Engine provides **independent, real-time risk intelligence** that:

1. **Reacts** to trading events without direct coupling to Trading domain
2. **Computes** comprehensive risk metrics using financial-grade calculations
3. **Triggers** alerts and recommendations based on configurable thresholds
4. **Emits** events for other domains to make informed decisions
5. **Maintains** complete decoupling while providing critical risk oversight

**Key Benefits:**
- **Real-time risk monitoring** with immediate alert generation
- **Configurable thresholds** for different challenge types and risk profiles
- **Pattern detection** for identifying risky trading behaviors
- **Event-driven integration** enabling loose coupling between domains
- **Comprehensive risk assessment** supporting challenge management decisions
- **Audit trail** of all risk calculations and alert activities

The Risk Engine serves as the **risk intelligence center** of the prop trading platform, providing continuous oversight and recommendations while maintaining strict domain boundaries and enabling other systems to make informed risk-based decisions.