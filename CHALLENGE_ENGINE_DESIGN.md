# Challenge Engine Design - Prop Trading Firm

## State Machine Overview

```
Challenge State Machine - Immutable Transitions:

    ┌─────────┐
    │ PENDING │ ◄─── Initial state when challenge is created
    └────┬────┘
         │ start_challenge()
         │ ✓ Trader initiates challenge
         ▼
    ┌─────────┐
    │ ACTIVE  │ ◄─── Trading allowed, rules monitored
    └────┬────┘
         │
         ├─── pass_challenge() ────────┐
         │    ✓ All requirements met    │
         │                             ▼
         │                        ┌─────────┐
         │                        │ FUNDED  │ ◄─── Terminal: Trader funded
         │                        └─────────┘
         │
         ├─── fail_challenge() ────────┐
         │    ✗ Manual failure         │
         │                             │
         ├─── risk_violation() ────────┤
         │    ✗ Auto-failure           ▼
         │                        ┌─────────┐
         └─── expire() ────────────► │ FAILED  │ ◄─── Terminal: Challenge failed
              ✗ Time limit reached  └─────────┘

Legal Transitions:
✓ PENDING → ACTIVE    (start_challenge)
✓ ACTIVE → FUNDED     (pass_challenge)
✓ ACTIVE → FAILED     (fail_challenge, risk_violation, expire)

Illegal Transitions (Blocked):
✗ PENDING → FUNDED    (must go through ACTIVE)
✗ PENDING → FAILED    (must go through ACTIVE)
✗ FUNDED → any state  (terminal state)
✗ FAILED → any state  (terminal state)
✗ Any backward transitions
```

## Domain Rules

### 1. Challenge Lifecycle Rules

```typescript
// Core Business Rules
- Only one ACTIVE challenge per trader at any time
- Challenge must be started before any trading activity
- Challenge cannot be restarted once FAILED or FUNDED
- Challenge has maximum duration (configurable per type)
- No multiple funding for same trader (financial regulation)
```

### 2. Trading Permission Rules

```typescript
// Trading Access Control
State.PENDING: trading = FORBIDDEN
State.ACTIVE:  trading = ALLOWED
State.FAILED:  trading = FORBIDDEN  
State.FUNDED:  trading = ALLOWED (live capital)
```

### 3. Risk Management Rules

```typescript
// Automatic Failure Triggers
- Daily loss limit violation → immediate FAILED transition
- Total loss limit violation → immediate FAILED transition
- Position size limit violation → trading halt + warning
- Forbidden instrument trading → immediate FAILED transition
- Time limit exceeded → FAILED (unless requirements met)

// Risk Rule Examples:
- Max daily loss: 5% of account balance
- Max total loss: 10% of initial balance
- Max position size: 10% of account balance
- Min trading days: 5 days minimum activity
- Consistency rule: No single day > 50% of total profit
```

### 4. Completion Requirements

```typescript
// Requirements for FUNDED transition:
✓ Profit target achieved (e.g., 8% of initial balance)
✓ Minimum trading days completed (e.g., 5 days)
✓ No critical risk violations
✓ Consistency requirements met
✓ Within time limit
```

## Transition Validation Logic

### State Transition Guards

```python
def can_transition_to(current_state: ChallengeState, target_state: ChallengeState) -> bool:
    """Validate state transitions with immutable rules."""
    
    valid_transitions = {
        ChallengeState.PENDING: [ChallengeState.ACTIVE],
        ChallengeState.ACTIVE: [ChallengeState.FAILED, ChallengeState.FUNDED],
        ChallengeState.FAILED: [],  # Terminal - no transitions allowed
        ChallengeState.FUNDED: [], # Terminal - no transitions allowed
    }
    
    return target_state in valid_transitions.get(current_state, [])

def validate_start_challenge(challenge: Challenge) -> None:
    """Validate challenge start conditions."""
    if challenge.state != ChallengeState.PENDING:
        raise IllegalTransitionError(f"Cannot start challenge in {challenge.state} state")
    
    # Additional business rule validations
    if trader_has_active_challenge(challenge.trader_id):
        raise BusinessRuleViolationError("Trader already has active challenge")
    
    if trader_has_funded_account(challenge.trader_id):
        raise BusinessRuleViolationError("Multiple funding not allowed")

def validate_pass_challenge(challenge: Challenge) -> None:
    """Validate challenge pass conditions."""
    if challenge.state != ChallengeState.ACTIVE:
        raise IllegalTransitionError(f"Cannot pass challenge in {challenge.state} state")
    
    if not are_pass_requirements_met(challenge):
        raise BusinessRuleViolationError("Challenge requirements not met")

def validate_fail_challenge(challenge: Challenge) -> None:
    """Validate challenge failure conditions."""
    if challenge.state != ChallengeState.ACTIVE:
        raise IllegalTransitionError(f"Cannot fail challenge in {challenge.state} state")
```

## Events Emitted on Transitions

### 1. PENDING → ACTIVE (Challenge Started)

```python
Events Emitted:
├── ChallengeStarted
│   ├── aggregate_id: UUID
│   ├── trader_id: UUID
│   ├── challenge_type: str
│   ├── initial_balance: str
│   ├── profit_target: str
│   └── max_duration_days: int
│
└── ChallengeStateChanged
    ├── aggregate_id: UUID
    ├── trader_id: UUID
    ├── old_state: "PENDING"
    ├── new_state: "ACTIVE"
    ├── reason: "Challenge started"
    └── changed_by: UUID (optional)
```

### 2. ACTIVE → FUNDED (Challenge Passed)

```python
Events Emitted:
├── ChallengeStateChanged
│   ├── old_state: "ACTIVE"
│   ├── new_state: "FUNDED"
│   └── reason: "Challenge requirements met"
│
├── ChallengePassed
│   ├── aggregate_id: UUID
│   ├── trader_id: UUID
│   ├── challenge_type: str
│   ├── final_balance: str
│   ├── total_profit: str
│   ├── trading_days: int
│   └── performance_metrics: Dict
│
└── TraderFunded (when funding is processed)
    ├── aggregate_id: UUID
    ├── trader_id: UUID
    ├── funded_amount: str
    ├── profit_split_percent: int
    └── funding_date: str
```

### 3. ACTIVE → FAILED (Challenge Failed)

```python
Events Emitted:
├── ChallengeStateChanged
│   ├── old_state: "ACTIVE"
│   ├── new_state: "FAILED"
│   └── reason: str (failure reason)
│
├── ChallengeFailed
│   ├── aggregate_id: UUID
│   ├── trader_id: UUID
│   ├── failure_reason: str
│   ├── risk_violations: List[Dict]
│   ├── final_balance: str
│   └── trading_days: int
│
└── RiskViolationDetected (if caused by risk violation)
    ├── aggregate_id: UUID
    ├── trader_id: UUID
    ├── rule_name: str
    ├── violation_type: str
    ├── severity: str
    ├── description: str
    ├── current_value: str
    ├── limit_value: str
    └── auto_failed: bool
```

### 4. Continuous Monitoring Events

```python
Real-time Events:
├── TradingMetricsUpdated
│   ├── total_pnl: str
│   ├── daily_pnl: str
│   ├── trading_days: int
│   ├── total_trades: int
│   └── current_balance: str
│
├── RiskViolationDetected
│   ├── rule_name: str
│   ├── violation_type: str
│   ├── severity: "LOW|MEDIUM|HIGH|CRITICAL"
│   └── auto_failed: bool
│
└── ChallengeExpired
    ├── started_at: str
    ├── expired_at: str
    ├── max_duration_days: int
    └── final_state: str
```

## Risk Rules Implementation

### Risk Rule Types

```python
class RiskRule:
    """Configurable risk rule with validation logic."""
    
    # Loss Limits
    max_daily_loss: Optional[Money]           # Absolute daily loss limit
    max_daily_loss_percent: Optional[Decimal] # Percentage daily loss limit
    max_total_loss: Optional[Money]           # Absolute total loss limit
    max_total_loss_percent: Optional[Decimal] # Percentage total loss limit
    
    # Position Limits
    max_position_size: Optional[Money]        # Maximum position size
    max_leverage: Optional[Decimal]           # Maximum leverage ratio
    
    # Trading Requirements
    min_trading_days: Optional[int]           # Minimum trading days
    allowed_instruments: List[str]            # Allowed trading instruments
    forbidden_strategies: List[str]           # Forbidden trading strategies
    
    # Consistency Rules
    max_single_day_profit_percent: Optional[Decimal] # Max % of profit from one day

# Example Risk Rules Configuration:
PHASE_1_RULES = [
    RiskRule(
        name="Daily Loss Limit",
        max_daily_loss_percent=Decimal("5.0"),  # 5% max daily loss
        severity="CRITICAL"
    ),
    RiskRule(
        name="Total Loss Limit", 
        max_total_loss_percent=Decimal("10.0"), # 10% max total loss
        severity="CRITICAL"
    ),
    RiskRule(
        name="Position Size Limit",
        max_position_size_percent=Decimal("10.0"), # 10% max position
        severity="HIGH"
    ),
    RiskRule(
        name="Minimum Trading Days",
        min_trading_days=5,
        severity="MEDIUM"
    )
]
```

### Automatic Risk Monitoring

```python
def check_risk_violations(challenge: Challenge, trading_update: TradingUpdate) -> List[RiskViolation]:
    """Real-time risk violation checking."""
    
    violations = []
    
    for rule in challenge.parameters.risk_rules:
        # Check daily loss violation
        if rule.max_daily_loss_percent:
            daily_loss_percent = abs(trading_update.daily_pnl) / challenge.current_balance * 100
            if daily_loss_percent > rule.max_daily_loss_percent:
                violations.append(RiskViolation(
                    rule_name=rule.name,
                    violation_type="daily_loss",
                    severity="CRITICAL",
                    current_value=str(daily_loss_percent),
                    limit_value=str(rule.max_daily_loss_percent)
                ))
        
        # Check total loss violation
        if rule.max_total_loss_percent:
            total_loss_percent = abs(challenge.total_pnl) / challenge.initial_balance * 100
            if total_loss_percent > rule.max_total_loss_percent:
                violations.append(RiskViolation(
                    rule_name=rule.name,
                    violation_type="total_loss", 
                    severity="CRITICAL",
                    current_value=str(total_loss_percent),
                    limit_value=str(rule.max_total_loss_percent)
                ))
    
    return violations

def process_risk_violations(challenge: Challenge, violations: List[RiskViolation]) -> None:
    """Process detected risk violations."""
    
    for violation in violations:
        # Emit risk violation event
        challenge.add_domain_event(RiskViolationDetected(...))
        
        # Auto-fail on critical violations
        if violation.severity == "CRITICAL":
            challenge.fail_challenge(f"Risk violation: {violation.description}")
            break
```

## Audit Trail & Immutability

### Complete Audit Trail

```python
# Every state transition is fully auditable:
1. State change events with before/after states
2. Reason for transition (manual/automatic)
3. User who initiated change (if manual)
4. Timestamp of transition
5. All risk violations leading to failure
6. Complete trading metrics at time of transition
7. Challenge parameters and rule violations

# Immutable Event Store:
- All events are append-only
- No modification of historical events
- Complete reconstruction of challenge state from events
- Regulatory compliance with full audit trail
```

### Financial Compliance Features

```python
# Regulatory Requirements:
✓ Complete audit trail of all decisions
✓ Immutable state transitions (no backdating)
✓ Risk rule violations automatically recorded
✓ No manual override of critical risk rules
✓ All funding decisions fully documented
✓ Challenge parameters locked once started
✓ Trader eligibility checks enforced
✓ Multiple funding prevention
```

## Usage Examples

### Starting a Challenge

```python
# Create challenge with parameters
parameters = ChallengeParameters(
    challenge_type=ChallengeType.PHASE_1,
    initial_balance=Money(100000, "USD"),
    profit_target=ProfitTarget(Money(8000, "USD")),
    risk_rules=PHASE_1_RULES,
    max_duration_days=30,
    min_trading_days=5
)

challenge = Challenge(trader_id=trader_id, parameters=parameters)

# Start challenge (PENDING → ACTIVE)
challenge.start_challenge(started_by=admin_user_id)

# Events emitted: ChallengeStarted, ChallengeStateChanged
```

### Processing Trading Updates

```python
# Update trading metrics
challenge.update_trading_metrics(
    new_balance=Money(102000, "USD"),
    daily_pnl=Money(2000, "USD"),
    trade_count=5,
    winning_trades=3,
    losing_trades=2
)

# Automatic checks:
# - Risk rule violations
# - Completion requirements
# - Auto-transition to FUNDED if requirements met
# - Auto-transition to FAILED if violations detected

# Events emitted: TradingMetricsUpdated, possibly ChallengePassed/Failed
```

### Risk Violation Handling

```python
# Risk violation detected during trading
if daily_loss > max_daily_loss:
    # Automatic failure - no manual intervention possible
    challenge.fail_challenge("Daily loss limit exceeded")
    
    # Events emitted:
    # - RiskViolationDetected
    # - ChallengeStateChanged (ACTIVE → FAILED)  
    # - ChallengeFailed
    
    # Result: Trading immediately halted, challenge terminated
```

This Challenge Engine design ensures:
- **Immutable state transitions** with complete audit trail
- **Automatic risk management** with no manual overrides
- **Financial compliance** with regulatory requirements
- **Real-time monitoring** and violation detection
- **Complete auditability** of all decisions and state changes

The system prevents all illegal transitions and maintains data integrity while providing comprehensive tracking for regulatory compliance.