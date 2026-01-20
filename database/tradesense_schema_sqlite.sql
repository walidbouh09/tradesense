-- ============================================================================
-- TradeSense AI - Complete Database Schema (SQLite Compatible)
-- ============================================================================
-- Senior Database Engineer Design
-- Compatible with: SQLite 3.35+
-- Design Principles: Financial Audit Compliance, Event Sourcing, Immutability
-- ============================================================================

-- Enable foreign keys (SQLite specific)
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE 1: USERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    email TEXT NOT NULL,
    
    -- Authentication
    password_hash TEXT NOT NULL,
    
    -- Authorization
    role TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN', 'SUPERADMIN')),
    
    -- Account lifecycle
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED')),
    
    -- Audit timestamps (UTC)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    
    -- Soft delete
    deleted_at TEXT,
    deleted_reason TEXT,
    
    -- Metadata (JSON as TEXT in SQLite)
    metadata TEXT DEFAULT '{}',
    
    -- Optimistic locking
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CHECK (length(password_hash) > 0),
    CHECK (updated_at >= created_at)
);

-- Indexes for users
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_active ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_role_status ON users (role, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status) WHERE deleted_at IS NULL;

-- ============================================================================
-- TABLE 2: CHALLENGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS challenges (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL REFERENCES users(id),
    
    -- Challenge configuration
    challenge_type TEXT NOT NULL,
    initial_balance REAL NOT NULL CHECK (initial_balance > 0),
    max_daily_drawdown_percent REAL NOT NULL CHECK (max_daily_drawdown_percent > 0 AND max_daily_drawdown_percent <= 1),
    max_total_drawdown_percent REAL NOT NULL CHECK (max_total_drawdown_percent > 0 AND max_total_drawdown_percent <= 1),
    profit_target_percent REAL NOT NULL CHECK (profit_target_percent > 0 AND profit_target_percent <= 1),
    
    -- Dynamic equity tracking
    current_equity REAL NOT NULL CHECK (current_equity >= 0),
    max_equity_ever REAL NOT NULL CHECK (max_equity_ever >= initial_balance),
    
    -- Daily tracking
    daily_start_equity REAL NOT NULL CHECK (daily_start_equity >= 0),
    daily_max_equity REAL NOT NULL CHECK (daily_max_equity >= 0),
    daily_min_equity REAL NOT NULL CHECK (daily_min_equity >= 0),
    current_date TEXT NOT NULL DEFAULT (date('now')),
    
    -- Performance tracking
    total_trades INTEGER NOT NULL DEFAULT 0 CHECK (total_trades >= 0),
    total_pnl REAL NOT NULL DEFAULT 0,
    win_rate REAL,
    avg_trade_pnl REAL,
    
    -- Lifecycle status
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED')),
    
    -- Time tracking
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    ended_at TEXT,
    last_trade_at TEXT,
    
    -- Rule violation tracking
    failure_reason TEXT,
    funded_at TEXT,
    
    -- Configuration and metadata
    rules_config TEXT DEFAULT '{}',
    metadata TEXT DEFAULT '{}',
    
    -- Optimistic locking
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CHECK (current_equity <= max_equity_ever),
    CHECK (daily_min_equity <= daily_max_equity),
    CHECK (
        (status IN ('FAILED', 'FUNDED') AND ended_at IS NOT NULL) OR
        (status NOT IN ('FAILED', 'FUNDED') AND ended_at IS NULL)
    ),
    CHECK (
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

-- ============================================================================
-- TABLE 3: TRADES
-- ============================================================================

CREATE TABLE IF NOT EXISTS trades (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    challenge_id TEXT NOT NULL REFERENCES challenges(id),
    
    -- Trade execution details
    trade_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    
    -- Financial impact
    realized_pnl REAL NOT NULL,
    commission REAL NOT NULL DEFAULT 0,
    
    -- Timing
    executed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Sequence tracking
    sequence_number INTEGER NOT NULL,
    
    -- Metadata
    external_trade_id TEXT,
    metadata TEXT DEFAULT '{}',
    
    -- Constraints
    CHECK (created_at >= executed_at),
    UNIQUE (challenge_id, trade_id),
    UNIQUE (challenge_id, sequence_number)
);

-- Indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_challenge_id ON trades (challenge_id);
CREATE INDEX IF NOT EXISTS idx_trades_challenge_executed_at ON trades (challenge_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_challenge_sequence ON trades (challenge_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades (executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_challenge_sequence_lock ON trades (challenge_id, sequence_number);

-- Immutability trigger for trades (SQLite)
CREATE TRIGGER IF NOT EXISTS trg_trades_immutable_update
BEFORE UPDATE ON trades
BEGIN
    SELECT RAISE(ABORT, 'Trades are immutable - cannot update trade');
END;

CREATE TRIGGER IF NOT EXISTS trg_trades_immutable_delete
BEFORE DELETE ON trades
BEGIN
    SELECT RAISE(ABORT, 'Trades are immutable - cannot delete trade');
END;

-- ============================================================================
-- TABLE 4: CHALLENGE_EVENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS challenge_events (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    challenge_id TEXT NOT NULL REFERENCES challenges(id),
    
    -- Event metadata
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT 'v1',
    sequence_number INTEGER NOT NULL,
    
    -- Event payload
    event_data TEXT NOT NULL,
    
    -- Human-readable explanation
    description TEXT NOT NULL,
    user_friendly_message TEXT,
    
    -- Timing
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Event correlation
    correlation_id TEXT,
    causation_id TEXT,
    
    -- Metadata
    metadata TEXT DEFAULT '{}',
    
    -- Constraints
    CHECK (length(trim(event_type)) > 0),
    CHECK (recorded_at >= occurred_at),
    UNIQUE (challenge_id, sequence_number)
);

-- Indexes for challenge_events
CREATE INDEX IF NOT EXISTS idx_challenge_events_challenge_id ON challenge_events (challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_events_challenge_sequence ON challenge_events (challenge_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_challenge_events_type ON challenge_events (event_type);
CREATE INDEX IF NOT EXISTS idx_challenge_events_occurred_at ON challenge_events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_challenge_events_correlation_id ON challenge_events (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_trade_executed ON challenge_events (challenge_id, occurred_at) WHERE event_type = 'TRADE_EXECUTED';
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_challenge_sequence_lock ON challenge_events (challenge_id, sequence_number);

-- Immutability trigger for events (SQLite)
CREATE TRIGGER IF NOT EXISTS trg_events_immutable_update
BEFORE UPDATE ON challenge_events
BEGIN
    SELECT RAISE(ABORT, 'Events are immutable - cannot update event');
END;

CREATE TRIGGER IF NOT EXISTS trg_events_immutable_delete
BEFORE DELETE ON challenge_events
BEGIN
    SELECT RAISE(ABORT, 'Events are immutable - cannot delete event');
END;

-- ============================================================================
-- TABLE 5: PAYMENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS payments (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL REFERENCES users(id),
    challenge_id TEXT REFERENCES challenges(id),
    
    -- Payment provider details
    provider TEXT NOT NULL CHECK (provider IN ('STRIPE', 'PAYPAL', 'BANK_TRANSFER', 'MOCK')),
    provider_payment_id TEXT,
    provider_transaction_id TEXT,
    external_payment_id TEXT,
    
    -- Financial details
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'USD' CHECK (currency IN ('USD', 'EUR', 'GBP')),
    fee REAL NOT NULL DEFAULT 0,
    
    -- Payment lifecycle
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED')),
    status_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Timing
    initiated_at TEXT NOT NULL DEFAULT (datetime('now')),
    processing_started_at TEXT,
    processed_at TEXT,
    completed_at TEXT,
    settled_at TEXT,
    failed_at TEXT,
    
    -- Error handling
    failure_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    
    -- Refund tracking
    refund_amount REAL,
    refunded_at TEXT,
    
    -- Webhook and provider data
    webhook_data TEXT,
    provider_metadata TEXT DEFAULT '{}',
    provider_response TEXT DEFAULT '{}',
    
    -- Audit trail
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Metadata
    metadata TEXT DEFAULT '{}',
    
    -- Constraints
    CHECK (
        (status = 'SUCCESS' AND challenge_id IS NOT NULL) OR
        (status != 'SUCCESS')
    ),
    CHECK (
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

-- ============================================================================
-- TABLE 6: RISK_ALERTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS risk_alerts (
    -- Primary identity
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    challenge_id TEXT REFERENCES challenges(id),
    user_id TEXT REFERENCES users(id),
    
    -- Alert classification
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    
    -- Alert content
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    alert_data TEXT DEFAULT '{}',
    
    -- Alert lifecycle
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_POSITIVE')),
    acknowledged_at TEXT,
    acknowledged_by TEXT REFERENCES users(id),
    resolved_at TEXT,
    resolved_by TEXT REFERENCES users(id),
    
    -- Context data
    recommended_actions TEXT DEFAULT '{}',
    threshold_breached TEXT,
    
    -- Timing
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Correlation
    correlation_id TEXT,
    rule_id TEXT,
    
    -- Metadata
    metadata TEXT DEFAULT '{}',
    
    -- Constraints
    CHECK (
        (status = 'ACKNOWLEDGED' AND acknowledged_at IS NOT NULL) OR
        (status != 'ACKNOWLEDGED')
    ),
    CHECK (
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

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Challenge performance analytics view
CREATE VIEW IF NOT EXISTS challenge_performance_analytics AS
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
    COALESCE(trade_stats.total_volume, 0) as total_volume,
    COALESCE(trade_stats.win_rate, 0) as win_rate,
    COALESCE(trade_stats.avg_trade_size, 0) as avg_trade_size
FROM challenges c
LEFT JOIN (
    SELECT
        challenge_id,
        COUNT(*) as total_volume,
        ROUND(
            CAST(SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS REAL) /
            CAST(COUNT(*) AS REAL) * 100, 2
        ) as win_rate,
        ROUND(AVG(ABS(realized_pnl)), 2) as avg_trade_size
    FROM trades
    WHERE realized_pnl != 0
    GROUP BY challenge_id
) trade_stats ON c.id = trade_stats.challenge_id;

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

-- Users updated_at trigger
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Challenges updated_at trigger
CREATE TRIGGER IF NOT EXISTS trg_challenges_updated_at
AFTER UPDATE ON challenges
BEGIN
    UPDATE challenges SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Payments updated_at trigger
CREATE TRIGGER IF NOT EXISTS trg_payments_updated_at
AFTER UPDATE ON payments
BEGIN
    UPDATE payments SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Risk alerts updated_at trigger
CREATE TRIGGER IF NOT EXISTS trg_risk_alerts_updated_at
AFTER UPDATE ON risk_alerts
BEGIN
    UPDATE risk_alerts SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Insert default admin user
INSERT OR IGNORE INTO users (id, email, password_hash, role, status)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'admin@tradesense.ai',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeA8JcKfjO2qywIK', -- password: admin123
    'SUPERADMIN',
    'ACTIVE'
);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
