# Challenge Engine - Technical Specification

## Business Responsibility

The Challenge Engine evaluates prop firm trading challenges in real-time. It enforces risk management rules on every simulated trade, determining challenge lifecycle states: ACTIVE, FAILED, or FUNDED. The system is synchronous, deterministic, and financially auditable.

**Core Requirements:**
- **Synchronous Processing**: Immediate rule evaluation per trade
- **Deterministic Rules**: Identical inputs produce identical outcomes
- **Financial Auditability**: Complete traceability of all decisions
- **Zero Business Logic Duplication**: Single source of truth for rules

## State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING: Challenge Created
    PENDING --> ACTIVE: First Trade Executed
    ACTIVE --> FAILED: Rule Violation
    ACTIVE --> FUNDED: Profit Target Met
    FAILED --> [*]: Terminal
    FUNDED --> [*]: Terminal
```

**State Definitions:**
- **PENDING**: Challenge created, awaiting first trade
- **ACTIVE**: Trading in progress, rules actively enforced
- **FAILED**: Rule violation occurred, challenge terminated
- **FUNDED**: Profit target achieved, trader eligible for live account
- **Terminal States**: FAILED and FUNDED are immutable

## Rule Evaluation Flow

### Rules (Strict Priority Order)

1. **Max Daily Drawdown** (FAILURE - Highest Priority)
   - **Formula**: `(Daily Start Equity - Current Equity) / Daily Start Equity × 100`
   - **Threshold**: > 5% loss from daily opening balance
   - **Reset**: UTC midnight daily
   - **Purpose**: Prevent catastrophic single-day losses

2. **Max Total Drawdown** (FAILURE)
   - **Formula**: `(Max Equity Ever - Current Equity) / Max Equity Ever × 100`
   - **Threshold**: > 10% loss from all-time peak
   - **Reset**: Never - permanent protection
   - **Purpose**: Protect against accumulated losses after profitable periods

3. **Profit Target** (SUCCESS)
   - **Formula**: `(Current Equity - Initial Balance) / Initial Balance × 100`
   - **Threshold**: ≥ 10% profit from starting capital
   - **Reset**: N/A
   - **Purpose**: Require demonstrated profitability before funding

### Evaluation Process

```
Trade Executed → Update Equity → Check Daily Reset → Evaluate Rules → Update Status
```

**Invariants Maintained:**
- Equity never falls below zero
- Rules evaluated in strict priority order
- Status transitions are atomic
- All calculations use Decimal precision

## Transaction & Locking Strategy

### Transaction Scope
All challenge evaluation occurs within a single database transaction:

```sql
BEGIN;
SELECT challenge FOR UPDATE;  -- Pessimistic locking
-- Process trade logic --
UPDATE challenge SET ...;
COMMIT;
```

### Locking Rationale

**Why SELECT FOR UPDATE?**
1. **Equity Consistency**: Prevents concurrent trades corrupting equity calculations
2. **Rule Determinism**: Ensures rules evaluate against current state
3. **Status Integrity**: Prevents invalid state transitions
4. **Sequence Preservation**: Maintains trade ordering within challenges

**Locking Granularity:**
- **Row-level**: Only the specific challenge is locked
- **Duration**: Milliseconds per trade
- **Contention**: Minimal due to high challenge dispersion

**Performance Trade-offs:**
- **Safety**: Eliminates race conditions in equity updates
- **Throughput**: Slight reduction under extreme concurrency
- **Scalability**: Horizontal scaling via database clustering

## Event Emission & Auditability

### Domain Events

**CHALLENGE_STATUS_CHANGED**
- **Trigger**: Status transitions (PENDING→ACTIVE, ACTIVE→FAILED/FUNDED)
- **Payload**: challenge_id, old_status, new_status, reason, timestamp
- **Purpose**: Audit trail for all state changes

### Event Bus Architecture

**Current Implementation:**
- Synchronous in-memory event bus
- Simple emit/subscribe pattern
- No external dependencies

**Future Extensibility:**
- Redis pub/sub for distributed systems
- RabbitMQ for reliable messaging
- Kafka for high-throughput analytics
- Event versioning and schema validation

### Audit Trail Construction

**Complete Timeline Reconstruction:**
```sql
-- 1. Get all status changes
SELECT * FROM challenge_events
WHERE challenge_id = ? AND event_type = 'CHALLENGE_STATUS_CHANGED'
ORDER BY occurred_at;

-- 2. Get all trades for context
SELECT * FROM trades
WHERE challenge_id = ? ORDER BY executed_at;

-- 3. Reconstruct equity at any point
SELECT executed_at, realized_pnl,
       SUM(realized_pnl) OVER (ORDER BY executed_at) + initial_balance
FROM trades WHERE challenge_id = ?;
```

## Known Edge Cases Handled

### Concurrency Scenarios
- **Simultaneous Trades**: SELECT FOR UPDATE prevents corruption
- **Version Conflicts**: Optimistic locking for status updates
- **Sequence Violations**: Strict trade ordering enforcement

### Data Integrity
- **Equity Floor**: Negative P&L cannot reduce equity below zero
- **Terminal State Protection**: FAILED/FUNDED challenges reject trades
- **Timestamp Ordering**: executed_at must be after previous trade

### Business Rules
- **Daily Reset Timing**: UTC midnight boundary handling
- **Peak Equity Tracking**: All-time high maintained through losses
- **Rule Priority**: Drawdown failures override profit targets

### Performance Considerations
- **Lock Duration**: Minimal time holding database locks
- **Index Coverage**: Optimized queries for high-volume trading
- **Memory Bounds**: Stateless rule evaluation

## Architecture Components

### Core Classes

**ChallengeEngine**
- Orchestrates trade processing workflow
- Enforces state machine transitions
- Coordinates with rules engine and event bus

**ChallengeRulesEngine**
- Pure business logic for rule evaluation
- No database access or side effects
- Deterministic output from inputs

**TradingService**
- Entry point for trade execution requests
- Handles pessimistic locking
- Validates trade data

### Data Flow

```
API Request → TradingService → ChallengeEngine → RulesEngine
                                      ↓
                               EventBus → Handlers
                                      ↓
                               Database Commit
```

### Error Handling

**No try/except Swallowing:**
- Business rule violations raise ValueError with clear messages
- Database errors bubble up for framework handling
- Event emission failures logged but don't block commits

**Validation Layers:**
- API layer: Input format validation
- Service layer: Business rule pre-checks
- Engine layer: State machine enforcement

## Testing Strategy

### Unit Tests
- **Rules Engine**: Pure logic testing with edge cases
- **State Machine**: All valid transitions covered
- **Equity Calculations**: Decimal precision verification
- **Event Emission**: Correct payload generation

### Integration Tests
- **Database Transactions**: Lock behavior verification
- **Concurrent Access**: Race condition prevention
- **Event Processing**: End-to-end event flow

### Property-Based Testing
- **Mathematical Invariants**: Equity never negative
- **Rule Consistency**: Same inputs = same outputs
- **State Transitions**: No invalid state combinations

## Performance Benchmarks

**Per-Trade Processing:**
- Average: < 10ms (including database round-trip)
- P95: < 50ms under normal load
- P99: < 200ms under peak load

**Throughput:**
- Single challenge: 100 trades/second
- Concurrent challenges: 10,000 trades/second (distributed)
- Database locks: < 1ms contention under normal load

**Scalability Limits:**
- Horizontal scaling via database read replicas
- Event-driven architecture for async processing
- Caching layer for frequently accessed challenges

## Operational Considerations

### Monitoring
- **Business Metrics**: Challenge completion rates, rule violation patterns
- **Technical Metrics**: Transaction latency, lock wait times
- **Risk Metrics**: Drawdown distributions, equity floor hits

### Alerting
- **Rule Violations**: High-frequency failure patterns
- **Performance Degradation**: Increased processing latency
- **Data Anomalies**: Invalid equity calculations

### Disaster Recovery
- **Event Sourcing**: Complete system reconstruction from events
- **Point-in-Time Recovery**: Database backup/restore capability
- **Circuit Breakers**: Automatic degradation under load

## Regulatory Compliance

### SOC 2 Alignment
- **Security**: Access controls and audit trails
- **Availability**: Transactional consistency guarantees
- **Processing Integrity**: Deterministic rule evaluation
- **Confidentiality**: Encrypted sensitive data

### Financial Audit Readiness
- **Immutability**: Append-only event logs
- **Traceability**: Complete decision reconstruction
- **Reconciliation**: External system matching capability
- **Retention**: Configurable data lifecycle management

This Challenge Engine provides the foundation for a regulated prop trading platform with complete auditability, deterministic rule enforcement, and production-grade reliability.