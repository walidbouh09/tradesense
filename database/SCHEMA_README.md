# TradeSense AI Database Schema Documentation

## Overview

This document describes the complete database schema for the TradeSense AI prop trading platform. The schema is designed with financial audit compliance, event sourcing, and immutability as core principles.

## Schema Files

- **`tradesense_schema.sql`** - PostgreSQL 14+ compatible schema
- **`tradesense_schema_sqlite.sql`** - SQLite 3.35+ compatible schema

Both schemas implement the same logical design with database-specific optimizations.

## Core Tables

### 1. Users Table

**Purpose**: User accounts with role-based access control

**Key Features**:
- UUID primary keys for global uniqueness
- Password hashes only (never plaintext)
- Soft delete for compliance (never hard delete financial data)
- Role-based access: USER, ADMIN, SUPERADMIN
- Account status tracking: PENDING_VERIFICATION, ACTIVE, SUSPENDED, CLOSED
- Optimistic locking with version column

**Security Considerations**:
- No sensitive PII beyond email
- No payment card data (handled by payment processors)
- Metadata field for future KYC data (encrypted at application layer)

### 2. Challenges Table

**Purpose**: Prop firm challenge accounts with real-time equity tracking

**Key Features**:
- Immutable configuration (initial balance, drawdown limits, profit targets)
- Real-time equity tracking (current, max ever, daily metrics)
- Daily reset tracking (resets at UTC midnight)
- State machine enforcement (PENDING → ACTIVE → FAILED/FUNDED)
- Complete audit trail of state changes

**Critical Fields**:
- `current_equity`: Real-time account value
- `max_equity_ever`: Peak value for total drawdown calculation
- `daily_start_equity`: Opening balance each day for daily drawdown
- `initial_balance`: Starting capital (immutable)

**State Transitions**:
```
PENDING → ACTIVE (challenge started)
ACTIVE → FUNDED (profit target reached)
ACTIVE → FAILED (rule violation or expiry)
```

### 3. Trades Table

**Purpose**: Immutable trade ledger - append-only for financial audit compliance

**Key Features**:
- **IMMUTABLE**: Triggers prevent UPDATE/DELETE operations
- Sequence numbers for strict ordering per challenge
- Business time (executed_at) vs system time (created_at)
- Realized P&L stored explicitly (not recalculated)
- Complete trade details (symbol, side, quantity, price, commission)

**Why P&L is Stored**:
1. Audit compliance - original calculation preserved
2. Precision - avoids floating-point errors
3. Performance - no reprocessing needed
4. Dispute resolution - immutable evidence
5. Reconciliation - matches external platforms

### 4. Challenge Events Table

**Purpose**: Event-sourced audit log - append-only, replayable for dispute resolution

**Key Features**:
- **IMMUTABLE**: Triggers prevent modifications
- Complete business event history
- Sequence numbers for strict ordering
- Human-readable descriptions for auditors
- JSONB event payloads for structured data
- Event correlation and causation tracking

**Event Types**:
- TRADE_EXECUTED
- CHALLENGE_STATUS_CHANGED
- CHALLENGE_FAILED
- CHALLENGE_FUNDED
- RISK_VIOLATION_DETECTED
- DAILY_PNL_CALCULATED

**Reconstruction Capability**:
```sql
-- Replay all events to reconstruct challenge state
SELECT event_type, event_data, occurred_at, sequence_number
FROM challenge_events
WHERE challenge_id = ?
ORDER BY sequence_number ASC;
```

### 5. Payments Table

**Purpose**: Payment processing for challenge purchases

**Key Features**:
- Multi-provider support (Stripe, PayPal, Bank Transfer, Mock)
- Idempotent operations (provider_payment_id uniqueness)
- Complete payment lifecycle tracking
- Webhook data preservation for audit
- Refund tracking
- Decoupled from challenge lifecycle

**Payment States**:
- PENDING → PROCESSING → SUCCESS/FAILED
- SUCCESS → REFUNDED (if refund issued)
- CANCELLED (user cancelled before processing)

### 6. Risk Alerts Table

**Purpose**: Risk monitoring and alerting system

**Key Features**:
- Separate from core decision logic (monitoring only)
- Alert lifecycle (ACTIVE → ACKNOWLEDGED → RESOLVED)
- Severity levels (LOW, MEDIUM, HIGH, CRITICAL)
- Correlation IDs for grouping related alerts
- Threshold breach details for analysis

**Alert Types**:
- HIGH_DRAWDOWN
- TOTAL_DRAWDOWN_EXCEEDED
- PROFIT_TARGET_REACHED
- INACTIVE_TRADING
- UNUSUAL_ACTIVITY
- RISK_SCORE_SPIKE

## Database Design Principles

### 1. Immutability

**Tables with Immutability Enforcement**:
- `trades` - Financial transaction ledger
- `challenge_events` - Event sourcing log

**Implementation**:
- PostgreSQL: Database triggers prevent UPDATE/DELETE
- SQLite: BEFORE triggers with RAISE(ABORT)
- Application layer: Additional validation

### 2. Event Sourcing

**Complete Audit Trail**:
- Every state change logged as event
- Events contain complete context (metrics, thresholds, timestamps)
- Events are immutable and sequentially ordered
- System can be reconstructed from event log

### 3. Financial Audit Compliance

**Regulatory Requirements Met**:
- ✅ Complete transaction history (trades table)
- ✅ Immutable financial records (triggers)
- ✅ Event-sourced audit log (challenge_events)
- ✅ Soft delete only (no hard deletes)
- ✅ UTC timestamps (no timezone ambiguity)
- ✅ Sequence numbers (prevent reordering)
- ✅ Human-readable explanations (for auditors)

### 4. Optimistic Locking

**Concurrency Control**:
- Version columns on users and challenges
- Prevents lost updates in concurrent scenarios
- Application layer handles retry logic

**Example**:
```sql
-- Update with version check
UPDATE challenges
SET current_equity = ?, version = version + 1
WHERE id = ? AND version = ?;

-- If no rows affected, concurrent update occurred
```

### 5. Proper Indexing

**Index Strategy**:
- Primary keys: UUID for global uniqueness
- Foreign keys: All relationships indexed
- Query patterns: Composite indexes for common queries
- Partial indexes: Filter on status for active records
- Unique indexes: Prevent duplicates (idempotency)

## Views and Analytics

### Challenge Performance Analytics View

**Purpose**: Real-time performance metrics without impacting transactional tables

**Metrics Provided**:
- Profit percentage
- Drawdown percentage
- Daily drawdown used
- Trading hours
- Win rate
- Average trade size
- Total volume

**Usage**:
```sql
SELECT * FROM challenge_performance_analytics
WHERE user_id = ?
ORDER BY created_at DESC;
```

## Database Compatibility

### PostgreSQL Features Used

- UUID generation: `gen_random_uuid()`
- JSONB data type with GIN indexes
- Advanced constraints and check constraints
- Triggers with PL/pgSQL functions
- Materialized views (optional)
- TIMESTAMPTZ for timezone-aware timestamps

### SQLite Adaptations

- UUID as TEXT with `lower(hex(randomblob(16)))`
- JSON as TEXT (no native JSONB)
- Triggers with RAISE(ABORT) for immutability
- TEXT for timestamps (ISO 8601 format)
- REAL for numeric values (limited precision)

## Installation

### PostgreSQL

```bash
# Create database
createdb tradesense

# Run schema
psql tradesense < database/tradesense_schema.sql
```

### SQLite

```bash
# Create database and run schema
sqlite3 tradesense.db < database/tradesense_schema_sqlite.sql
```

## Migration Strategy

### Core Principles

1. **ZERO DATA LOSS**: Never drop columns or tables with financial data
2. **BACKWARD COMPATIBILITY**: Old code must work with new schema
3. **AUDIT TRAIL PRESERVATION**: Event history remains intact
4. **BUSINESS LOGIC CONSISTENCY**: Rule evaluation logic unaffected
5. **PERFORMANCE MAINTENANCE**: Indexes optimized for new query patterns

### Forbidden Changes

❌ **NEVER DO THESE**:
- Drop financial tables (trades, payments, challenge_events)
- Drop columns with financial data
- Modify existing trades or events
- Change historical timestamps
- Remove uniqueness constraints on financial IDs
- Modify existing enum values

✅ **ALLOWED CHANGES**:
- Add new columns (with DEFAULT values)
- Add new indexes (for performance)
- Add new tables (for new features)
- Increase data type precision (VARCHAR length, NUMERIC scale)
- Add new enum values (append only)

## Security Considerations

### Data Protection

- **Encryption at Rest**: Database-level encryption recommended
- **Encryption in Transit**: TLS 1.3 for all connections
- **Password Storage**: Bcrypt/scrypt hashes only
- **PCI DSS Compliance**: No card data stored
- **GDPR Compliance**: Data minimization, soft deletes

### Access Control

- **Role-Based Access**: USER, ADMIN, SUPERADMIN
- **Principle of Least Privilege**: Grant minimum required permissions
- **Audit Logging**: All data access logged
- **Connection Pooling**: Limit concurrent connections

## Performance Optimization

### Query Optimization

1. **Use Indexes**: All foreign keys and common query patterns indexed
2. **Partial Indexes**: Filter on status for active records only
3. **Composite Indexes**: Multi-column indexes for complex queries
4. **Avoid SELECT ***: Select only needed columns
5. **Use EXPLAIN**: Analyze query plans regularly

### Scaling Strategies

1. **Read Replicas**: Separate read/write database instances
2. **Connection Pooling**: PgBouncer for PostgreSQL
3. **Partitioning**: Partition large tables by date (future)
4. **Caching**: Redis for frequently accessed data
5. **Materialized Views**: Pre-compute expensive aggregations

## Monitoring and Maintenance

### Key Metrics to Monitor

- Query performance (slow query log)
- Connection pool utilization
- Table sizes and growth rates
- Index usage statistics
- Lock contention and deadlocks
- Replication lag (if using replicas)

### Regular Maintenance Tasks

- **Daily**: Monitor slow queries and errors
- **Weekly**: Analyze table statistics, vacuum (PostgreSQL)
- **Monthly**: Review index usage, optimize queries
- **Quarterly**: Audit data retention policies
- **Yearly**: Review and update schema documentation

## Testing

### Schema Validation

```sql
-- Verify all tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('users', 'challenges', 'trades', 'challenge_events', 'payments', 'risk_alerts');
```

### Data Integrity Tests

```sql
-- Verify no orphaned records
SELECT COUNT(*) FROM challenges WHERE user_id NOT IN (SELECT id FROM users);
SELECT COUNT(*) FROM trades WHERE challenge_id NOT IN (SELECT id FROM challenges);

-- Verify immutability (should fail)
UPDATE trades SET realized_pnl = 999 WHERE id = 'test-id'; -- Should raise error
DELETE FROM challenge_events WHERE id = 'test-id'; -- Should raise error
```

## Troubleshooting

### Common Issues

**Issue**: Concurrent update conflicts
**Solution**: Implement exponential backoff retry logic in application

**Issue**: Slow queries on large tables
**Solution**: Add appropriate indexes, use EXPLAIN to analyze

**Issue**: Disk space growth
**Solution**: Implement data archival strategy, partition old data

**Issue**: Connection pool exhaustion
**Solution**: Increase pool size, optimize connection usage

## Support and Documentation

For questions or issues:
1. Review this documentation
2. Check existing schema comments
3. Consult design documents (TRADING_DOMAIN_DESIGN.md, etc.)
4. Contact database engineering team

## Version History

- **v1.0** (2024-01-19): Initial schema design
  - Core tables: users, challenges, trades, challenge_events, payments, risk_alerts
  - PostgreSQL and SQLite compatibility
  - Immutability enforcement
  - Event sourcing implementation
  - Financial audit compliance

---

**Last Updated**: January 19, 2024  
**Schema Version**: 1.0  
**Maintained By**: Database Engineering Team
