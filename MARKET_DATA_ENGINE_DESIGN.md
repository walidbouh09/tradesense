# TradeSense AI Market Data Engine Design

## Overview

The Market Data Engine provides unified access to real-time and historical market data from multiple providers across US and Moroccan markets. It features provider abstraction, intelligent aggregation, multi-layer caching, and comprehensive rate limiting.

## Architecture Principles

- **Provider Agnostic**: Unified interface for multiple data providers
- **Multi-Market Support**: US (NYSE, NASDAQ) and Morocco (Casablanca Stock Exchange)
- **Dual Protocol**: REST for historical data, WebSocket for real-time feeds
- **Intelligent Caching**: Multi-layer caching with TTL and invalidation strategies
- **Rate Limiting**: Provider-specific and global rate limiting
- **Fault Tolerance**: Failover, circuit breakers, and graceful degradation

## Market Coverage

### US Markets
- **NYSE**: New York Stock Exchange
- **NASDAQ**: NASDAQ Global Market
- **AMEX**: American Stock Exchange
- **OTC**: Over-the-Counter markets

### Moroccan Markets
- **CSE**: Casablanca Stock Exchange (Bourse de Casablanca)
- **MAD**: Moroccan Dirham currency pairs
- **MASI**: Moroccan All Shares Index

## Data Types

### Real-Time Data (WebSocket)
- **Level 1**: Best bid/ask, last trade, volume
- **Level 2**: Full order book depth
- **Trades**: Individual trade executions
- **Market Status**: Open/closed, trading halts
- **News**: Market-moving news and announcements

### Historical Data (REST)
- **OHLCV**: Open, High, Low, Close, Volume bars
- **Tick Data**: Individual price movements
- **Corporate Actions**: Splits, dividends, mergers
- **Fundamentals**: Financial statements, ratios
- **Economic Indicators**: GDP, inflation, employment

## Provider Ecosystem

### Tier 1 Providers (Premium)
- **Bloomberg Terminal API**: Comprehensive global data
- **Refinitiv Eikon**: Real-time and historical data
- **Interactive Brokers**: Direct market access
- **Alpha Vantage**: US market data with global coverage

### Tier 2 Providers (Standard)
- **Yahoo Finance**: Free historical and basic real-time
- **Quandl**: Economic and financial data
- **IEX Cloud**: US market data
- **Twelve Data**: Multi-market coverage

### Regional Providers
- **Casablanca Stock Exchange API**: Direct CSE data
- **Bank Al-Maghrib**: Moroccan central bank data
- **Moroccan Ministry of Economy**: Economic indicators

## Aggregation Strategy

### Data Prioritization
1. **Primary Source**: Highest quality, lowest latency
2. **Secondary Source**: Backup with slight delay tolerance
3. **Tertiary Source**: Fallback for basic data needs

### Conflict Resolution
- **Price Conflicts**: Use most recent timestamp
- **Volume Conflicts**: Sum from all sources
- **Corporate Actions**: Prefer official exchange data
- **News**: Aggregate from multiple sources with deduplication

### Quality Scoring
```
Quality Score = (Latency Weight × Latency Score) + 
                (Accuracy Weight × Accuracy Score) + 
                (Completeness Weight × Completeness Score)
```

## Caching Architecture

### Layer 1: In-Memory Cache (Redis)
- **TTL**: 1-60 seconds for real-time data
- **Capacity**: 10GB RAM allocation
- **Eviction**: LRU with priority weighting
- **Use Case**: Ultra-low latency access

### Layer 2: Distributed Cache (Redis Cluster)
- **TTL**: 1-60 minutes for historical data
- **Capacity**: 100GB distributed storage
- **Partitioning**: By symbol and time range
- **Use Case**: Frequently accessed historical data

### Layer 3: Persistent Cache (Database)
- **TTL**: 24 hours to permanent
- **Storage**: PostgreSQL with time-series optimization
- **Indexing**: Symbol, timestamp, provider
- **Use Case**: Long-term historical data

### Cache Invalidation
- **Time-Based**: Automatic TTL expiration
- **Event-Based**: Corporate actions, market events
- **Manual**: Administrative cache clearing
- **Cascade**: Dependent data invalidation

## Rate Limiting Strategy

### Provider-Level Limits
```python
PROVIDER_LIMITS = {
    "bloomberg": {"requests_per_second": 100, "burst": 200},
    "alpha_vantage": {"requests_per_minute": 5, "daily": 500},
    "yahoo_finance": {"requests_per_hour": 2000, "burst": 100},
    "cse_api": {"requests_per_second": 10, "daily": 10000},
}
```

### Global Rate Limiting
- **Per Client**: 1000 requests/minute
- **Per Symbol**: 100 requests/minute
- **Per Market**: 5000 requests/minute
- **Burst Allowance**: 2x normal rate for 30 seconds

### Rate Limiting Algorithms
- **Token Bucket**: For burst handling
- **Sliding Window**: For precise rate control
- **Leaky Bucket**: For smooth traffic shaping

## API Design

### REST API Endpoints

#### Historical Data
```
GET /api/v1/market-data/historical/{symbol}
GET /api/v1/market-data/ohlcv/{symbol}
GET /api/v1/market-data/fundamentals/{symbol}
GET /api/v1/market-data/corporate-actions/{symbol}
```

#### Market Information
```
GET /api/v1/markets/{market}/status
GET /api/v1/markets/{market}/symbols
GET /api/v1/markets/{market}/holidays
```

#### Data Quality & Metadata
```
GET /api/v1/providers/status
GET /api/v1/data-quality/report
GET /api/v1/cache/statistics
```

### WebSocket API

#### Subscription Management
```json
{
  "action": "subscribe",
  "channel": "level1",
  "symbols": ["AAPL", "ATW.CSE"],
  "markets": ["NYSE", "CSE"]
}
```

#### Real-Time Data Streams
- **level1**: Best bid/ask and last trade
- **level2**: Full order book
- **trades**: Individual executions
- **news**: Market news feed
- **status**: Market status updates

## Performance Targets

### Latency Requirements
- **Real-Time Data**: <50ms end-to-end
- **Historical Data**: <200ms for cached, <2s for uncached
- **Market Status**: <10ms
- **WebSocket Updates**: <20ms

### Throughput Requirements
- **Concurrent Users**: 10,000+
- **Messages/Second**: 100,000+
- **API Requests**: 50,000/minute
- **Data Points**: 1M+ symbols supported

### Availability Requirements
- **Uptime**: 99.95% during market hours
- **Failover Time**: <30 seconds
- **Data Freshness**: <5 seconds for critical data
- **Recovery Time**: <5 minutes for full service

## Monitoring & Observability

### Key Metrics
- **Data Latency**: Provider to client delivery time
- **Cache Hit Ratio**: Percentage of requests served from cache
- **Provider Health**: Availability and response times
- **Rate Limit Usage**: Current vs maximum rates
- **Error Rates**: By provider, endpoint, and error type

### Alerting Thresholds
- **High Latency**: >100ms for real-time data
- **Low Cache Hit**: <80% hit ratio
- **Provider Down**: >5% error rate
- **Rate Limit**: >90% of limit reached
- **Data Staleness**: >30 seconds old

## Security & Compliance

### Data Protection
- **Encryption**: TLS 1.3 for all communications
- **Authentication**: JWT tokens with refresh
- **Authorization**: Role-based access control
- **Audit Logging**: All data access logged

### Regulatory Compliance
- **Market Data Agreements**: Proper licensing
- **Data Redistribution**: Controlled sharing
- **Privacy**: GDPR and local privacy laws
- **Financial Regulations**: SEC, AMMC compliance

## Disaster Recovery

### Backup Strategy
- **Real-Time**: Multiple provider redundancy
- **Historical**: Daily backups to cloud storage
- **Configuration**: Version-controlled infrastructure
- **Metadata**: Replicated across regions

### Recovery Procedures
- **Provider Failover**: Automatic within 30 seconds
- **Data Center Failover**: Manual within 15 minutes
- **Full System Recovery**: <4 hours RTO
- **Data Recovery**: <1 hour RPO

## Cost Optimization

### Provider Cost Management
- **Usage Monitoring**: Track costs per provider
- **Smart Routing**: Use cheapest provider for non-critical data
- **Bulk Requests**: Batch requests to reduce costs
- **Caching**: Minimize redundant provider calls

### Infrastructure Optimization
- **Auto Scaling**: Scale based on demand
- **Resource Pooling**: Shared infrastructure
- **Compression**: Reduce bandwidth costs
- **CDN**: Geographic distribution for global users