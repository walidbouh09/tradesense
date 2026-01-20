# Trading Domain Design - TradeSense AI

## Overview

The Trading domain is responsible for **trade execution recording**, **PnL calculation**, and **position tracking**. It operates as a pure recording and calculation system that **DOES NOT make challenge decisions** but emits events for other domains to consume.

## Core Principles

### 1. Event-Only Architecture
- **No Risk Logic**: Trading domain contains zero risk management or challenge decision logic
- **Event Emission**: All state changes emit domain events for other systems to consume
- **Pure Recording**: Acts as a financial ledger recording what happened, not deciding what should happen

### 2. Financial Accuracy
- **Precise Calculations**: All monetary calculations use `Decimal` for precision
- **Audit Trail**: Complete immutable record of all trades and position changes
- **Commission Tracking**: Accurate commission calculation and tracking

### 3. Domain Separation
- **No Challenge Dependencies**: Trading domain has no knowledge of challenges or rules
- **Event-Driven Integration**: Communicates with other domains only through events
- **Clean Boundaries**: Clear separation between trade execution and risk management

## Domain Model

### Core Entities

#### 1. Trade Aggregate
```python
class Trade(AggregateRoot):
    """Single trade execution record."""
    
    # Identity
    trade_id: TradeId           # Unique trade identifier
    user_id: UUID              # Trader identifier
    
    # Trade Details
    symbol: Symbol             # Trading instrument
    side: OrderSide           # BUY/SELL
    quantity: Quantity        # Trade size
    price: Price              # Execution price
    
    # Financial
    gross_value: Money        # Total trade value
    net_value: Money          # Value after commission
    commission: Commission    # Commission paid
    
    # References
    order_id: UUID            # Source order
    fill: Fill                # Execution fill details
    
    # Classification
    trade_type: TradeType     # OPEN/CLOSE/INCREASE/REDUCE
    executed_at: datetime     # Execution timestamp
```

#### 2. Position Aggregate
```python
class Position(AggregateRoot):
    """Open or closed trading position."""
    
    # Identity
    user_id: UUID             # Position owner
    symbol: Symbol            # Trading instrument
    side: PositionSide       # LONG/SHORT
    
    # Position Details
    quantity: Quantity        # Current position size
    entry_price: Price       # Weighted average entry price
    entry_value: Money       # Total entry value
    current_price: Price     # Current market price
    
    # P&L Tracking
    realized_pnl: Money      # Closed P&L
    unrealized_pnl: Money    # Open P&L
    total_commission: Money  # Total commission paid
    
    # State
    is_open: bool            # Position status
    opened_at: datetime      # Open timestamp
    closed_at: datetime      # Close timestamp (if closed)
    
    # Trade References
    trades: List[UUID]       # All trades in position
    opening_trade_id: UUID   # First trade
    closing_trade_id: UUID   # Final trade (if closed)
```

#### 3. TradingAccount Aggregate
```python
class TradingAccount(AggregateRoot):
    """Overall trading account with P&L summary."""
    
    # Identity
    user_id: UUID            # Account owner
    account_currency: str    # Base currency
    
    # Balance Tracking
    initial_balance: Money   # Starting balance
    current_balance: Money   # Current balance
    
    # P&L Summary
    total_realized_pnl: Money    # All closed P&L
    total_unrealized_pnl: Money  # All open P&L
    daily_pnl: Money            # Today's P&L
    total_commission: Money     # Total commission paid
    
    # Statistics
    total_trades: int           # Trade count
    winning_trades: int         # Profitable trades
    losing_trades: int          # Loss-making trades
    largest_win: Money          # Best trade
    largest_loss: Money         # Worst trade
    trading_days: int           # Active trading days
```

### Value Objects

#### Financial Value Objects
```python
class Quantity(ValueObject):
    """Trade/position quantity with 8 decimal precision."""
    value: Decimal  # Precise quantity

class Price(ValueObject):
    """Market price wrapper around Money."""
    value: Money    # Price with currency

class Commission(ValueObject):
    """Commission structure and amount."""
    amount: Money           # Commission paid
    rate: Decimal          # Commission rate (if applicable)
    commission_type: str   # FIXED/PERCENTAGE/TIERED

class PnL(ValueObject):
    """Profit and Loss calculation."""
    amount: Money          # P&L amount
    pnl_type: PnLType     # REALIZED/UNREALIZED
    currency: str         # Currency
    percentage: Decimal   # P&L percentage (optional)
```

#### Trade Classification
```python
class TradeType(Enum):
    OPEN = "OPEN"         # Opens new position
    CLOSE = "CLOSE"       # Closes existing position
    INCREASE = "INCREASE" # Increases position size
    REDUCE = "REDUCE"     # Reduces position size

class PositionSide(Enum):
    LONG = "LONG"         # Long position (buy low, sell high)
    SHORT = "SHORT"       # Short position (sell high, buy low)

class PnLType(Enum):
    REALIZED = "REALIZED"     # Closed position P&L
    UNREALIZED = "UNREALIZED" # Open position P&L
```

## Trade Execution Flow

### 1. Order Fill → Trade Creation

```
Order Execution (External) → Fill Data → Trade Creation

1. External system executes order
2. Fill data received (quantity, price, commission)
3. Trade entity created with execution details
4. TradeExecuted event emitted
```

### 2. Trade → Position Management

```
Trade Creation → Position Determination → Position Update/Creation

1. Determine trade type (OPEN/CLOSE/INCREASE/REDUCE)
2. Find existing position for symbol (if any)
3. Create new position OR update existing position
4. Calculate P&L changes
5. Emit PositionOpened/PositionUpdated/PositionClosed events
```

### 3. Position → Account Updates

```
Position Changes → Account P&L Update → Daily Calculations

1. Position P&L changes trigger account updates
2. Aggregate all position P&L for account totals
3. Update trading statistics (win/loss counts, etc.)
4. Calculate daily P&L snapshots
5. Emit DailyPnLCalculated events
```

## Event Emission Strategy

### Trade Events
```python
# Emitted when trade is executed
TradeExecuted(
    trade_id: str,
    user_id: UUID,
    symbol: str,
    side: str,
    quantity: str,
    price: str,
    gross_value: str,
    net_value: str,
    commission: str,
    trade_type: str,
    executed_at: str,
)
```

### Position Events
```python
# Emitted when new position opened
PositionOpened(
    user_id: UUID,
    symbol: str,
    side: str,
    quantity: str,
    entry_price: str,
    entry_value: str,
    opening_trade_id: UUID,
)

# Emitted when position closed
PositionClosed(
    user_id: UUID,
    symbol: str,
    side: str,
    quantity: str,
    entry_price: str,
    exit_price: str,
    realized_pnl: str,
    total_commission: str,
    duration_seconds: int,
)

# Emitted when position size changes
PositionUpdated(
    user_id: UUID,
    symbol: str,
    trade_type: str,
    new_quantity: str,
    new_entry_price: str,
    realized_pnl: str,
)
```

### P&L Events
```python
# Emitted when P&L calculated
PnLCalculated(
    user_id: UUID,
    symbol: str,
    position_side: str,
    unrealized_pnl: str,
    realized_pnl: str,
    total_pnl: str,
)

# Emitted daily for account summary
DailyPnLCalculated(
    user_id: UUID,
    date: str,
    daily_pnl: str,
    total_realized_pnl: str,
    total_unrealized_pnl: str,
    current_balance: str,
    total_trades: int,
    trading_days: int,
)
```

## API Endpoints

### Trade Execution
```http
POST /trading/trades/execute
{
  "trade_id": "TRADE_001",
  "user_id": "uuid",
  "symbol": "EURUSD",
  "side": "BUY",
  "quantity": "10000",
  "price": "1.0850",
  "order_id": "uuid",
  "fill_id": "FILL_001",
  "commission": "5.00"
}
```

### Trade History
```http
GET /trading/trades?user_id=uuid&symbol=EURUSD&limit=100
```

### Position Management
```http
GET /trading/positions?user_id=uuid&include_closed=false

POST /trading/positions/{position_id}/close
{
  "price": "1.0900",
  "quantity": "5000",  // Optional for partial close
  "reason": "Manual close"
}
```

### Price Updates & P&L
```http
POST /trading/positions/update-prices
{
  "price_updates": [
    {"symbol": "EURUSD", "price": "1.0875"},
    {"symbol": "GBPUSD", "price": "1.2650"}
  ]
}
```

### Account & Metrics
```http
GET /trading/account?user_id=uuid
GET /trading/metrics?user_id=uuid&start_date=2024-01-01
GET /trading/daily-pnl?user_id=uuid&limit=30
```

## P&L Calculation Logic

### Position P&L Calculation

#### Long Position P&L
```python
# Unrealized P&L for long position
unrealized_pnl = (current_price - entry_price) * quantity - total_commission

# Realized P&L when closing long position
realized_pnl = (exit_price - entry_price) * quantity - total_commission
```

#### Short Position P&L
```python
# Unrealized P&L for short position
unrealized_pnl = (entry_price - current_price) * quantity - total_commission

# Realized P&L when closing short position
realized_pnl = (entry_price - exit_price) * quantity - total_commission
```

### Weighted Average Entry Price
```python
# When adding to existing position
new_entry_price = (
    (old_quantity * old_entry_price) + (new_quantity * new_price)
) / (old_quantity + new_quantity)
```

### Daily P&L Calculation
```python
# Daily P&L = Change in total P&L from previous day
daily_pnl = today_total_pnl - yesterday_total_pnl

# Where total_pnl = realized_pnl + unrealized_pnl
```

## Integration with Other Domains

### Challenge Engine Integration
```python
# Trading domain emits events, Challenge engine consumes

@event_handler(TradeExecuted)
async def handle_trade_executed(event: TradeExecuted):
    """Challenge engine updates trading metrics."""
    challenge = find_active_challenge(event.user_id)
    if challenge:
        challenge.update_trading_metrics(
            new_balance=calculate_new_balance(event),
            daily_pnl=calculate_daily_pnl(event),
            trade_count=1,
        )

@event_handler(DailyPnLCalculated)
async def handle_daily_pnl(event: DailyPnLCalculated):
    """Challenge engine evaluates rules."""
    challenge = find_active_challenge(event.user_id)
    if challenge:
        # Trigger rules evaluation with new P&L data
        await evaluate_challenge_rules(challenge, event)
```

### Rules Engine Integration
```python
# Trading events provide context for rule evaluation

@event_handler(PositionClosed)
async def handle_position_closed(event: PositionClosed):
    """Rules engine evaluates completion rules."""
    context = build_rule_context(event)
    rule_engine = get_rule_engine(event.user_id)
    await rule_engine.evaluate_rules(context)
```

## Database Schema

### Core Tables
```sql
-- Trades table
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    gross_value DECIMAL(20,8) NOT NULL,
    net_value DECIMAL(20,8) NOT NULL,
    commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    order_id UUID NOT NULL,
    fill_id VARCHAR(100) NOT NULL,
    trade_type VARCHAR(20) NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Positions table
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    entry_price DECIMAL(20,8) NOT NULL,
    entry_value DECIMAL(20,8) NOT NULL,
    current_price DECIMAL(20,8),
    realized_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    opening_trade_id UUID NOT NULL,
    closing_trade_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Trading accounts table
CREATE TABLE trading_accounts (
    id UUID PRIMARY KEY,
    user_id UUID UNIQUE NOT NULL,
    account_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    initial_balance DECIMAL(20,8) NOT NULL DEFAULT 0,
    current_balance DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_realized_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_unrealized_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    daily_pnl DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_commission DECIMAL(20,8) NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    largest_win DECIMAL(20,8) NOT NULL DEFAULT 0,
    largest_loss DECIMAL(20,8) NOT NULL DEFAULT 0,
    trading_days INTEGER NOT NULL DEFAULT 0,
    last_daily_calculation TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily P&L snapshots
CREATE TABLE daily_pnl (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    trading_account_id UUID NOT NULL REFERENCES trading_accounts(id),
    date TIMESTAMP NOT NULL,
    daily_pnl DECIMAL(20,8) NOT NULL,
    total_realized_pnl DECIMAL(20,8) NOT NULL,
    total_unrealized_pnl DECIMAL(20,8) NOT NULL,
    total_pnl DECIMAL(20,8) NOT NULL,
    current_balance DECIMAL(20,8) NOT NULL,
    daily_trades INTEGER NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    trading_days INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Indexes
```sql
-- Performance indexes
CREATE INDEX idx_trades_user_symbol ON trades(user_id, symbol);
CREATE INDEX idx_trades_executed_at ON trades(executed_at);
CREATE INDEX idx_positions_user_open ON positions(user_id, is_open);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_daily_pnl_user_date ON daily_pnl(user_id, date);
```

## Testing Strategy

### Unit Tests
- Value object validation and calculations
- Entity business logic and state transitions
- P&L calculation accuracy
- Event emission verification

### Integration Tests
- Trade execution flow end-to-end
- Position management with multiple trades
- P&L calculation with price updates
- Database persistence and retrieval

### Performance Tests
- High-frequency trade processing
- Bulk position price updates
- Large-scale P&L calculations
- Database query performance

## Compliance & Audit

### Audit Trail
- **Immutable Records**: All trades and position changes are immutable
- **Complete History**: Full audit trail of all financial transactions
- **Event Sourcing**: All state changes captured as domain events
- **Timestamp Precision**: Microsecond-level timestamps for all operations

### Financial Accuracy
- **Decimal Precision**: All monetary calculations use `Decimal` type
- **Commission Tracking**: Accurate commission calculation and recording
- **Currency Handling**: Proper multi-currency support
- **Rounding Rules**: Consistent rounding rules for all calculations

### Regulatory Compliance
- **MiFID II**: Trade reporting and best execution records
- **CFTC**: Swap data reporting for applicable instruments
- **GDPR**: Personal data handling in trading records
- **SOX**: Financial reporting accuracy and controls

## Performance Considerations

### Optimization Strategies
- **Batch Processing**: Bulk trade processing for high-frequency scenarios
- **Caching**: Position and account data caching for frequent reads
- **Indexing**: Optimized database indexes for common queries
- **Async Processing**: Non-blocking event processing

### Scalability
- **Horizontal Scaling**: Stateless services for easy scaling
- **Database Sharding**: User-based sharding for large datasets
- **Event Streaming**: Kafka/Redis for high-throughput event processing
- **Read Replicas**: Separate read/write database instances

## Summary

The Trading domain provides a **pure financial ledger** that:

1. **Records** all trade executions with complete accuracy
2. **Calculates** P&L for positions and accounts in real-time
3. **Tracks** position lifecycle from open to close
4. **Emits** events for other domains to consume
5. **Maintains** complete audit trail for compliance

**Key Principle**: The Trading domain **NEVER** makes business decisions about challenges, risk, or trading permissions. It purely records what happened and calculates the financial impact, leaving all business logic to other domains that consume its events.

This separation ensures clean domain boundaries, testability, and regulatory compliance while providing accurate financial data to the rest of the system.