-- TradeSense AI Database Initialization
-- ======================================
-- Initialize database, user, enums, and schema

-- Create database user if not exists
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'tradesense_user') THEN
      CREATE ROLE tradesense_user LOGIN PASSWORD 'tradesense_pass';
   END IF;
END
$$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE tradesense TO tradesense_user;

-- Switch to tradesense database context
\c tradesense;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO tradesense_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tradesense_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tradesense_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO tradesense_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO tradesense_user;

-- Create ENUM types first (required before table creation)
CREATE TYPE user_role_enum AS ENUM ('USER', 'ADMIN', 'SUPERADMIN');
CREATE TYPE account_status_enum AS ENUM ('PENDING', 'ACTIVE', 'SUSPENDED', 'CLOSED');
CREATE TYPE challenge_status_enum AS ENUM ('PENDING', 'ACTIVE', 'FAILED', 'FUNDED');
CREATE TYPE trade_side_enum AS ENUM ('BUY', 'SELL');
CREATE TYPE order_type_enum AS ENUM ('MARKET', 'LIMIT', 'STOP_LOSS', 'TAKE_PROFIT', 'TRAILING_STOP', 'OCO');
CREATE TYPE order_status_enum AS ENUM ('PENDING', 'OPEN', 'FILLED', 'CANCELLED', 'EXPIRED', 'REJECTED');
CREATE TYPE order_time_in_force_enum AS ENUM ('GTC', 'IOC', 'FOK', 'DAY');
CREATE TYPE payment_status_enum AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED');
CREATE TYPE payment_provider_enum AS ENUM ('STRIPE', 'PAYPAL', 'BANK_TRANSFER');
CREATE TYPE alert_severity_enum AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE alert_type_enum AS ENUM (
    'HIGH_DRAWDOWN', 'TOTAL_DRAWDOWN_EXCEEDED', 'PROFIT_TARGET_REACHED',
    'INACTIVE_TRADING', 'UNUSUAL_ACTIVITY', 'RISK_SCORE_SPIKE'
);

-- Create tables
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

CREATE TABLE challenges (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Challenge configuration
    initial_balance DECIMAL(20,8) NOT NULL CHECK (initial_balance > 0),
    max_daily_drawdown_percent DECIMAL(5,4) NOT NULL CHECK (max_daily_drawdown_percent > 0 AND max_daily_drawdown_percent <= 1),
    max_total_drawdown_percent DECIMAL(5,4) NOT NULL CHECK (max_total_drawdown_percent > 0 AND max_total_drawdown_percent <= 1),
    profit_target_percent DECIMAL(5,4) NOT NULL CHECK (profit_target_percent > 0 AND profit_target_percent <= 1),

    -- Dynamic equity tracking
    current_equity DECIMAL(20,8) NOT NULL,
    max_equity_ever DECIMAL(20,8) NOT NULL,

    -- Daily reset tracking (UTC midnight resets)
    daily_start_equity DECIMAL(20,8) NOT NULL,
    daily_max_equity DECIMAL(20,8) NOT NULL,
    daily_min_equity DECIMAL(20,8) NOT NULL,
    current_date_value DATE NOT NULL,

    -- Challenge lifecycle
    status challenge_status_enum NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    last_trade_at TIMESTAMPTZ,

    -- Trading statistics
    total_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,4),
    avg_trade_pnl DECIMAL(20,8),

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    rules_config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',

    -- Optimistic locking
    version BIGINT NOT NULL DEFAULT 1
);

CREATE TABLE orders (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),

    -- Order specification
    symbol VARCHAR(20) NOT NULL,
    side trade_side_enum NOT NULL,
    quantity DECIMAL(20,8) NOT NULL CHECK (quantity > 0),
    order_type order_type_enum NOT NULL DEFAULT 'MARKET',

    -- Pricing
    limit_price DECIMAL(20,8),  -- For limit orders
    stop_price DECIMAL(20,8),   -- For stop orders
    take_profit_price DECIMAL(20,8), -- For take profit
    trailing_stop_percent DECIMAL(5,4), -- For trailing stops

    -- Order lifecycle
    status order_status_enum NOT NULL DEFAULT 'PENDING',
    time_in_force order_time_in_force_enum NOT NULL DEFAULT 'GTC',

    -- Linked orders (for OCO, bracket orders)
    parent_order_id UUID REFERENCES orders(id),
    linked_order_id UUID REFERENCES orders(id),

    -- Execution details
    filled_quantity DECIMAL(20,8) DEFAULT 0,
    average_fill_price DECIMAL(20,8),
    remaining_quantity DECIMAL(20,8),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE trades (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    order_id UUID REFERENCES orders(id),

    -- Trade details (immutable)
    symbol VARCHAR(20) NOT NULL,
    side trade_side_enum NOT NULL,
    quantity DECIMAL(20,8) NOT NULL CHECK (quantity > 0),
    price DECIMAL(20,8) NOT NULL CHECK (price > 0),

    -- P&L calculation (stored, not computed)
    realized_pnl DECIMAL(20,8) NOT NULL,

    -- Business vs system timestamps
    executed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Trade metadata
    external_trade_id VARCHAR(255),
    commission DECIMAL(10,8) DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE positions (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),

    -- Position details
    symbol VARCHAR(20) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    average_cost DECIMAL(20,8) NOT NULL,
    current_price DECIMAL(20,8),
    market_value DECIMAL(20,8),

    -- P&L tracking
    unrealized_pnl DECIMAL(20,8) DEFAULT 0,
    realized_pnl DECIMAL(20,8) DEFAULT 0,
    total_pnl DECIMAL(20,8) DEFAULT 0,

    -- Position metadata
    entry_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Constraints
    UNIQUE(challenge_id, symbol)
);

CREATE TABLE challenge_events (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),

    -- Event data (append-only)
    event_type VARCHAR(100) NOT NULL,
    event_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    event_data JSONB NOT NULL,

    -- Human-readable explanation
    description TEXT,
    user_friendly_message TEXT,

    -- Timestamps
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE payments (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    challenge_id UUID REFERENCES challenges(id),

    -- Payment details
    provider payment_provider_enum NOT NULL,
    external_payment_id VARCHAR(255),
    amount DECIMAL(20,8) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',

    -- Payment lifecycle
    status payment_status_enum NOT NULL DEFAULT 'PENDING',
    status_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Processing details
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    failure_reason TEXT,

    -- Refund tracking
    refund_amount DECIMAL(20,8),
    refunded_at TIMESTAMPTZ,

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    provider_response JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE risk_alerts (
    -- Primary identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Alert details
    alert_type alert_type_enum NOT NULL,
    severity alert_severity_enum NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Alert lifecycle
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,

    -- Context data
    alert_data JSONB DEFAULT '{}',
    recommended_actions JSONB DEFAULT '{}',

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    correlation_id VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);

-- Create indexes for performance
CREATE INDEX idx_challenges_user_id ON challenges(user_id);
CREATE INDEX idx_challenges_status ON challenges(status);
CREATE INDEX idx_challenges_created_at ON challenges(created_at);

CREATE INDEX idx_orders_challenge_id ON orders(challenge_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_created_at ON orders(created_at);

CREATE INDEX idx_trades_challenge_id ON trades(challenge_id);
CREATE INDEX idx_trades_order_id ON trades(order_id);
CREATE INDEX idx_trades_executed_at ON trades(executed_at);
CREATE INDEX idx_trades_symbol ON trades(symbol);

CREATE INDEX idx_positions_challenge_id ON positions(challenge_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);

CREATE INDEX idx_challenge_events_challenge_id ON challenge_events(challenge_id);
CREATE INDEX idx_challenge_events_event_type ON challenge_events(event_type);
CREATE INDEX idx_challenge_events_occurred_at ON challenge_events(occurred_at);

CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_challenge_id ON payments(challenge_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at);

CREATE INDEX idx_risk_alerts_challenge_id ON risk_alerts(challenge_id);
CREATE INDEX idx_risk_alerts_user_id ON risk_alerts(user_id);
CREATE INDEX idx_risk_alerts_severity ON risk_alerts(severity);
CREATE INDEX idx_risk_alerts_created_at ON risk_alerts(created_at);

-- Create a default admin user for testing
INSERT INTO users (id, email, password_hash, role, status)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'admin@tradesense.ai',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeA8JcKfjO2qywIK', -- password: admin123
    'SUPERADMIN',
    'ACTIVE'
);