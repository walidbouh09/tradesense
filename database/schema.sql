-- TradeSense AI Challenge Engine Database Schema
-- PostgreSQL 14+ | UTC Timestamps | NUMERIC for Monetary Values
-- Regulated FinTech | Audit-Ready | Event-Driven | Append-Only Philosophy

-- ============================================================================
-- TASK 1: USERS TABLE
-- ============================================================================

-- Users table for a regulated FinTech platform
-- Security considerations: Only hashes stored, no sensitive data retention
CREATE TABLE users (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,

    -- Secure password storage (bcrypt/scrypt hash only)
    password_hash VARCHAR(255) NOT NULL,

    -- Role-based access control for FinTech operations
    role user_role_enum NOT NULL DEFAULT 'USER',

    -- Account lifecycle management
    status account_status_enum NOT NULL DEFAULT 'ACTIVE',

    -- Audit timestamps (UTC only)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,

    -- Soft delete for compliance (never hard delete financial data)
    deleted_at TIMESTAMPTZ,
    deleted_reason VARCHAR(500),

    -- Metadata for future expansion
    metadata JSONB DEFAULT '{}',

    -- Optimistic locking
    version BIGINT NOT NULL DEFAULT 1
);

-- Enums for regulated data integrity
CREATE TYPE user_role_enum AS ENUM ('USER', 'ADMIN', 'SUPERADMIN');
CREATE TYPE account_status_enum AS ENUM ('ACTIVE', 'SUSPENDED', 'CLOSED', 'PENDING_VERIFICATION');

-- Indexes for regulated FinTech access patterns
CREATE UNIQUE INDEX idx_users_email_active ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role_status ON users (role, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at ON users (created_at);
CREATE INDEX idx_users_status ON users (status) WHERE deleted_at IS NULL;

-- Constraints for data integrity
ALTER TABLE users ADD CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');
ALTER TABLE users ADD CONSTRAINT chk_password_hash_not_empty CHECK (length(password_hash) > 0);
ALTER TABLE users ADD CONSTRAINT chk_updated_at_after_created_at CHECK (updated_at >= created_at);
ALTER TABLE users ADD CONSTRAINT chk_deleted_at_future CHECK (deleted_at IS NULL OR deleted_at > created_at);

-- Comments for audit documentation
COMMENT ON TABLE users IS 'User accounts for regulated FinTech platform - audit-ready with lifecycle tracking';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt/scrypt hash only - never stores plaintext passwords';
COMMENT ON COLUMN users.metadata IS 'JSON field for future KYC, preferences - encrypted at application layer';
COMMENT ON COLUMN users.deleted_at IS 'Soft delete timestamp - maintains audit trail for regulators';
COMMENT ON COLUMN users.version IS 'Optimistic locking version for concurrent access control';

/*
TASK 1 EXPLANATION: USERS TABLE DESIGN

Column Explanations:
- id: UUID for global uniqueness and GDPR compliance (no sequential IDs)
- email: Unique identifier for authentication, validated format
- password_hash: Only secure hash stored - never plaintext (bcrypt/scrypt recommended)
- role: RBAC for FinTech operations (USER for traders, ADMIN for ops, SUPERADMIN for compliance)
- status: Account lifecycle (ACTIVE, SUSPENDED for violations, CLOSED for permanent, PENDING_VERIFICATION for KYC)
- created_at/updated_at: Audit timestamps in UTC
- last_login_at: Security monitoring and account activity tracking
- deleted_at/deleted_reason: Soft delete for compliance - never hard delete financial data
- metadata: JSONB for future expansion (KYC data, preferences) - encrypted at application layer
- version: Optimistic locking for concurrent updates

Security Considerations (What is INTENTIONALLY NOT stored):
- No plaintext passwords (only hashes)
- No sensitive PII beyond email (no names, addresses, phone numbers)
- No payment card data (handled by payment processors)
- No social security/tax IDs (stored encrypted elsewhere if required)
- No biometric data
- No unnecessary personal information

This design supports:
- SOC 2 compliance readiness
- GDPR compliance (data minimization)
- Future KYC/AML integration
- Audit trail maintenance
- Secure authentication flows
*/

-- ============================================================================
-- TASK 2: CHALLENGES TABLE
-- ============================================================================

-- Challenge accounts representing prop firm simulated trading accounts
-- Core financial state tracking for drawdown rules and decision logic
CREATE TABLE challenges (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Challenge configuration (immutable after creation)
    challenge_type VARCHAR(50) NOT NULL, -- e.g., 'PHASE_1', 'PHASE_2'
    initial_balance NUMERIC(15,2) NOT NULL CHECK (initial_balance > 0),
    max_daily_drawdown_percent NUMERIC(5,2) NOT NULL CHECK (max_daily_drawdown_percent BETWEEN 0 AND 100),
    max_total_drawdown_percent NUMERIC(5,2) NOT NULL CHECK (max_total_drawdown_percent BETWEEN 0 AND 100),
    profit_target_percent NUMERIC(5,2) NOT NULL CHECK (profit_target_percent BETWEEN 0 AND 100),

    -- Dynamic equity tracking (critical for rule evaluation)
    current_equity NUMERIC(15,2) NOT NULL CHECK (current_equity >= 0), -- Never negative (floor at zero)
    max_equity_ever NUMERIC(15,2) NOT NULL CHECK (max_equity_ever >= initial_balance), -- All-time high water mark

    -- Daily tracking (resets at UTC midnight)
    daily_start_equity NUMERIC(15,2) NOT NULL CHECK (daily_start_equity >= 0),
    daily_max_equity NUMERIC(15,2) NOT NULL CHECK (daily_max_equity >= 0),
    daily_min_equity NUMERIC(15,2) NOT NULL CHECK (daily_min_equity >= 0),
    current_date DATE NOT NULL,

    -- Performance tracking
    total_trades INTEGER NOT NULL DEFAULT 0 CHECK (total_trades >= 0),
    total_pnl NUMERIC(15,2) NOT NULL DEFAULT 0,

    -- Lifecycle status (state machine enforcement)
    status challenge_status_enum NOT NULL DEFAULT 'PENDING',

    -- Time tracking for audit and reporting
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,  -- When first trade occurs (PENDING -> ACTIVE)
    ended_at TIMESTAMPTZ,    -- When FAILED or FUNDED (terminal states)
    last_trade_at TIMESTAMPTZ,

    -- Rule violation tracking (for audit and reporting)
    failure_reason VARCHAR(100), -- e.g., 'MAX_DAILY_DRAWDOWN', 'MAX_TOTAL_DRAWDOWN'
    funded_at TIMESTAMPTZ,   -- Specific timestamp when profit target reached

    -- Optimistic locking for concurrent trade processing
    version BIGINT NOT NULL DEFAULT 1
);

-- Enum for challenge lifecycle states
CREATE TYPE challenge_status_enum AS ENUM ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED');

-- Referential integrity and business constraints
ALTER TABLE challenges ADD CONSTRAINT fk_challenges_user_id
    FOREIGN KEY (user_id) REFERENCES users(id);

ALTER TABLE challenges ADD CONSTRAINT chk_equity_consistency
    CHECK (current_equity <= max_equity_ever);

ALTER TABLE challenges ADD CONSTRAINT chk_daily_equity_bounds
    CHECK (daily_min_equity <= daily_max_equity AND daily_start_equity >= 0);

ALTER TABLE challenges ADD CONSTRAINT chk_terminal_states_complete
    CHECK (
        (status IN ('FAILED', 'FUNDED') AND ended_at IS NOT NULL) OR
        (status NOT IN ('FAILED', 'FUNDED') AND ended_at IS NULL)
    );

ALTER TABLE challenges ADD CONSTRAINT chk_funded_at_only_funded
    CHECK (
        (status = 'FUNDED' AND funded_at IS NOT NULL) OR
        (status != 'FUNDED' AND funded_at IS NULL)
    );

-- Indexes for high-volume financial operations
CREATE INDEX idx_challenges_user_id ON challenges (user_id);
CREATE INDEX idx_challenges_status ON challenges (status);
CREATE INDEX idx_challenges_user_status ON challenges (user_id, status);
CREATE INDEX idx_challenges_created_at ON challenges (created_at);
CREATE INDEX idx_challenges_current_date ON challenges (current_date);
CREATE INDEX idx_challenges_last_trade_at ON challenges (last_trade_at) WHERE last_trade_at IS NOT NULL;

-- Partial indexes for active challenges (most queried)
CREATE INDEX idx_challenges_active_equity ON challenges (current_equity) WHERE status = 'ACTIVE';
CREATE INDEX idx_challenges_active_daily ON challenges (daily_start_equity, daily_max_equity) WHERE status = 'ACTIVE';

-- Comments for audit documentation
COMMENT ON TABLE challenges IS 'Prop firm challenge accounts - core financial state for rule evaluation';
COMMENT ON COLUMN challenges.initial_balance IS 'Starting capital amount - immutable configuration';
COMMENT ON COLUMN challenges.current_equity IS 'Current account equity - never goes below zero';
COMMENT ON COLUMN challenges.max_equity_ever IS 'All-time high water mark for total drawdown calculation';
COMMENT ON COLUMN challenges.daily_start_equity IS 'Equity at start of current trading day (resets daily)';
COMMENT ON COLUMN challenges.daily_max_equity IS 'Maximum equity reached today';
COMMENT ON COLUMN challenges.daily_min_equity IS 'Minimum equity reached today';
COMMENT ON COLUMN challenges.current_date IS 'Current trading date for daily reset logic';
COMMENT ON COLUMN challenges.failure_reason IS 'Specific rule that caused failure (audit trail)';
COMMENT ON COLUMN challenges.funded_at IS 'Exact timestamp when profit target was reached';

/*
TASK 2 EXPLANATION: CHALLENGES TABLE DESIGN

Referential Integrity:
- Foreign key to users table ensures challenges belong to valid users
- No CASCADE DELETE - challenges are audit data, never deleted

Indexing Strategy:
- user_id: Find all challenges for a user (common query)
- status: Filter active challenges for processing
- Composite (user_id, status): User dashboard queries
- current_date: Daily reset operations
- last_trade_at: Recent activity monitoring
- Partial indexes on ACTIVE status: Optimize for live challenges

Rationale for Each Equity Field:
- current_equity: Real-time account value, used in all calculations
- max_equity_ever: Peak value for total drawdown = (max_equity - current) / max_equity
- daily_start_equity: Opening balance each day for daily drawdown = (daily_start - current) / daily_start
- daily_max/min_equity: Track daily ranges for reporting and analysis
- current_date: Determines when daily reset occurs (UTC midnight)

How This Table Supports Audit & Rule Evaluation:
- Complete equity history through event sourcing (challenge_events table)
- Rule decisions are deterministic: same equity values → same rule outcomes
- Audit reconstruction: replay events to verify rule application
- Financial compliance: immutable equity trail for regulator review
- Dispute resolution: exact equity state at any point in time
*/

-- ============================================================================
-- TASK 3: TRADES TABLE (IMMUTABLE LEDGER)
-- ============================================================================

-- Immutable trade ledger - each row is historical truth
-- NO UPDATE, NO DELETE - append-only for financial audit compliance
CREATE TABLE trades (
    -- Primary identity (UUID for global uniqueness)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Immutable business relationship
    challenge_id UUID NOT NULL REFERENCES challenges(id),

    -- Trade execution details (business time - when trade occurred)
    trade_id VARCHAR(100) NOT NULL, -- External trade identifier for idempotency
    symbol VARCHAR(20) NOT NULL,    -- Trading instrument (EURUSD, AAPL, etc.)
    side trade_side_enum NOT NULL, -- BUY or SELL
    quantity NUMERIC(15,8) NOT NULL CHECK (quantity > 0), -- Support fractional shares/crypto
    price NUMERIC(15,8) NOT NULL CHECK (price > 0),       -- Price per unit

    -- Financial impact (stored explicitly - not recalculated)
    realized_pnl NUMERIC(15,2) NOT NULL, -- Profit/Loss from this trade
    commission NUMERIC(15,2) NOT NULL DEFAULT 0, -- Trading fees

    -- Timing (critical for audit and sequence)
    executed_at TIMESTAMPTZ NOT NULL, -- Business time (when trade occurred)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- System time (when recorded)

    -- Sequence tracking within challenge
    sequence_number BIGINT NOT NULL, -- Monotonically increasing per challenge

    -- Metadata for future expansion
    metadata JSONB DEFAULT '{}'
);

-- Enum for trade direction
CREATE TYPE trade_side_enum AS ENUM ('BUY', 'SELL');

-- Referential integrity (no CASCADE - trades are audit data)
ALTER TABLE trades ADD CONSTRAINT fk_trades_challenge_id
    FOREIGN KEY (challenge_id) REFERENCES challenges(id);

-- Uniqueness constraints (prevent duplicate trades)
ALTER TABLE trades ADD CONSTRAINT uk_trades_challenge_trade_id
    UNIQUE (challenge_id, trade_id);

-- Sequence constraints (enforce ordering)
ALTER TABLE trades ADD CONSTRAINT uk_trades_challenge_sequence
    UNIQUE (challenge_id, sequence_number);

-- Business rules
ALTER TABLE trades ADD CONSTRAINT chk_executed_at_not_future
    CHECK (executed_at <= NOW() + INTERVAL '1 hour'); -- Allow some clock skew

ALTER TABLE trades ADD CONSTRAINT chk_created_at_after_executed_at
    CHECK (created_at >= executed_at);

-- IMMUTABILITY ENFORCEMENT (append-only philosophy)
-- No UPDATE trigger - trades cannot be modified once inserted
CREATE OR REPLACE FUNCTION prevent_trade_updates()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow INSERTs, but prevent UPDATEs and DELETEs
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Trades are immutable - cannot update trade %', OLD.id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Trades are immutable - cannot delete trade %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trades_immutable
    BEFORE UPDATE OR DELETE ON trades
    FOR EACH ROW EXECUTE FUNCTION prevent_trade_updates();

-- Indexes for high-volume queries (trades can be high-frequency)
CREATE INDEX idx_trades_challenge_id ON trades (challenge_id);
CREATE INDEX idx_trades_challenge_executed_at ON trades (challenge_id, executed_at);
CREATE INDEX idx_trades_challenge_sequence ON trades (challenge_id, sequence_number);
CREATE INDEX idx_trades_executed_at ON trades (executed_at);
CREATE INDEX idx_trades_symbol ON trades (symbol);
CREATE INDEX idx_trades_created_at ON trades (created_at);

-- Partial indexes for recent data (common query patterns)
CREATE INDEX idx_trades_recent ON trades (executed_at) WHERE executed_at > NOW() - INTERVAL '30 days';

-- Comments for audit documentation
COMMENT ON TABLE trades IS 'Immutable trade ledger - append-only for financial audit compliance';
COMMENT ON COLUMN trades.trade_id IS 'External trade identifier for idempotency and reconciliation';
COMMENT ON COLUMN trades.realized_pnl IS 'Profit/loss explicitly stored - not recalculated from price data';
COMMENT ON COLUMN trades.executed_at IS 'Business time (when trade occurred in market)';
COMMENT ON COLUMN trades.created_at IS 'System time (when trade was recorded in our system)';
COMMENT ON COLUMN trades.sequence_number IS 'Monotonic sequence per challenge for ordering';

/*
TASK 3 EXPLANATION: TRADES TABLE DESIGN

Constraints Enforcing Immutability:
- Trigger prevents UPDATE/DELETE operations
- No CASCADE DELETE on foreign keys
- UNIQUE constraints prevent duplicate inserts
- Sequence numbers enforce strict ordering

Indexes for High-Volume Queries:
- challenge_id: Find all trades for a challenge (common for reconstruction)
- (challenge_id, executed_at): Time-ordered trades for a challenge
- (challenge_id, sequence_number): Sequence-ordered trades
- executed_at: Global trade timeline queries
- symbol: Instrument-specific analytics

Why PnL is Stored (Not Recalculated):
1. Audit Compliance: Original calculation is preserved as historical truth
2. Precision: Avoids floating-point errors in recalculation
3. Performance: No need to reprocess price/quantity on every query
4. Dispute Resolution: Original PnL values are immutable evidence
5. Reconciliation: Matches external trading platform calculations exactly

This design ensures:
- Financial audit compliance (immutable transaction log)
- High-performance querying (proper indexing)
- Data integrity (constraints and triggers)
- Regulatory reporting readiness
*/

-- ============================================================================
-- TASK 4: CHALLENGE_EVENTS TABLE (EVENT SOURCING)
-- ============================================================================

-- Event-sourced audit log of all significant business events
-- Append-only, replayable, human-readable for audit and dispute resolution
CREATE TABLE challenge_events (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event sourcing relationship
    challenge_id UUID NOT NULL REFERENCES challenges(id),

    -- Event metadata
    event_type VARCHAR(100) NOT NULL,        -- e.g., 'TRADE_EXECUTED', 'CHALLENGE_FAILED'
    event_version INTEGER NOT NULL DEFAULT 1, -- Schema version for evolution
    sequence_number BIGINT NOT NULL,         -- Monotonic sequence per challenge

    -- Event payload (structured data)
    event_data JSONB NOT NULL,               -- Complete event payload

    -- Human-readable explanation (for audit reports)
    description TEXT NOT NULL,

    -- Timing (business vs system time)
    occurred_at TIMESTAMPTZ NOT NULL,        -- Business time (when event occurred)
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- System time (when recorded)

    -- Event correlation (for distributed tracing)
    correlation_id UUID,                     -- Links related events
    causation_id UUID,                       -- Event that caused this event

    -- Metadata for future expansion
    metadata JSONB DEFAULT '{}'
);

-- Referential integrity (no CASCADE - events are audit data)
ALTER TABLE challenge_events ADD CONSTRAINT fk_challenge_events_challenge_id
    FOREIGN KEY (challenge_id) REFERENCES challenges(id);

-- Sequence constraints (strict ordering per challenge)
ALTER TABLE challenge_events ADD CONSTRAINT uk_challenge_events_sequence
    UNIQUE (challenge_id, sequence_number);

-- Business rules
ALTER TABLE challenge_events ADD CONSTRAINT chk_recorded_at_after_occurred_at
    CHECK (recorded_at >= occurred_at);

ALTER TABLE challenge_events ADD CONSTRAINT chk_event_type_not_empty
    CHECK (length(trim(event_type)) > 0);

-- IMMUTABILITY ENFORCEMENT (event sourcing principle)
CREATE OR REPLACE FUNCTION prevent_event_modifications()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow INSERTs, but prevent UPDATEs and DELETEs
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Events are immutable - cannot update event %', OLD.id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Events are immutable - cannot delete event %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_challenge_events_immutable
    BEFORE UPDATE OR DELETE ON challenge_events
    FOR EACH ROW EXECUTE FUNCTION prevent_event_modifications();

-- Indexes for event sourcing patterns
CREATE INDEX idx_challenge_events_challenge_id ON challenge_events (challenge_id);
CREATE INDEX idx_challenge_events_challenge_sequence ON challenge_events (challenge_id, sequence_number);
CREATE INDEX idx_challenge_events_type ON challenge_events (event_type);
CREATE INDEX idx_challenge_events_occurred_at ON challenge_events (occurred_at);
CREATE INDEX idx_challenge_events_recorded_at ON challenge_events (recorded_at);
CREATE INDEX idx_challenge_events_correlation_id ON challenge_events (correlation_id) WHERE correlation_id IS NOT NULL;

-- Partial indexes for common event types
CREATE INDEX idx_events_trade_executed ON challenge_events (challenge_id, occurred_at)
    WHERE event_type = 'TRADE_EXECUTED';
CREATE INDEX idx_events_status_changes ON challenge_events (challenge_id, occurred_at)
    WHERE event_type IN ('CHALLENGE_STATUS_CHANGED', 'CHALLENGE_FAILED', 'CHALLENGE_FUNDED');

-- GIN index for JSONB queries (rule violation details, etc.)
CREATE INDEX idx_challenge_events_data_gin ON challenge_events USING GIN (event_data);

-- Comments for audit documentation
COMMENT ON TABLE challenge_events IS 'Event-sourced audit log - append-only, replayable for dispute resolution';
COMMENT ON COLUMN challenge_events.event_type IS 'Business event type (TRADE_EXECUTED, CHALLENGE_FAILED, etc.)';
COMMENT ON COLUMN challenge_events.event_data IS 'Complete structured event payload (JSONB)';
COMMENT ON COLUMN challenge_events.description IS 'Human-readable explanation for audit reports';
COMMENT ON COLUMN challenge_events.occurred_at IS 'Business time (when event occurred in domain)';
COMMENT ON COLUMN challenge_events.recorded_at IS 'System time (when event was persisted)';
COMMENT ON COLUMN challenge_events.correlation_id IS 'Links related events across distributed systems';

/*
TASK 4 EXPLANATION: CHALLENGE_EVENTS TABLE DESIGN

Event Schema Design:
Events are versioned JSONB payloads with standardized structure:

{
  "eventType": "TRADE_EXECUTED",
  "eventVersion": 1,
  "challengeId": "uuid",
  "occurredAt": "2024-01-01T12:00:00Z",
  "data": {
    "tradeId": "external_id",
    "symbol": "EURUSD",
    "side": "BUY",
    "quantity": "10000",
    "price": "1.0850",
    "realizedPnl": 200.00,
    "commission": 5.00
  },
  "metadata": {}
}

Indexing Strategy:
- (challenge_id, sequence_number): Strict ordering for replay
- event_type: Filter by event type (common queries)
- occurred_at: Time-based event queries
- correlation_id: Distributed tracing lookups
- GIN on event_data: Query rule violation details, trade amounts, etc.

How to Reconstruct Challenge Timeline:
1. SELECT * FROM challenge_events WHERE challenge_id = ?
   ORDER BY sequence_number ASC;
2. Apply events in order to reconstruct state:
   - TRADE_EXECUTED: Update equity, check rules
   - CHALLENGE_STATUS_CHANGED: Update status
   - CHALLENGE_FAILED/FUNDED: Terminal state
3. Validate: Final state should match current challenge table

This design enables:
- Complete audit trails for regulators
- Dispute resolution through event replay
- System reconstruction after failures
- Business intelligence and analytics
- Compliance reporting and monitoring
*/

-- ============================================================================
-- TASK 5: PAYMENTS TABLE
-- ============================================================================

-- Payment processing for challenge purchases
-- Supports multiple providers, idempotent operations, decoupled from challenge lifecycle
CREATE TABLE payments (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Business relationships
    user_id UUID NOT NULL REFERENCES users(id),
    challenge_id UUID REFERENCES challenges(id), -- May be NULL for failed payments

    -- Payment provider details
    provider payment_provider_enum NOT NULL,     -- STRIPE, PAYPAL, etc.
    provider_payment_id VARCHAR(255) UNIQUE,     -- External payment ID (idempotency key)
    provider_transaction_id VARCHAR(255),        -- Provider's transaction reference

    -- Financial details
    amount NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    fee NUMERIC(15,2) NOT NULL DEFAULT 0,        -- Processing fee charged by provider

    -- Payment lifecycle
    status payment_status_enum NOT NULL DEFAULT 'PENDING',

    -- Timing for audit and reconciliation
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- When payment was started
    processed_at TIMESTAMPTZ,                      -- When payment was completed/failed
    settled_at TIMESTAMPTZ,                        -- When funds were settled

    -- Error handling and retry logic
    failure_reason VARCHAR(500),                   -- Provider error message
    retry_count INTEGER NOT NULL DEFAULT 0,

    -- Webhook and callback data
    webhook_data JSONB,                            -- Raw webhook payload from provider
    provider_metadata JSONB DEFAULT '{}',          -- Additional provider-specific data

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enums for payment processing
CREATE TYPE payment_provider_enum AS ENUM ('STRIPE', 'PAYPAL', 'BANK_TRANSFER');
CREATE TYPE payment_status_enum AS ENUM ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED');

-- Referential integrity
ALTER TABLE payments ADD CONSTRAINT fk_payments_user_id
    FOREIGN KEY (user_id) REFERENCES users(id);

ALTER TABLE payments ADD CONSTRAINT fk_payments_challenge_id
    FOREIGN KEY (challenge_id) REFERENCES challenges(id);

-- Business constraints
ALTER TABLE payments ADD CONSTRAINT chk_payment_success_has_challenge
    CHECK (
        (status = 'SUCCESS' AND challenge_id IS NOT NULL) OR
        (status != 'SUCCESS')
    );

ALTER TABLE payments ADD CONSTRAINT chk_processed_at_for_completed
    CHECK (
        (status IN ('SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED') AND processed_at IS NOT NULL) OR
        (status NOT IN ('SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED'))
    );

ALTER TABLE payments ADD CONSTRAINT chk_currency_valid
    CHECK (currency IN ('USD', 'EUR', 'GBP'));

-- Indexes for payment processing workflows
CREATE INDEX idx_payments_user_id ON payments (user_id);
CREATE INDEX idx_payments_challenge_id ON payments (challenge_id) WHERE challenge_id IS NOT NULL;
CREATE INDEX idx_payments_provider_payment_id ON payments (provider_payment_id) WHERE provider_payment_id IS NOT NULL;
CREATE INDEX idx_payments_status ON payments (status);
CREATE INDEX idx_payments_provider_status ON payments (provider, status);
CREATE INDEX idx_payments_initiated_at ON payments (initiated_at);
CREATE INDEX idx_payments_processed_at ON payments (processed_at) WHERE processed_at IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX idx_payments_pending_webhooks ON payments (provider, updated_at)
    WHERE status IN ('PENDING', 'PROCESSING');
CREATE INDEX idx_payments_recent_failures ON payments (user_id, initiated_at)
    WHERE status = 'FAILED' AND initiated_at > NOW() - INTERVAL '7 days';

-- Comments for audit documentation
COMMENT ON TABLE payments IS 'Payment processing for challenge purchases - decoupled from challenge lifecycle';
COMMENT ON COLUMN payments.provider_payment_id IS 'External payment ID for idempotency and reconciliation';
COMMENT ON COLUMN payments.webhook_data IS 'Raw webhook payload for audit and dispute resolution';
COMMENT ON COLUMN payments.failure_reason IS 'Provider error message for troubleshooting';
COMMENT ON COLUMN payments.retry_count IS 'Number of retry attempts for failed payments';

/*
TASK 5 EXPLANATION: PAYMENTS TABLE DESIGN

Constraints & Indexes:
- provider_payment_id UNIQUE: Prevents duplicate processing (idempotency)
- Business rules: Successful payments must have challenge_id
- Status-based constraints: Terminal states require processed_at
- Provider-specific indexes: Optimize webhook processing
- Time-based indexes: Recent payment queries

Why Payment State is Decoupled from Challenge Status:
1. Payment Success != Challenge Activation: Payment may succeed but challenge creation fail
2. Refund Scenarios: Payment refunded but challenge may continue (edge case)
3. Audit Independence: Payment history separate from trading activity
4. Provider Reconciliation: Match provider statements independently
5. Dispute Resolution: Payment issues don't affect trading decisions

Example Usage Scenarios:
- Webhook Processing: Find payment by provider_payment_id, update status
- User Dashboard: Show payment history regardless of challenge status
- Financial Reporting: Payment reconciliation separate from trading P&L
- Refund Processing: Update payment status without affecting challenge
- Audit Queries: Payment timeline independent of trading activity

This design ensures:
- PCI DSS compliance readiness (no card data stored)
- Multi-provider support (Stripe, PayPal, etc.)
- Idempotent webhook processing
- Financial reconciliation capabilities
- Regulatory reporting compliance
*/

-- ============================================================================
-- TASK 6: RISK_ALERTS TABLE
-- ============================================================================

-- Risk monitoring and alerting system
-- Stores warnings and alerts from Risk Engine - NOT part of core decision logic
CREATE TABLE risk_alerts (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert context
    challenge_id UUID REFERENCES challenges(id),    -- May be NULL for system-wide alerts
    user_id UUID REFERENCES users(id),              -- For user-specific alerts

    -- Alert classification
    alert_type VARCHAR(100) NOT NULL,               -- e.g., 'HIGH_DRAWDOWN', 'UNUSUAL_ACTIVITY'
    severity alert_severity_enum NOT NULL DEFAULT 'MEDIUM',

    -- Alert content
    title VARCHAR(255) NOT NULL,                    -- Human-readable title
    message TEXT NOT NULL,                          -- Detailed explanation
    alert_data JSONB DEFAULT '{}',                  -- Structured alert data (metrics, thresholds)

    -- Alert lifecycle
    status alert_status_enum NOT NULL DEFAULT 'ACTIVE',
    acknowledged_at TIMESTAMPTZ,                    -- When alert was acknowledged
    acknowledged_by UUID REFERENCES users(id),     -- Who acknowledged it
    resolved_at TIMESTAMPTZ,                        -- When alert was resolved

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Correlation and grouping
    correlation_id UUID,                            -- Group related alerts
    rule_id VARCHAR(100),                           -- Which risk rule triggered this
    threshold_breached JSONB,                       -- Threshold details (value, limit, etc.)
);

-- Enums for alert classification
CREATE TYPE alert_severity_enum AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE alert_status_enum AS ENUM ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE');

-- Referential integrity
ALTER TABLE risk_alerts ADD CONSTRAINT fk_risk_alerts_challenge_id
    FOREIGN KEY (challenge_id) REFERENCES challenges(id);

ALTER TABLE risk_alerts ADD CONSTRAINT fk_risk_alerts_user_id
    FOREIGN KEY (user_id) REFERENCES users(id);

ALTER TABLE risk_alerts ADD CONSTRAINT fk_risk_alerts_acknowledged_by
    FOREIGN KEY (acknowledged_by) REFERENCES users(id);

-- Business constraints
ALTER TABLE risk_alerts ADD CONSTRAINT chk_acknowledged_status
    CHECK (
        (status = 'ACKNOWLEDGED' AND acknowledged_at IS NOT NULL) OR
        (status != 'ACKNOWLEDGED')
    );

ALTER TABLE risk_alerts ADD CONSTRAINT chk_resolved_status
    CHECK (
        (status IN ('RESOLVED', 'FALSE_POSITIVE') AND resolved_at IS NOT NULL) OR
        (status NOT IN ('RESOLVED', 'FALSE_POSITIVE'))
    );

-- Indexes for monitoring and alerting workflows
CREATE INDEX idx_risk_alerts_challenge_id ON risk_alerts (challenge_id) WHERE challenge_id IS NOT NULL;
CREATE INDEX idx_risk_alerts_user_id ON risk_alerts (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_risk_alerts_type_severity ON risk_alerts (alert_type, severity);
CREATE INDEX idx_risk_alerts_status ON risk_alerts (status);
CREATE INDEX idx_risk_alerts_created_at ON risk_alerts (created_at);
CREATE INDEX idx_risk_alerts_correlation_id ON risk_alerts (correlation_id) WHERE correlation_id IS NOT NULL;

-- Partial indexes for active alerts (most queried)
CREATE INDEX idx_risk_alerts_active ON risk_alerts (severity, created_at) WHERE status = 'ACTIVE';
CREATE INDEX idx_risk_alerts_unacknowledged ON risk_alerts (severity, created_at)
    WHERE status = 'ACTIVE' AND acknowledged_at IS NULL;

-- Comments for audit documentation
COMMENT ON TABLE risk_alerts IS 'Risk monitoring alerts - separate from core decision logic for monitoring purposes';
COMMENT ON COLUMN risk_alerts.alert_type IS 'Categorization of risk condition (HIGH_DRAWDOWN, UNUSUAL_ACTIVITY, etc.)';
COMMENT ON COLUMN risk_alerts.alert_data IS 'Structured data with metrics and threshold details';
COMMENT ON COLUMN risk_alerts.correlation_id IS 'Groups related alerts for incident management';
COMMENT ON COLUMN risk_alerts.threshold_breached IS 'Details of what threshold was exceeded';

-- ============================================================================
-- TASK 6.5: RISK_SCORES TABLE (Adaptive Risk Scoring)
-- ============================================================================

-- Risk Scores table for AI-powered adaptive risk assessment
-- Append-only storage of risk score computations for audit and ML training
CREATE TABLE risk_scores (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Assessment context
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Risk score result
    risk_score NUMERIC(5,2) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_level risk_level_enum NOT NULL,

    -- Score breakdown for explainability
    score_breakdown JSONB NOT NULL,  -- Component scores and weights

    -- Feature summary (snapshot for reproducibility)
    feature_summary JSONB NOT NULL,  -- Key metrics used in scoring

    -- Assessment metadata
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessment_version VARCHAR(50) NOT NULL DEFAULT '1.0',  -- Model version

    -- Action plan (computed recommendations)
    action_plan JSONB DEFAULT '{}',  -- Recommended actions based on score

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata for future ML training
    training_labels JSONB DEFAULT '{}',  -- Future labels for supervised learning

    -- Optimistic locking
    version BIGINT NOT NULL DEFAULT 1
);

-- Enum for risk levels (matches application logic)
CREATE TYPE risk_level_enum AS ENUM ('STABLE', 'MONITOR', 'HIGH_RISK', 'CRITICAL');

-- Indexes for risk monitoring and analytics
CREATE INDEX idx_risk_scores_challenge_id ON risk_scores (challenge_id);
CREATE INDEX idx_risk_scores_user_id ON risk_scores (user_id);
CREATE INDEX idx_risk_scores_risk_level ON risk_scores (risk_level);
CREATE INDEX idx_risk_scores_assessed_at ON risk_scores (assessed_at);
CREATE INDEX idx_risk_scores_score ON risk_scores (risk_score);

-- Composite indexes for common queries
CREATE INDEX idx_risk_scores_challenge_assessed ON risk_scores (challenge_id, assessed_at DESC);
CREATE INDEX idx_risk_scores_level_assessed ON risk_scores (risk_level, assessed_at DESC);

-- Partial indexes for active challenges (most relevant for monitoring)
CREATE INDEX idx_risk_scores_active_challenges ON risk_scores (challenge_id, assessed_at DESC)
    WHERE EXISTS (
        SELECT 1 FROM challenges c
        WHERE c.id = risk_scores.challenge_id
        AND c.status IN ('ACTIVE', 'PENDING')
    );

-- Comments for audit documentation
COMMENT ON TABLE risk_scores IS 'Adaptive risk scoring results - AI-powered assessment for enhanced risk monitoring';
COMMENT ON COLUMN risk_scores.risk_score IS 'Computed risk score (0-100) using explainable heuristics';
COMMENT ON COLUMN risk_scores.score_breakdown IS 'Detailed breakdown of score components and weights for explainability';
COMMENT ON COLUMN risk_scores.feature_summary IS 'Snapshot of trading features used in risk computation';
COMMENT ON COLUMN risk_scores.assessment_version IS 'Version of scoring model/algorithm used';
COMMENT ON COLUMN risk_scores.action_plan IS 'Computed recommendations based on risk assessment';

/*
TASK 6.5 EXPLANATION: RISK_SCORES TABLE DESIGN

Purpose:
The risk_scores table stores the results of AI-powered adaptive risk assessments.
It provides a complete audit trail of risk scoring decisions while enabling
explainability and future ML model training.

Why This Table Exists:
1. Audit Compliance: Complete history of risk assessments for regulatory review
2. Explainability: Score breakdowns allow understanding of risk computation
3. ML Training: Historical scores and outcomes for model improvement
4. Monitoring: Trend analysis and risk escalation tracking
5. Decision Support: Actionable recommendations based on risk levels

Key Design Decisions:
1. Append-Only: Never update or delete - maintains audit integrity
2. Feature Snapshot: Store input features for reproducibility
3. Score Breakdown: Detailed component scores for explainability
4. Version Tracking: Track scoring algorithm versions
5. Action Plans: Store computed recommendations

Separation from risk_alerts:
- risk_scores: Assessment results (complete risk profile)
- risk_alerts: Event-driven notifications (immediate actions)

Example Usage Scenarios:
1. Risk Committee Review: Historical risk scores for oversight
2. Trader Performance: Risk score trends over time
3. Model Validation: Compare scores against actual outcomes
4. Regulatory Audit: Complete audit trail of risk assessments
5. ML Training: Labeled data for improved scoring models

Data Retention:
- 7+ years for regulatory compliance
- Partitioned by year for performance
- Archived to cold storage after 2 years

This table enables TradeSense AI to provide sophisticated risk intelligence
while maintaining full transparency and regulatory compliance.
*/

/*
TASK 6 EXPLANATION: RISK_ALERTS TABLE DESIGN

Intended Usage Scenarios:
1. Real-time Monitoring: Dashboard showing active high-severity alerts
2. Risk Oversight: Ops team monitoring for concerning patterns
3. Incident Response: Correlated alerts grouped by correlation_id
4. Compliance Reporting: Audit trail of risk events and responses
5. Performance Analytics: False positive rates, response times

Why This is Separated from challenge_events:
1. Decision vs Monitoring: challenge_events drive business logic, alerts are observational
2. Performance Isolation: Alert queries don't impact core trading performance
3. Different Retention: Alerts may have shorter retention than audit events
4. Access Control: Different teams access alerts vs core business events
5. Update Patterns: Alerts can be acknowledged/resolved, events cannot

Example Alert Types:
- HIGH_DRAWDOWN: Equity dropped below warning threshold (not rule violation yet)
- UNUSUAL_ACTIVITY: Trading pattern deviates from normal behavior
- SYSTEM_LATENCY: Risk rule evaluation taking too long
- CONCURRENT_TRADES: Multiple trades in same millisecond detected
- LARGE_POSITION: Single trade exceeds position size limits

This design enables:
- Proactive risk monitoring without affecting core logic
- Alert escalation workflows
- Incident management and response tracking
- Compliance with risk management regulations
- Performance optimization through separation of concerns
*/

-- ============================================================================
-- TASK 7: DATABASE-LEVEL SAFEGUARDS
-- ============================================================================

-- Additional indexes for concurrency control and data integrity
-- Critical for preventing race conditions in high-frequency trading scenarios

-- Challenge update locking (optimistic concurrency)
CREATE UNIQUE INDEX idx_challenges_id_version ON challenges (id, version);

-- Trade sequence locking (prevent out-of-order trades)
CREATE UNIQUE INDEX idx_trades_challenge_sequence_lock ON trades (challenge_id, sequence_number);

-- Event sequence locking (prevent event reordering)
CREATE UNIQUE INDEX idx_events_challenge_sequence_lock ON challenge_events (challenge_id, sequence_number);

-- Payment idempotency locking
CREATE UNIQUE INDEX idx_payments_provider_lock ON payments (provider, provider_payment_id);

-- User session locking (prevent concurrent account modifications)
CREATE INDEX idx_users_concurrent_updates ON users (id, version);

/*
TASK 7 EXPLANATION: DATABASE SAFEGUARDS

Required Indexes for Concurrency Control:
- challenges(id, version): Optimistic locking for challenge state updates
- trades(challenge_id, sequence_number): Strict ordering enforcement
- challenge_events(challenge_id, sequence_number): Event sourcing sequence integrity
- payments(provider, provider_payment_id): Idempotent webhook processing
- users(id, version): Concurrent user account modifications

Example SELECT FOR UPDATE Usage:

1. Challenge Trade Processing (Pessimistic Locking):
```sql
BEGIN;
SELECT id, version, current_equity, status
FROM challenges
WHERE id = $1 AND status = 'ACTIVE'
FOR UPDATE;

-- Process trade logic here --

UPDATE challenges
SET current_equity = $2, version = version + 1, last_trade_at = NOW()
WHERE id = $1 AND version = $3;

COMMIT;
```

2. Optimistic Concurrency with Retry:
```sql
-- Application layer handles version check and retry
SELECT version FROM challenges WHERE id = $1;

-- Process trade with rule evaluation --

UPDATE challenges
SET current_equity = $2, version = $4
WHERE id = $1 AND version = $3;  -- Will fail if concurrent update occurred
```

3. Trade Sequence Locking:
```sql
-- Ensure trades are processed in strict order
SELECT MAX(sequence_number) + 1 as next_sequence
FROM trades
WHERE challenge_id = $1
FOR UPDATE;  -- Lock prevents concurrent trade insertion
```

When Locking is Mandatory:
1. Challenge State Updates: Always use optimistic locking (version column)
2. Trade Insertion: Sequence number allocation requires locking
3. Payment Processing: Provider payment ID uniqueness requires locking
4. Terminal State Transitions: FAILED/FUNDED status changes are critical
5. High-Frequency Trading: Sub-millisecond trades need strict sequencing

Trade-offs (Performance vs Safety):

Performance Impact:
- Pessimistic locking reduces concurrency but guarantees consistency
- Optimistic locking allows higher throughput but requires retry logic
- Sequence locks prevent parallel trade processing per challenge
- Additional indexes increase write latency but enable fast reads

Safety Benefits:
- Prevents lost updates in concurrent trading scenarios
- Guarantees trade ordering (critical for equity calculations)
- Enables idempotent operations (webhooks, retries)
- Supports financial audit requirements (deterministic replay)

Recommended Strategy:
- Use optimistic locking for challenge updates (high throughput)
- Use pessimistic locking for trade sequence allocation (strict ordering)
- Implement exponential backoff for optimistic lock failures
- Monitor lock contention and adjust isolation levels as needed
- Use READ COMMITTED isolation for balance of performance and consistency
*/

-- ============================================================================
-- TASK 8: READ MODELS FOR ANALYTICS AND LEADERBOARD
-- ============================================================================

-- Materialized view for leaderboard - optimized for ranking queries
-- Refreshes periodically to balance performance and data freshness
CREATE MATERIALIZED VIEW challenge_leaderboard AS
SELECT
    c.id as challenge_id,
    c.user_id,
    c.challenge_type,
    c.initial_balance,
    c.current_equity,
    c.max_equity_ever,
    c.status,
    c.total_trades,
    c.total_pnl,

    -- Calculated performance metrics
    ROUND(
        ((c.current_equity - c.initial_balance) / c.initial_balance) * 100,
        2
    ) as profit_percentage,

    ROUND(
        ((c.max_equity_ever - c.current_equity) / c.max_equity_ever) * 100,
        2
    ) as current_drawdown_percentage,

    -- Time-based metrics
    c.started_at,
    c.ended_at,
    c.last_trade_at,

    -- Ranking score (composite metric for leaderboard)
    CASE
        WHEN c.status = 'FUNDED' THEN
            -- Funded challenges: profit % + consistency bonus
            ROUND(
                ((c.current_equity - c.initial_balance) / c.initial_balance) * 100
                + (c.total_trades * 0.1)  -- Consistency bonus
                - EXTRACT(EPOCH FROM (c.ended_at - c.started_at))/86400,  -- Speed bonus (days)
                2
            )
        WHEN c.status = 'ACTIVE' THEN
            -- Active challenges: current profit % + activity bonus
            ROUND(
                ((c.current_equity - c.initial_balance) / c.initial_balance) * 100
                + (c.total_trades * 0.05),  -- Activity bonus
                2
            )
        ELSE 0  -- Failed or pending challenges don't rank
    END as ranking_score,

    -- Metadata for filtering
    EXTRACT(EPOCH FROM (c.ended_at - c.started_at))/86400 as duration_days,
    CASE WHEN c.status = 'FUNDED' THEN true ELSE false END as is_funded,
    CASE WHEN c.status = 'ACTIVE' THEN true ELSE false END as is_active

FROM challenges c
WHERE c.status IN ('ACTIVE', 'FUNDED')  -- Only show active and successful challenges
ORDER BY ranking_score DESC, ended_at DESC;

-- Indexes for leaderboard queries (critical for performance)
CREATE UNIQUE INDEX idx_leaderboard_challenge_id ON challenge_leaderboard (challenge_id);
CREATE INDEX idx_leaderboard_ranking_score ON challenge_leaderboard (ranking_score DESC);
CREATE INDEX idx_leaderboard_user_id ON challenge_leaderboard (user_id);
CREATE INDEX idx_leaderboard_status ON challenge_leaderboard (is_funded, is_active);
CREATE INDEX idx_leaderboard_challenge_type ON challenge_leaderboard (challenge_type);
CREATE INDEX idx_leaderboard_profit_percentage ON challenge_leaderboard (profit_percentage DESC);

-- Refresh function for the materialized view
CREATE OR REPLACE FUNCTION refresh_challenge_leaderboard()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY challenge_leaderboard;
END;
$$;

-- View for detailed challenge analytics (real-time, not materialized)
CREATE VIEW challenge_performance_analytics AS
SELECT
    c.id,
    c.user_id,
    c.challenge_type,
    c.status,

    -- Equity progression
    c.initial_balance,
    c.current_equity,
    c.max_equity_ever,

    -- Performance metrics
    ROUND(((c.current_equity - c.initial_balance) / c.initial_balance) * 100, 2) as profit_percentage,
    ROUND(((c.max_equity_ever - c.current_equity) / c.max_equity_ever) * 100, 2) as drawdown_percentage,

    -- Trading activity
    c.total_trades,
    c.total_pnl,

    -- Daily metrics
    c.daily_start_equity,
    c.daily_max_equity,
    c.daily_min_equity,
    ROUND(((c.daily_start_equity - c.daily_min_equity) / c.daily_start_equity) * 100, 2) as daily_drawdown_used,

    -- Time metrics
    c.started_at,
    c.ended_at,
    c.last_trade_at,
    EXTRACT(EPOCH FROM (c.last_trade_at - c.started_at))/3600 as trading_hours,

    -- Trade statistics from trades table
    COALESCE(trade_stats.total_volume, 0) as total_volume,
    COALESCE(trade_stats.win_rate, 0) as win_rate,
    COALESCE(trade_stats.avg_trade_size, 0) as avg_trade_size

FROM challenges c
LEFT JOIN (
    SELECT
        challenge_id,
        COUNT(*) as total_volume,
        ROUND(
            (COUNT(*) FILTER (WHERE realized_pnl > 0))::numeric /
            NULLIF(COUNT(*), 0) * 100, 2
        ) as win_rate,
        ROUND(AVG(ABS(realized_pnl)) FILTER (WHERE realized_pnl != 0), 2) as avg_trade_size
    FROM trades
    GROUP BY challenge_id
) trade_stats ON c.id = trade_stats.challenge_id;

-- Indexes for analytics queries
CREATE INDEX idx_analytics_user_status ON challenges (user_id, status);
CREATE INDEX idx_analytics_date_range ON challenges (started_at, ended_at) WHERE started_at IS NOT NULL;
CREATE INDEX idx_analytics_performance ON challenges (status, current_equity, total_trades);

/*
TASK 8 EXPLANATION: READ MODELS DESIGN

MATERIALIZED VIEW: challenge_leaderboard
- Contains only ACTIVE and FUNDED challenges (most relevant for users)
- Pre-computed ranking scores for fast leaderboard queries
- Composite ranking algorithm: profit % + consistency/activity bonuses
- Optimized for top-N queries with LIMIT/OFFSET

Indexing Strategy:
- ranking_score DESC: Primary leaderboard sorting
- challenge_id UNIQUE: Fast lookups for specific challenges
- user_id: Find user's position in leaderboard
- status filters: Separate active vs funded leaderboards
- profit_percentage: Alternative sorting options

Refresh Strategy:
- CONCURRENTLY refresh to avoid blocking reads during updates
- Refresh frequency: Every 5-15 minutes (balance freshness vs performance)
- Trigger-based refresh possible but may cause performance issues
- Manual refresh for immediate accuracy after important events

Why Read Models are Separated from Write Models:
1. Performance Isolation: Analytics queries don't impact transactional performance
2. Different Optimization: Write models optimized for updates, read models for queries
3. Data Transformation: Calculated metrics (profit %, drawdown) pre-computed
4. Scaling Strategy: Read models can be replicated to separate reporting instances
5. Schema Evolution: Read models can change without affecting core business logic

Example Queries:
```sql
-- Top 10 leaderboard
SELECT * FROM challenge_leaderboard
ORDER BY ranking_score DESC
LIMIT 10;

-- User's ranking position
SELECT COUNT(*) + 1 as rank
FROM challenge_leaderboard
WHERE ranking_score > (
    SELECT ranking_score FROM challenge_leaderboard WHERE challenge_id = $1
);

-- Challenge type performance
SELECT challenge_type, AVG(profit_percentage), COUNT(*)
FROM challenge_leaderboard
WHERE is_funded = true
GROUP BY challenge_type;
```

This design enables:
- Sub-second leaderboard queries (materialized view)
- Complex analytics without impacting core performance
- Flexible ranking algorithms (easily modified in view definition)
- Historical analysis capabilities (time-based filtering)
- Real-time dashboard updates (periodic refresh)
*/

-- ============================================================================
-- TASK 9: FINANCIAL AUDIT REQUIREMENTS SATISFACTION
-- ============================================================================

/*
STRUCTURED EXPLANATION: HOW SCHEMA SATISFIES FINANCIAL AUDIT REQUIREMENTS

This database schema is designed to withstand scrutiny from regulators, auditors, and CTOs
in a regulated FinTech environment. Every design decision supports auditability, traceability,
and compliance with financial industry standards.

================================================================================
IM MUTABILITY GUARANTEES (Core Audit Principle)
================================================================================

1. TRADES TABLE: Append-only ledger with triggers preventing UPDATE/DELETE
   - Why: Historical trade data cannot be altered (regulatory requirement)
   - Audit: All trades are immutable records of financial transactions
   - Enforcement: Database triggers + application-layer controls

2. CHALLENGE_EVENTS TABLE: Event-sourced audit log
   - Why: Complete business event history for reconstruction
   - Audit: Every state change is logged with human-readable explanations
   - Enforcement: Triggers prevent modifications

3. PAYMENTS TABLE: Financial transaction audit trail
   - Why: Payment processing must be fully traceable
   - Audit: Provider reconciliation and dispute resolution
   - Enforcement: Status constraints and webhook data preservation

================================================================================
TRACEABILITY OF DECISIONS (Rule → Data → Event → Decision Mapping)
================================================================================

CLEAR MAPPING: RULE EVALUATION PROCESS

┌─────────────────────────────────────────────────────────────────────────────┐
│                           RULE EVALUATION FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. RULE DEFINITION (Business Logic)                                        │
│    - Max Daily Drawdown: (Daily Start - Current) / Daily Start > 5%       │
│    - Max Total Drawdown: (Max Equity - Current) / Max Equity > 10%        │
│    - Profit Target: (Current - Initial) / Initial >= 8%                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. DATA CAPTURE (Challenge State)                                          │
│    - current_equity: Real-time account value                              │
│    - max_equity_ever: Peak value for total drawdown calc                  │
│    - daily_start_equity: Opening balance each day                        │
│    - initial_balance: Starting capital (immutable)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. EVENT RECORDING (Audit Trail)                                          │
│    Event Type: TRADE_EXECUTED                                              │
│    Payload: {tradeId, pnl, symbol, timestamp, equity_before/after}        │
│                                                                             │
│    Event Type: CHALLENGE_FAILED                                             │
│    Payload: {reason: "MAX_DAILY_DRAWDOWN", metrics: {...}}                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. DECISION VERIFICATION (Auditor Reconstruction)                         │
│    Query: SELECT * FROM challenge_events                                   │
│           WHERE challenge_id = ? ORDER BY sequence_number                 │
│                                                                             │
│    Replay: Apply events in order → Verify final state matches             │
│    Result: Deterministic decision reconstruction                          │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
RECONSTRUCTION OF ACCOUNT STATE (Dispute Resolution)
================================================================================

CHALLENGE STATE RECONSTRUCTION QUERY:

```sql
-- Step 1: Get all events for the challenge
SELECT event_type, event_data, occurred_at, sequence_number
FROM challenge_events
WHERE challenge_id = $1
ORDER BY sequence_number ASC;

-- Step 2: Reconstruct equity changes
SELECT
    trade_id,
    realized_pnl,
    SUM(realized_pnl) OVER (ORDER BY executed_at) + initial_balance as reconstructed_equity
FROM trades
WHERE challenge_id = $1
ORDER BY executed_at;

-- Step 3: Verify rule application at each step
-- Auditor can replay the exact rule evaluation logic
-- Compare reconstructed equity vs rule thresholds
```

================================================================================
COMPLIANCE MINDSET (SOC 2 / Financial Best Practices)
================================================================================

PRINCIPLES IMPLEMENTED:

1. AUDIT TRAIL INTEGRITY
   - All financial events logged (trades, payments, state changes)
   - Timestamps in UTC (no timezone ambiguity)
   - Sequence numbers prevent reordering
   - Human-readable event descriptions

2. DATA RETENTION & DELETION
   - No hard deletes on financial data (soft deletes only)
   - Configurable retention periods for different data types
   - Clear audit trail of data lifecycle

3. CHANGE MANAGEMENT
   - Schema versioning through event_data JSONB
   - Migration scripts with rollback capabilities
   - Zero-downtime deployment considerations

4. ACCESS CONTROLS
   - Role-based access (USER, ADMIN, SUPERADMIN)
   - Audit logging of data access
   - Encryption at rest and in transit

5. BUSINESS CONTINUITY
   - Event sourcing enables complete system reconstruction
   - Immutable data survives system failures
   - Point-in-time recovery capabilities

================================================================================
AUDITOR DEFENSE STRATEGY
================================================================================

WHEN AUDITORS ASK: "How do you prove this decision was correct?"

RESPONSE FRAMEWORK:
1. "Show me the rule" → Business logic in domain layer (code repository)
2. "Show me the data" → Challenge state in database (current_equity, max_equity_ever)
3. "Show me the event" → challenge_events table (exact timestamp, payload)
4. "Let me verify" → Reconstruct decision using event replay
5. "Prove it hasn't changed" → Immutability constraints and triggers

CRITICAL SUCCESS FACTORS:
- Every decision is logged as an event
- Events contain complete context (metrics, thresholds, timestamps)
- Events are immutable and sequentially ordered
- System can be reconstructed from event log
- Human-readable explanations for non-technical auditors

================================================================================
REGULATORY REPORTING CAPABILITIES
================================================================================

SUPPORTED REPORTS:
1. Transaction Reconciliation: trades + payments tables
2. Risk Rule Effectiveness: challenge_events analysis
3. Customer Activity: User challenge history
4. Financial Performance: Aggregated P&L reporting
5. Audit Trail: Complete event history for any time period

This schema design ensures that TradeSense AI can pass any financial audit
with complete confidence, providing regulators with the transparency and
traceability required for regulated financial services.
*/

-- ============================================================================
-- TASK 10: MIGRATION STRATEGY
-- ============================================================================

/*
MIGRATION PRINCIPLES FOR REGULATED FINTECH DATABASE

This schema requires careful evolution due to financial audit and regulatory requirements.
All migrations must maintain backward compatibility and data integrity.

================================================================================
CORE PRINCIPLES
================================================================================

1. ZERO DATA LOSS: Never drop columns or tables with financial data
2. BACKWARD COMPATIBILITY: Old code must work with new schema
3. AUDIT TRAIL PRESERVATION: Event history remains intact
4. BUSINESS LOGIC CONSISTENCY: Rule evaluation logic unaffected
5. PERFORMANCE MAINTENANCE: Indexes optimized for new query patterns

================================================================================
MIGRATION WORKFLOW
================================================================================

PHASE 1: PLANNING
- Impact assessment on existing queries and business logic
- Audit review for regulatory compliance
- Performance testing on realistic data volumes
- Rollback plan documented and tested

PHASE 2: DEVELOPMENT
- Alembic migration script with both upgrade/downgrade
- Schema changes tested in staging environment
- Application code updated for new schema
- Integration tests pass with new schema

PHASE 3: DEPLOYMENT
- Zero-downtime deployment (if possible)
- Feature flags for gradual rollout
- Monitoring dashboards for performance impact
- Rollback procedures ready

PHASE 4: VALIDATION
- Data integrity checks post-migration
- Performance benchmarks vs baseline
- Audit trail continuity verification
- Business metric validation

================================================================================
EXAMPLE MIGRATION: ADDING NEW RULE FIELD
================================================================================

SCENARIO: Adding minimum_trading_days requirement to challenges

MIGRATION SCRIPT (Alembic format):

```python
# alembic/versions/001_add_min_trading_days.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add new column with default value
    op.add_column('challenges',
        sa.Column('min_trading_days', sa.Integer(), nullable=False, default=0)
    )

    # Update existing challenges to have reasonable default
    op.execute("""
        UPDATE challenges
        SET min_trading_days = 5
        WHERE challenge_type = 'PHASE_1'
    """)

    op.execute("""
        UPDATE challenges
        SET min_trading_days = 10
        WHERE challenge_type = 'PHASE_2'
    """)

    # Add constraint
    op.create_check_constraint(
        'chk_min_trading_days_positive',
        'challenges',
        'min_trading_days >= 0'
    )

    # Add index for queries
    op.create_index(
        'idx_challenges_min_trading_days',
        'challenges',
        ['min_trading_days']
    )

def downgrade():
    # Remove index
    op.drop_index('idx_challenges_min_trading_days')

    # Remove constraint
    op.drop_constraint('chk_min_trading_days_positive', 'challenges')

    # Remove column (CAUTION: Only if no data loss acceptable)
    op.drop_column('challenges', 'min_trading_days')
```

APPLICATION CODE UPDATE:

```python
# Challenge creation - include new field
@dataclass
class CreateChallenge(Command):
    min_trading_days: int = 5

# Challenge aggregate - use in rule evaluation
def _evaluate_min_trading_days_rule(self) -> RiskEvaluationResult:
    trading_days = (self.last_trade_at - self.started_at).days
    if trading_days < self.parameters.min_trading_days:
        return RiskEvaluationResult(
            status=ChallengeStatus.ACTIVE,  # Not a failure, just waiting
            rule_triggered=None
        )
    # Continue with other rules...
```

================================================================================
WHAT CHANGES ARE FORBIDDEN
================================================================================

CRITICAL CONSTRAINTS (Will Fail Audit):

1. DROPPING FINANCIAL TABLES/COLUMNS
   - Never DROP trades, payments, challenge_events tables
   - Never DROP columns with financial data (amounts, timestamps)
   - Forbidden: ALTER TABLE trades DROP COLUMN realized_pnl;

2. MODIFYING IMMUTABLE DATA
   - Never UPDATE existing trades or events
   - Never change historical timestamps
   - Forbidden: UPDATE trades SET realized_pnl = 999 WHERE id = 'xxx';

3. BREAKING EXISTING CONSTRAINTS
   - Never remove uniqueness constraints on financial IDs
   - Never relax NOT NULL on critical audit fields
   - Forbidden: ALTER TABLE challenges ALTER COLUMN initial_balance DROP NOT NULL;

4. CHANGING ENUM VALUES
   - Never modify existing enum values (ACTIVE, FAILED, etc.)
   - Only ADD new enum values
   - Forbidden: UPDATE pg_enum SET enumlabel = 'TERMINATED' WHERE enumlabel = 'FAILED';

5. REMOVING INDEXES CRITICAL FOR AUDIT
   - Never drop unique indexes on financial identifiers
   - Never remove sequence number indexes
   - Forbidden: DROP INDEX idx_trades_challenge_sequence;

================================================================================
ALLOWED CHANGES (With Care)
================================================================================

SAFE MODIFICATIONS:

1. ADDING COLUMNS
   - Always with DEFAULT values
   - Nullable initially, then NOT NULL if appropriate
   - Example: ADD COLUMN risk_score NUMERIC(5,2) DEFAULT 0;

2. ADDING INDEXES
   - For performance optimization
   - Non-unique indexes only
   - Example: CREATE INDEX idx_challenges_performance ON challenges(current_equity, total_trades);

3. ADDING TABLES
   - New feature tables
   - Reference existing tables appropriately
   - Example: New risk_scenarios table

4. MODIFYING DATA TYPES (Carefully)
   - Only increasing precision (VARCHAR length, NUMERIC scale)
   - With comprehensive testing
   - Example: VARCHAR(50) → VARCHAR(100)

5. ADDING ENUM VALUES
   - Only append new values
   - Update application logic accordingly
   - Example: Add 'SUSPENDED' to challenge_status_enum

================================================================================
EMERGENCY ROLLBACK PROCEDURES
================================================================================

WHEN THINGS GO WRONG:

1. IMMEDIATE ACTIONS
   - Stop all application instances
   - Assess data integrity impact
   - Notify compliance and risk teams

2. DATABASE ROLLBACK
   - Use Alembic downgrade if available
   - Point-in-time recovery from backup if needed
   - Validate data consistency post-rollback

3. APPLICATION ROLLBACK
   - Deploy previous application version
   - Feature flags to disable new functionality
   - Monitor for data consistency issues

4. POST-MORTEM
   - Root cause analysis
   - Migration script improvements
   - Update migration runbooks

================================================================================
MIGRATION TESTING CHECKLIST
================================================================================

PRE-DEPLOYMENT:
□ Migration scripts tested on production-sized data
□ Rollback scripts tested and functional
□ Application compatibility verified
□ Performance impact assessed
□ Audit trail continuity confirmed

POST-DEPLOYMENT:
□ Data integrity validation queries pass
□ Business metrics unchanged
□ Performance within acceptable ranges
□ Monitoring alerts configured
□ Rollback procedures documented

This migration strategy ensures that TradeSense AI can evolve its database schema
while maintaining the highest standards of financial audit compliance and data integrity.
*/