-- ============================================================================
-- TradeSense AI - Complete Database Schema
-- ============================================================================
-- Senior Database Engineer Design
-- Compatible with: PostgreSQL 14+ and SQLite 3.35+
-- Design Principles: Financial Audit Compliance, Event Sourcing, Immutability
-- ============================================================================

-- ============================================================================
-- ENUMS (PostgreSQL) / Check Constraints (SQLite)
-- ============================================================================

-- User roles and account status
DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('USER', 'ADMIN', 'SUPERADMIN');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE account_status_enum AS ENUM ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Challenge lifecycle states
DO $$ BEGIN
    CREATE TYPE challenge_status_enum AS ENUM ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Trading enums
DO $$ BEGIN
    CREATE TYPE trade_side_enum AS ENUM ('BUY', 'SELL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Payment enums
DO $$ BEGIN
    CREATE TYPE payment_provider_enum AS ENUM ('STRIPE', 'PAYPAL', 'BANK_TRANSFER', 'MOCK');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_status_enum AS ENUM ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Risk alert enums
DO $$ BEGIN
    CREATE TYPE alert_severity_enum AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE alert_status_enum AS ENUM ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE risk_level_enum AS ENUM ('STABLE', 'MONITOR', 'HIGH_RISK', 'CRITICAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- TABLE 1: USERS
-- ============================================================================
-- User accounts with role-based access control
-- Security: Only password hashes stored, soft delete for compliance
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    
    -- Authentication
    password_hash VARCHAR(255) NOT NULL,
    
    -- Authorization
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    
    -- Account lifecycle
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    
    -- Audit timestamps (UTC)
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ,
    
    -- Soft delete (never hard delete financial data)
    deleted_at TIMESTAMPTZ,
    deleted_reason VARCHAR(500),
    
    -- Metadata for future expansion (KYC, preferences)
    metadata JSONB DEFAULT '{}',
    
    -- Optimistic locking
    version BIGINT NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT chk_users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_users_password_not_empty CHECK (length(password_hash) > 0),
    CONSTRAINT chk_users_role CHECK (role IN ('USER', 'ADMIN', 'SUPERADMIN')),
    CONSTRAINT chk_users_status CHECK (status IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED')),
    CONSTRAINT chk_users_updated_after_created CHECK (updated_at >= created_at)
);

-- Indexes for users
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_active ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users (role, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status) WHERE deleted_at IS NULL;

-- Comments
COMMENT ON TABLE users IS 'User accounts with RBAC - audit-ready with lifecycle tracking';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt/scrypt hash only - never plaintext passwords';
COMMENT ON COLUMN users.metadata IS 'JSONB for KYC data, preferences - encrypted at app layer';
COMMENT ON COLUMN users.deleted_at IS 'Soft delete timestamp - maintains audit trail';

-- ============================================================================
-- TABLE 2: CHALLENGES
-- ============================================================================
-- Prop firm challenge accounts with real-time equity tracking
-- Core financial state for drawdown rules and decision logic
-- ============================================================================

CREATE TABLE IF NOT EXISTS challenges (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Challenge configuration (immutable after creation)
    challenge_type VARCHAR(50) NOT NULL,
    initial_balance NUMERIC(20,8) NOT NULL CHECK (initial_balance > 0),
    max_daily_drawdown_percent NUMERIC(5,4) NOT NULL CHECK (max_daily_drawdown_percent > 0 AND max_daily_drawdown_percent <= 1),
    max_total_drawdown_percent NUMERIC(5,4) NOT NULL CHECK (max_total_drawdown_percent > 0 AND max_total_drawdown_percent <= 1),
    profit_target_percent NUMERIC(5,4) NOT NULL CHECK (profit_target_percent > 0 AND profit_target_percent <= 1),
    
    -- Dynamic equity tracking (critical for rule evaluation)
    current_equity NUMERIC(20,8) NOT NULL CHECK (current_equity >= 0),
    max_equity_ever NUMERIC(20,8) NOT NULL CHECK (max_equity_ever >= initial_balance),
    
    -- Daily tracking (resets at UTC midnight)
    daily_start_equity NUMERIC(20,8) NOT NULL CHECK (daily_start_equity >= 0),
    daily_max_equity NUMERIC(20,8) NOT NULL CHECK (daily_max_equity >= 0),
    daily_min_equity NUMERIC(20,8) NOT NULL CHECK (daily_min_equity >= 0),
    current_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Performance tracking
    total_trades INTEGER NOT NULL DEFAULT 0 CHECK (total_trades >= 0),
    total_pnl NUMERIC(20,8) NOT NULL DEFAULT 0,
    win_rate NUMERIC(5,4),
    avg_trade_pnl NUMERIC(20,8),
    
    -- Lifecycle status (state machine)
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    
    -- Time tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    last_trade_at TIMESTAMPTZ,
    
    -- Rule violation tracking
    failure_reason VARCHAR(100),
    funded_at TIMESTAMPTZ,
    
    -- Configuration and metadata
    rules_config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Optimistic locking
    version BIGINT NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT chk_challenges_status CHECK (status IN ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED')),
    CONSTRAINT chk_challenges_equity_consistency CHECK (current_equity <= max_equity_ever),
    CONSTRAINT chk_challenges_daily_equity_bounds CHECK (daily_min_equity <= daily_max_equity),
    CONSTRAINT chk_challenges_terminal_states CHECK (
        (status IN ('FAILED', 'FUNDED') AND ended_at IS NOT NULL) OR
        (status NOT IN ('FAILED', 'FUNDED') AND ended_at IS NULL)
    ),
    CONSTRAINT chk_challenges_funded_timestamp CHECK (
        (status = 'FUNDED' AND funded_at IS NOT NULL) OR
        (status != 'FUNDED' AND funded_at IS NULL)
    )
);

-- Indexes for challenges
CREATE INDEX IF NOT EXISTS idx_challenges_user_id ON challenges (user_id);
CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges (status);
CREATE INDEX IF NOT EXISTS idx_challenges_user_status ON challenges (user_id, status);
CREATE INDEX IF NOT EXISTS idx_challenges_created_at ON challenges (created_at);
CREATE INDEX IF NOT EXISTS idx_challenges_current_date ON challenges (current_date);
CREATE INDEX IF NOT EXISTS idx_challenges_last_trade_at ON challenges (last_trade_at) WHERE last_trade_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_challenges_active_equity ON challenges (current_equity) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX IF NOT EXISTS idx_challenges_id_version ON challenges (id, version);

-- Comments
COMMENT ON TABLE challenges IS 'Prop firm challenge accounts - core financial state for rule evaluation';
COMMENT ON COLUMN challenges.current_equity IS 'Current account equity - never goes below zero';
COMMENT ON COLUMN challenges.max_equity_ever IS 'All-time high water mark for total drawdown calculation';
COMMENT ON COLUMN challenges.daily_start_equity IS 'Equity at start of current trading day (resets daily)';

-- ============================================================================
-- TABLE 3: TRADES
-- ============================================================================
-- Immutable trade ledger - append-only for financial audit compliance
-- NO UPDATE, NO DELETE - each row is historical truth
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    
    -- Trade execution details
    trade_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity NUMERIC(20,8) NOT NULL CHECK (quantity > 0),
    price NUMERIC(20,8) NOT NULL CHECK (price > 0),
    
    -- Financial impact (stored explicitly)
    realized_pnl NUMERIC(20,8) NOT NULL,
    commission NUMERIC(10,8) NOT NULL DEFAULT 0,
    
    -- Timing (business vs system time)
    executed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Sequence tracking
    sequence_number BIGINT NOT NULL,
    
    -- Metadata
    external_trade_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_trades_side CHECK (side IN ('BUY', 'SELL')),
    CONSTRAINT chk_trades_executed_not_future CHECK (executed_at <= CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    CONSTRAINT chk_trades_created_after_executed CHECK (created_at >= executed_at),
    CONSTRAINT uk_trades_challenge_trade_id UNIQUE (challenge_id, trade_id),
    CONSTRAINT uk_trades_challenge_sequence UNIQUE (challenge_id, sequence_number)
);

-- Indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_challenge_id ON trades (challenge_id);
CREATE INDEX IF NOT EXISTS idx_trades_challenge_executed_at ON trades (challenge_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_challenge_sequence ON trades (challenge_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades (executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_recent ON trades (executed_at) WHERE executed_at > CURRENT_TIMESTAMP - INTERVAL '30 days';
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_challenge_sequence_lock ON trades (challenge_id, sequence_number);

-- Comments
COMMENT ON TABLE trades IS 'Immutable trade ledger - append-only for financial audit compliance';
COMMENT ON COLUMN trades.realized_pnl IS 'Profit/loss explicitly stored - not recalculated';
COMMENT ON COLUMN trades.executed_at IS 'Business time (when trade occurred in market)';
COMMENT ON COLUMN trades.sequence_number IS 'Monotonic sequence per challenge for ordering';

-- Immutability trigger (PostgreSQL)
CREATE OR REPLACE FUNCTION prevent_trade_updates()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Trades are immutable - cannot update trade %', OLD.id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Trades are immutable - cannot delete trade %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trades_immutable ON trades;
CREATE TRIGGER trg_trades_immutable
    BEFORE UPDATE OR DELETE ON trades
    FOR EACH ROW EXECUTE FUNCTION prevent_trade_updates();

-- ============================================================================
-- TABLE 4: CHALLENGE_EVENTS
-- ============================================================================
-- Event-sourced audit log - append-only, replayable for dispute resolution
-- Complete business event history for reconstruction
-- ============================================================================

CREATE TABLE IF NOT EXISTS challenge_events (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    
    -- Event metadata
    event_type VARCHAR(100) NOT NULL,
    event_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    sequence_number BIGINT NOT NULL,
    
    -- Event payload
    event_data JSONB NOT NULL,
    
    -- Human-readable explanation
    description TEXT NOT NULL,
    user_friendly_message TEXT,
    
    -- Timing
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Event correlation
    correlation_id UUID,
    causation_id UUID,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_events_type_not_empty CHECK (length(trim(event_type)) > 0),
    CONSTRAINT chk_events_recorded_after_occurred CHECK (recorded_at >= occurred_at),
    CONSTRAINT uk_challenge_events_sequence UNIQUE (challenge_id, sequence_number)
);

-- Indexes for challenge_events
CREATE INDEX IF NOT EXISTS idx_challenge_events_challenge_id ON challenge_events (challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_events_challenge_sequence ON challenge_events (challenge_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_challenge_events_type ON challenge_events (event_type);
CREATE INDEX IF NOT EXISTS idx_challenge_events_occurred_at ON challenge_events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_challenge_events_correlation_id ON challenge_events (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_trade_executed ON challenge_events (challenge_id, occurred_at) WHERE event_type = 'TRADE_EXECUTED';
CREATE INDEX IF NOT EXISTS idx_challenge_events_data_gin ON challenge_events USING GIN (event_data);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_challenge_sequence_lock ON challenge_events (challenge_id, sequence_number);

-- Comments
COMMENT ON TABLE challenge_events IS 'Event-sourced audit log - append-only, replayable for dispute resolution';
COMMENT ON COLUMN challenge_events.event_data IS 'Complete structured event payload (JSONB)';
COMMENT ON COLUMN challenge_events.description IS 'Human-readable explanation for audit reports';

-- Immutability trigger (PostgreSQL)
CREATE OR REPLACE FUNCTION prevent_event_modifications()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Events are immutable - cannot update event %', OLD.id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Events are immutable - cannot delete event %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_challenge_events_immutable ON challenge_events;
CREATE TRIGGER trg_challenge_events_immutable
    BEFORE UPDATE OR DELETE ON challenge_events
    FOR EACH ROW EXECUTE FUNCTION prevent_event_modifications();

-- ============================================================================
-- TABLE 5: PAYMENTS
-- ============================================================================
-- Payment processing for challenge purchases
-- Supports multiple providers, idempotent operations
-- ============================================================================

CREATE TABLE IF NOT EXISTS payments (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    challenge_id UUID REFERENCES challenges(id),
    
    -- Payment provider details
    provider VARCHAR(30) NOT NULL,
    provider_payment_id VARCHAR(255),
    provider_transaction_id VARCHAR(255),
    external_payment_id VARCHAR(255),
    
    -- Financial details
    amount NUMERIC(20,8) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    fee NUMERIC(10,8) NOT NULL DEFAULT 0,
    
    -- Payment lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    status_updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Timing
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    
    -- Error handling
    failure_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    
    -- Refund tracking
    refund_amount NUMERIC(20,8),
    refunded_at TIMESTAMPTZ,
    
    -- Webhook and provider data
    webhook_data JSONB,
    provider_metadata JSONB DEFAULT '{}',
    provider_response JSONB DEFAULT '{}',
    
    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_payments_provider CHECK (provider IN ('STRIPE', 'PAYPAL', 'BANK_TRANSFER', 'MOCK')),
    CONSTRAINT chk_payments_status CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED')),
    CONSTRAINT chk_payments_currency CHECK (currency IN ('USD', 'EUR', 'GBP')),
    CONSTRAINT chk_payments_success_has_challenge CHECK (
        (status = 'SUCCESS' AND challenge_id IS NOT NULL) OR
        (status != 'SUCCESS')
    ),
    CONSTRAINT chk_payments_processed_timestamp CHECK (
        (status IN ('SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED') AND processed_at IS NOT NULL) OR
        (status NOT IN ('SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED'))
    )
);

-- Indexes for payments
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments (user_id);
CREATE INDEX IF NOT EXISTS idx_payments_challenge_id ON payments (challenge_id) WHERE challenge_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_provider_payment_id ON payments (provider_payment_id) WHERE provider_payment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
CREATE INDEX IF NOT EXISTS idx_payments_provider_status ON payments (provider, status);
CREATE INDEX IF NOT EXISTS idx_payments_initiated_at ON payments (initiated_at);
CREATE INDEX IF NOT EXISTS idx_payments_pending_webhooks ON payments (provider, updated_at) WHERE status IN ('PENDING', 'PROCESSING');
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_provider_lock ON payments (provider, provider_payment_id) WHERE provider_payment_id IS NOT NULL;

-- Comments
COMMENT ON TABLE payments IS 'Payment processing - decoupled from challenge lifecycle';
COMMENT ON COLUMN payments.provider_payment_id IS 'External payment ID for idempotency';
COMMENT ON COLUMN payments.webhook_data IS 'Raw webhook payload for audit';

-- ============================================================================
-- TABLE 6: RISK_ALERTS
-- ============================================================================
-- Risk monitoring and alerting system
-- Stores warnings from Risk Engine - NOT part of core decision logic
-- ============================================================================

CREATE TABLE IF NOT EXISTS risk_alerts (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID REFERENCES challenges(id),
    user_id UUID REFERENCES users(id),
    
    -- Alert classification
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    
    -- Alert content
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    alert_data JSONB DEFAULT '{}',
    
    -- Alert lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    
    -- Context data
    recommended_actions JSONB DEFAULT '{}',
    threshold_breached JSONB,
    
    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Correlation
    correlation_id UUID,
    rule_id VARCHAR(100),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT chk_alerts_severity CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT chk_alerts_status CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE')),
    CONSTRAINT chk_alerts_acknowledged_status CHECK (
        (status = 'ACKNOWLEDGED' AND acknowledged_at IS NOT NULL) OR
        (status != 'ACKNOWLEDGED')
    ),
    CONSTRAINT chk_alerts_resolved_status CHECK (
        (status IN ('RESOLVED', 'FALSE_POSITIVE') AND resolved_at IS NOT NULL) OR
        (status NOT IN ('RESOLVED', 'FALSE_POSITIVE'))
    )
);

-- Indexes for risk_alerts
CREATE INDEX IF NOT EXISTS idx_risk_alerts_challenge_id ON risk_alerts (challenge_id) WHERE challenge_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_alerts_user_id ON risk_alerts (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_alerts_type_severity ON risk_alerts (alert_type, severity);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_status ON risk_alerts (status);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_created_at ON risk_alerts (created_at);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_correlation_id ON risk_alerts (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_risk_alerts_active ON risk_alerts (severity, created_at) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_risk_alerts_severity ON risk_alerts (severity);

-- Comments
COMMENT ON TABLE risk_alerts IS 'Risk monitoring alerts - separate from core decision logic';
COMMENT ON COLUMN risk_alerts.alert_data IS 'Structured data with metrics and threshold details';

-- ============================================================================
-- VIEWS AND MATERIALIZED VIEWS
-- ============================================================================

-- Challenge performance analytics view
CREATE OR REPLACE VIEW challenge_performance_analytics AS
SELECT
    c.id,
    c.user_id,
    c.challenge_type,
    c.status,
    c.initial_balance,
    c.current_equity,
    c.max_equity_ever,
    ROUND(((c.current_equity - c.initial_balance) / c.initial_balance) * 100, 2) as profit_percentage,
    ROUND(((c.max_equity_ever - c.current_equity) / c.max_equity_ever) * 100, 2) as drawdown_percentage,
    c.total_trades,
    c.total_pnl,
    c.daily_start_equity,
    c.daily_max_equity,
    c.daily_min_equity,
    ROUND(((c.daily_start_equity - c.daily_min_equity) / c.daily_start_equity) * 100, 2) as daily_drawdown_used,
    c.started_at,
    c.ended_at,
    c.last_trade_at,
    EXTRACT(EPOCH FROM (c.last_trade_at - c.started_at))/3600 as trading_hours,
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

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_challenges_updated_at ON challenges;
CREATE TRIGGER trg_challenges_updated_at
    BEFORE UPDATE ON challenges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_payments_updated_at ON payments;
CREATE TRIGGER trg_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_risk_alerts_updated_at ON risk_alerts;
CREATE TRIGGER trg_risk_alerts_updated_at
    BEFORE UPDATE ON risk_alerts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Insert default admin user
INSERT INTO users (id, email, password_hash, role, status)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'admin@tradesense.ai',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeA8JcKfjO2qywIK', -- password: admin123
    'SUPERADMIN',
    'ACTIVE'
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- SCHEMA VALIDATION QUERIES
-- ============================================================================

-- Verify all tables exist
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('users', 'challenges', 'trades', 'challenge_events', 'payments', 'risk_alerts');
    
    IF table_count = 6 THEN
        RAISE NOTICE 'Schema validation: All 6 core tables created successfully';
    ELSE
        RAISE WARNING 'Schema validation: Expected 6 tables, found %', table_count;
    END IF;
END $$;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
