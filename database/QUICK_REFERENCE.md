# TradeSense AI Database Schema - Quick Reference

## Table Summary

| Table | Purpose | Immutable | Key Constraints |
|-------|---------|-----------|-----------------|
| **users** | User accounts with RBAC | No | Soft delete only, unique email |
| **challenges** | Challenge accounts with equity tracking | No | State machine, optimistic locking |
| **trades** | Trade execution ledger | **YES** | Sequence numbers, no updates/deletes |
| **challenge_events** | Event-sourced audit log | **YES** | Sequence numbers, no updates/deletes |
| **payments** | Payment processing | No | Idempotent operations |
| **risk_alerts** | Risk monitoring alerts | No | Lifecycle tracking |

## Primary Keys and Foreign Keys

```
users (id)
  ↓
challenges (id, user_id → users.id)
  ↓
trades (id, challenge_id → challenges.id)
challenge_events (id, challenge_id → challenges.id)
risk_alerts (id, challenge_id → challenges.id, user_id → users.id)

payments (id, user_id → users.id, challenge_id → challenges.id)
```

## Common Queries

### User Management

```sql
-- Create user
INSERT INTO users (email, password_hash, role, status)
VALUES (?, ?, 'USER', 'ACTIVE');

-- Find user by email
SELECT * FROM users WHERE email = ? AND deleted_at IS NULL;

-- Soft delete user
UPDATE users
SET deleted_at = CURRENT_TIMESTAMP, deleted_reason = ?
WHERE id = ?;
```

### Challenge Management

```sql
-- Create challenge
INSERT INTO challenges (
    user_id, challenge_type, initial_balance,
    max_daily_drawdown_percent, max_total_drawdown_percent,
    profit_target_percent, current_equity, max_equity_ever,
    daily_start_equity, daily_max_equity, daily_min_equity
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- Get active challenges for user
SELECT * FROM challenges
WHERE user_id = ? AND status = 'ACTIVE'
ORDER BY created_at DESC;

-- Update challenge equity (with optimistic locking)
UPDATE challenges
SET current_equity = ?,
    max_equity_ever = GREATEST(max_equity_ever, ?),
    version = version + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE id = ? AND version = ?;

-- Start challenge
UPDATE challenges
SET status = 'ACTIVE',
    started_at = CURRENT_TIMESTAMP,
    version = version + 1
WHERE id = ? AND status = 'PENDING';

-- Fail challenge
UPDATE challenges
SET status = 'FAILED',
    ended_at = CURRENT_TIMESTAMP,
    failure_reason = ?,
    version = version + 1
WHERE id = ? AND status = 'ACTIVE';

-- Fund challenge
UPDATE challenges
SET status = 'FUNDED',
    ended_at = CURRENT_TIMESTAMP,
    funded_at = CURRENT_TIMESTAMP,
    version = version + 1
WHERE id = ? AND status = 'ACTIVE';
```

### Trade Management

```sql
-- Insert trade (immutable - no updates allowed)
INSERT INTO trades (
    challenge_id, trade_id, symbol, side,
    quantity, price, realized_pnl, commission,
    executed_at, sequence_number
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- Get trades for challenge
SELECT * FROM trades
WHERE challenge_id = ?
ORDER BY sequence_number ASC;

-- Get recent trades
SELECT * FROM trades
WHERE challenge_id = ?
AND executed_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY executed_at DESC;

-- Calculate total P&L
SELECT SUM(realized_pnl) as total_pnl
FROM trades
WHERE challenge_id = ?;
```

### Event Sourcing

```sql
-- Insert event (immutable - no updates allowed)
INSERT INTO challenge_events (
    challenge_id, event_type, event_version,
    sequence_number, event_data, description,
    occurred_at
) VALUES (?, ?, 'v1', ?, ?::jsonb, ?, ?);

-- Replay events for challenge
SELECT event_type, event_data, occurred_at, sequence_number
FROM challenge_events
WHERE challenge_id = ?
ORDER BY sequence_number ASC;

-- Get events by type
SELECT * FROM challenge_events
WHERE challenge_id = ?
AND event_type = 'TRADE_EXECUTED'
ORDER BY occurred_at DESC;
```

### Payment Processing

```sql
-- Create payment
INSERT INTO payments (
    user_id, provider, amount, currency, status
) VALUES (?, ?, ?, ?, 'PENDING');

-- Update payment status (idempotent)
UPDATE payments
SET status = ?,
    processed_at = CURRENT_TIMESTAMP,
    provider_payment_id = ?,
    webhook_data = ?::jsonb
WHERE id = ?;

-- Find payment by provider ID
SELECT * FROM payments
WHERE provider = ?
AND provider_payment_id = ?;

-- Get user payment history
SELECT * FROM payments
WHERE user_id = ?
ORDER BY created_at DESC;
```

### Risk Alerts

```sql
-- Create risk alert
INSERT INTO risk_alerts (
    challenge_id, user_id, alert_type,
    severity, title, message, alert_data
) VALUES (?, ?, ?, ?, ?, ?, ?::jsonb);

-- Get active alerts for challenge
SELECT * FROM risk_alerts
WHERE challenge_id = ?
AND status = 'ACTIVE'
ORDER BY severity DESC, created_at DESC;

-- Acknowledge alert
UPDATE risk_alerts
SET status = 'ACKNOWLEDGED',
    acknowledged_at = CURRENT_TIMESTAMP,
    acknowledged_by = ?
WHERE id = ?;

-- Resolve alert
UPDATE risk_alerts
SET status = 'RESOLVED',
    resolved_at = CURRENT_TIMESTAMP,
    resolved_by = ?
WHERE id = ?;
```

## Analytics Queries

### Challenge Performance

```sql
-- Get challenge performance metrics
SELECT * FROM challenge_performance_analytics
WHERE id = ?;

-- Top performing challenges
SELECT * FROM challenge_performance_analytics
WHERE status = 'FUNDED'
ORDER BY profit_percentage DESC
LIMIT 10;

-- User statistics
SELECT
    user_id,
    COUNT(*) as total_challenges,
    SUM(CASE WHEN status = 'FUNDED' THEN 1 ELSE 0 END) as funded_count,
    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
    AVG(CASE WHEN status = 'FUNDED' THEN total_pnl ELSE NULL END) as avg_funded_pnl
FROM challenges
GROUP BY user_id;
```

### Trading Statistics

```sql
-- Win rate calculation
SELECT
    challenge_id,
    COUNT(*) as total_trades,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    ROUND(
        CAST(SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) /
        CAST(COUNT(*) AS FLOAT) * 100, 2
    ) as win_rate_percent
FROM trades
GROUP BY challenge_id;

-- Daily trading volume
SELECT
    DATE(executed_at) as trade_date,
    COUNT(*) as trade_count,
    SUM(ABS(realized_pnl)) as total_volume
FROM trades
WHERE challenge_id = ?
GROUP BY DATE(executed_at)
ORDER BY trade_date DESC;

-- Most traded symbols
SELECT
    symbol,
    COUNT(*) as trade_count,
    SUM(realized_pnl) as total_pnl
FROM trades
WHERE challenge_id = ?
GROUP BY symbol
ORDER BY trade_count DESC;
```

## Status Field Values

### User Status
- `PENDING_VERIFICATION` - Account created, awaiting verification
- `ACTIVE` - Normal active account
- `SUSPENDED` - Temporarily suspended
- `CLOSED` - Permanently closed

### Challenge Status
- `PENDING` - Created but not started
- `ACTIVE` - Currently trading
- `FAILED` - Failed due to rule violation
- `FUNDED` - Successfully completed

### Trade Side
- `BUY` - Long position
- `SELL` - Short position

### Payment Status
- `PENDING` - Payment initiated
- `PROCESSING` - Being processed by provider
- `SUCCESS` - Payment successful
- `FAILED` - Payment failed
- `CANCELLED` - Payment cancelled
- `REFUNDED` - Payment refunded

### Alert Severity
- `LOW` - Informational
- `MEDIUM` - Warning
- `HIGH` - Requires attention
- `CRITICAL` - Immediate action required

### Alert Status
- `ACTIVE` - New alert
- `ACKNOWLEDGED` - Alert seen by user
- `RESOLVED` - Issue resolved
- `FALSE_POSITIVE` - Not a real issue

## Indexes Reference

### Users
- `idx_users_email_active` - Unique email for active users
- `idx_users_role_status` - Role and status queries
- `idx_users_created_at` - Time-based queries

### Challenges
- `idx_challenges_user_id` - User's challenges
- `idx_challenges_status` - Filter by status
- `idx_challenges_user_status` - User + status composite
- `idx_challenges_id_version` - Optimistic locking

### Trades
- `idx_trades_challenge_id` - Challenge's trades
- `idx_trades_challenge_executed_at` - Time-ordered trades
- `idx_trades_challenge_sequence` - Sequence-ordered trades
- `idx_trades_challenge_sequence_lock` - Concurrency control

### Challenge Events
- `idx_challenge_events_challenge_id` - Challenge's events
- `idx_challenge_events_challenge_sequence` - Sequence-ordered events
- `idx_challenge_events_type` - Filter by event type
- `idx_events_challenge_sequence_lock` - Concurrency control

### Payments
- `idx_payments_user_id` - User's payments
- `idx_payments_provider_payment_id` - Idempotency lookup
- `idx_payments_status` - Filter by status
- `idx_payments_provider_lock` - Prevent duplicates

### Risk Alerts
- `idx_risk_alerts_challenge_id` - Challenge's alerts
- `idx_risk_alerts_type_severity` - Filter by type and severity
- `idx_risk_alerts_active` - Active alerts only

## Constraints Reference

### Check Constraints

```sql
-- Users
CHECK (role IN ('USER', 'ADMIN', 'SUPERADMIN'))
CHECK (status IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED'))
CHECK (updated_at >= created_at)

-- Challenges
CHECK (initial_balance > 0)
CHECK (current_equity >= 0)
CHECK (current_equity <= max_equity_ever)
CHECK (daily_min_equity <= daily_max_equity)
CHECK (status IN ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED'))

-- Trades
CHECK (quantity > 0)
CHECK (price > 0)
CHECK (side IN ('BUY', 'SELL'))
CHECK (created_at >= executed_at)

-- Payments
CHECK (amount > 0)
CHECK (currency IN ('USD', 'EUR', 'GBP'))
CHECK (provider IN ('STRIPE', 'PAYPAL', 'BANK_TRANSFER', 'MOCK'))
CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED'))

-- Risk Alerts
CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))
CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE'))
```

### Unique Constraints

```sql
-- Users
UNIQUE (email) WHERE deleted_at IS NULL

-- Challenges
UNIQUE (id, version) -- Optimistic locking

-- Trades
UNIQUE (challenge_id, trade_id) -- Idempotency
UNIQUE (challenge_id, sequence_number) -- Ordering

-- Challenge Events
UNIQUE (challenge_id, sequence_number) -- Ordering

-- Payments
UNIQUE (provider, provider_payment_id) -- Idempotency
```

## Immutability Rules

### Tables That CANNOT Be Modified

**Trades Table**:
```sql
-- ❌ FORBIDDEN - Will raise error
UPDATE trades SET realized_pnl = 999 WHERE id = ?;
DELETE FROM trades WHERE id = ?;

-- ✅ ALLOWED - Insert only
INSERT INTO trades (...) VALUES (...);
```

**Challenge Events Table**:
```sql
-- ❌ FORBIDDEN - Will raise error
UPDATE challenge_events SET event_data = '{}' WHERE id = ?;
DELETE FROM challenge_events WHERE id = ?;

-- ✅ ALLOWED - Insert only
INSERT INTO challenge_events (...) VALUES (...);
```

## Optimistic Locking Pattern

```sql
-- 1. Read current version
SELECT id, version, current_equity
FROM challenges
WHERE id = ?;

-- 2. Perform business logic in application

-- 3. Update with version check
UPDATE challenges
SET current_equity = ?,
    version = version + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE id = ? AND version = ?;

-- 4. Check affected rows
-- If 0 rows affected, concurrent update occurred - retry
```

## Transaction Examples

### Process Trade with Challenge Update

```sql
BEGIN;

-- 1. Get next sequence number
SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
FROM trades
WHERE challenge_id = ?
FOR UPDATE;

-- 2. Insert trade
INSERT INTO trades (
    challenge_id, trade_id, symbol, side,
    quantity, price, realized_pnl, commission,
    executed_at, sequence_number
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);

-- 3. Update challenge equity
UPDATE challenges
SET current_equity = current_equity + ?,
    max_equity_ever = GREATEST(max_equity_ever, current_equity + ?),
    total_trades = total_trades + 1,
    total_pnl = total_pnl + ?,
    last_trade_at = CURRENT_TIMESTAMP,
    version = version + 1
WHERE id = ? AND version = ?;

-- 4. Insert event
INSERT INTO challenge_events (
    challenge_id, event_type, sequence_number,
    event_data, description, occurred_at
) VALUES (?, 'TRADE_EXECUTED', ?, ?::jsonb, ?, ?);

COMMIT;
```

## Error Handling

### Common Errors

**Immutability Violation**:
```
ERROR: Trades are immutable - cannot update trade
ERROR: Events are immutable - cannot delete event
```
**Solution**: Don't attempt to modify immutable tables

**Optimistic Lock Failure**:
```
UPDATE returned 0 rows (version mismatch)
```
**Solution**: Retry with exponential backoff

**Foreign Key Violation**:
```
ERROR: insert or update on table violates foreign key constraint
```
**Solution**: Ensure referenced record exists

**Unique Constraint Violation**:
```
ERROR: duplicate key value violates unique constraint
```
**Solution**: Check for existing record, handle idempotency

## Best Practices

1. **Always use transactions** for multi-table operations
2. **Use optimistic locking** for concurrent updates
3. **Never modify immutable tables** (trades, events)
4. **Use soft deletes** for user data
5. **Include version in WHERE clause** when updating challenges
6. **Use sequence numbers** for ordering
7. **Store timestamps in UTC** always
8. **Use JSONB for flexible data** (metadata, event payloads)
9. **Index foreign keys** for join performance
10. **Monitor query performance** regularly

---

**Quick Reference Version**: 1.0  
**Last Updated**: January 19, 2024
