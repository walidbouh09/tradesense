"""Market data domain entities."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ....shared.kernel.entity import Entity
from ....shared.kernel.value_object import ValueObject


class MarketType(str, Enum):
    """Market type enumeration."""
    STOCK = "stock"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"


class MarketStatus(str, Enum):
    """Market status enumeration."""
    PRE_MARKET = "pre_market"
    OPEN = "open"
    CLOSED = "closed"
    POST_MARKET = "post_market"
    HOLIDAY = "holiday"
    SUSPENDED = "suspended"


class DataQuality(str, Enum):
    """Data quality levels."""
    REAL_TIME = "real_time"
    DELAYED = "delayed"
    END_OF_DAY = "end_of_day"
    ESTIMATED = "estimated"
    STALE = "stale"


class ProviderTier(str, Enum):
    """Provider tier classification."""
    TIER_1 = "tier_1"  # Premium providers (Bloomberg, Refinitiv)
    TIER_2 = "tier_2"  # Standard providers (Alpha Vantage, IEX)
    TIER_3 = "tier_3"  # Free providers (Yahoo Finance)
    REGIONAL = "regional"  # Regional exchanges


class Symbol(ValueObject):
    """Financial instrument symbol."""
    
    def __init__(
        self,
        ticker: str,
        exchange: str,
        market: str,
        instrument_type: MarketType,
        currency: str = "USD",
        isin: Optional[str] = None,
        cusip: Optional[str] = None,
    ):
        self.ticker = ticker.upper()
        self.exchange = exchange.upper()
        self.market = market.upper()
        self.instrument_type = instrument_type
        self.currency = currency.upper()
        self.isin = isin
        self.cusip = cusip
    
    @property
    def full_symbol(self) -> str:
        """Get full symbol with exchange."""
        return f"{self.ticker}.{self.exchange}"
    
    @property
    def is_us_market(self) -> bool:
        """Check if symbol is from US market."""
        return self.exchange in ["NYSE", "NASDAQ", "AMEX", "OTC"]
    
    @property
    def is_moroccan_market(self) -> bool:
        """Check if symbol is from Moroccan market."""
        return self.exchange in ["CSE", "CASABLANCA"]


class MarketDataPoint(ValueObject):
    """Single market data point."""
    
    def __init__(
        self,
        symbol: Symbol,
        timestamp: datetime,
        price: Decimal,
        volume: Optional[Decimal] = None,
        bid: Optional[Decimal] = None,
        ask: Optional[Decimal] = None,
        bid_size: Optional[Decimal] = None,
        ask_size: Optional[Decimal] = None,
        provider: str = "",
        quality: DataQuality = DataQuality.REAL_TIME,
        metadata: Optional[Dict] = None,
    ):
        self.symbol = symbol
        self.timestamp = timestamp
        self.price = price
        self.volume = volume
        self.bid = bid
        self.ask = ask
        self.bid_size = bid_size
        self.ask_size = ask_size
        self.provider = provider
        self.quality = quality
        self.metadata = metadata or {}
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread."""
        if self.bid and self.ask:
            return self.ask - self.bid
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price."""
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return None


class OHLCV(ValueObject):
    """OHLCV (Open, High, Low, Close, Volume) bar."""
    
    def __init__(
        self,
        symbol: Symbol,
        timestamp: datetime,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume: Decimal,
        timeframe: str = "1D",
        provider: str = "",
        adjusted: bool = False,
    ):
        self.symbol = symbol
        self.timestamp = timestamp
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.timeframe = timeframe
        self.provider = provider
        self.adjusted = adjusted
    
    @property
    def typical_price(self) -> Decimal:
        """Calculate typical price (HLC/3)."""
        return (self.high_price + self.low_price + self.close_price) / 3
    
    @property
    def price_change(self) -> Decimal:
        """Calculate price change."""
        return self.close_price - self.open_price
    
    @property
    def price_change_percent(self) -> Decimal:
        """Calculate price change percentage."""
        if self.open_price == 0:
            return Decimal("0")
        return (self.price_change / self.open_price) * 100


class OrderBookLevel(ValueObject):
    """Order book level (bid/ask with size)."""
    
    def __init__(
        self,
        price: Decimal,
        size: Decimal,
        orders: int = 1,
    ):
        self.price = price
        self.size = size
        self.orders = orders


class OrderBook(ValueObject):
    """Full order book with multiple levels."""
    
    def __init__(
        self,
        symbol: Symbol,
        timestamp: datetime,
        bids: List[OrderBookLevel],
        asks: List[OrderBookLevel],
        provider: str = "",
    ):
        self.symbol = symbol
        self.timestamp = timestamp
        self.bids = sorted(bids, key=lambda x: x.price, reverse=True)  # Highest first
        self.asks = sorted(asks, key=lambda x: x.price)  # Lowest first
        self.provider = provider
    
    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        """Get best bid (highest price)."""
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        """Get best ask (lowest price)."""
        return self.asks[0] if self.asks else None
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Calculate mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None


class Trade(ValueObject):
    """Individual trade execution."""
    
    def __init__(
        self,
        symbol: Symbol,
        timestamp: datetime,
        price: Decimal,
        size: Decimal,
        side: str,  # "buy" or "sell"
        trade_id: Optional[str] = None,
        provider: str = "",
    ):
        self.symbol = symbol
        self.timestamp = timestamp
        self.price = price
        self.size = size
        self.side = side
        self.trade_id = trade_id or str(uuid4())
        self.provider = provider


class MarketNews(ValueObject):
    """Market news item."""
    
    def __init__(
        self,
        news_id: str,
        headline: str,
        summary: str,
        content: str,
        timestamp: datetime,
        symbols: List[Symbol],
        source: str,
        sentiment: Optional[str] = None,
        relevance_score: Optional[float] = None,
        provider: str = "",
    ):
        self.news_id = news_id
        self.headline = headline
        self.summary = summary
        self.content = content
        self.timestamp = timestamp
        self.symbols = symbols
        self.source = source
        self.sentiment = sentiment
        self.relevance_score = relevance_score
        self.provider = provider


class Market(Entity):
    """Market entity representing a trading venue."""
    
    def __init__(
        self,
        market_id: UUID,
        name: str,
        code: str,
        country: str,
        timezone: str,
        currency: str,
        market_type: MarketType,
        trading_hours: Dict[str, Dict[str, str]],  # Day -> {open, close}
        holidays: List[datetime],
    ):
        super().__init__(market_id)
        self.name = name
        self.code = code.upper()
        self.country = country
        self.timezone = timezone
        self.currency = currency.upper()
        self.market_type = market_type
        self.trading_hours = trading_hours
        self.holidays = holidays
        self.status = MarketStatus.CLOSED
        self.last_status_update = datetime.utcnow()
    
    def update_status(self, status: MarketStatus) -> None:
        """Update market status."""
        self.status = status
        self.last_status_update = datetime.utcnow()
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if given date is a trading day."""
        # Check if it's a weekend
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's a holiday
        for holiday in self.holidays:
            if holiday.date() == date.date():
                return False
        
        return True
    
    def get_trading_hours(self, day: str) -> Optional[Dict[str, str]]:
        """Get trading hours for specific day."""
        return self.trading_hours.get(day.lower())


class DataProvider(Entity):
    """Market data provider entity."""
    
    def __init__(
        self,
        provider_id: UUID,
        name: str,
        tier: ProviderTier,
        supported_markets: List[str],
        supported_data_types: List[str],
        rate_limits: Dict[str, int],
        latency_ms: int,
        reliability_score: float,
        cost_per_request: Decimal,
        api_endpoint: str,
        websocket_endpoint: Optional[str] = None,
    ):
        super().__init__(provider_id)
        self.name = name
        self.tier = tier
        self.supported_markets = supported_markets
        self.supported_data_types = supported_data_types
        self.rate_limits = rate_limits
        self.latency_ms = latency_ms
        self.reliability_score = reliability_score  # 0.0 to 1.0
        self.cost_per_request = cost_per_request
        self.api_endpoint = api_endpoint
        self.websocket_endpoint = websocket_endpoint
        self.is_active = True
        self.last_health_check = datetime.utcnow()
        self.error_count = 0
        self.success_count = 0
    
    def record_success(self) -> None:
        """Record successful request."""
        self.success_count += 1
        self.last_health_check = datetime.utcnow()
    
    def record_error(self) -> None:
        """Record failed request."""
        self.error_count += 1
        self.last_health_check = datetime.utcnow()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total_requests = self.success_count + self.error_count
        if total_requests == 0:
            return 1.0
        return self.success_count / total_requests
    
    @property
    def quality_score(self) -> float:
        """Calculate overall quality score."""
        # Weighted score based on reliability, latency, and success rate
        latency_score = max(0, 1 - (self.latency_ms / 1000))  # Normalize latency
        return (
            0.4 * self.reliability_score +
            0.3 * self.success_rate +
            0.3 * latency_score
        )
    
    def supports_market(self, market: str) -> bool:
        """Check if provider supports specific market."""
        return market.upper() in [m.upper() for m in self.supported_markets]
    
    def supports_data_type(self, data_type: str) -> bool:
        """Check if provider supports specific data type."""
        return data_type.lower() in [dt.lower() for dt in self.supported_data_types]


class DataAggregator(Entity):
    """Data aggregator for combining multiple provider sources."""
    
    def __init__(
        self,
        aggregator_id: UUID,
        name: str,
        providers: List[DataProvider],
        aggregation_rules: Dict[str, Dict],
    ):
        super().__init__(aggregator_id)
        self.name = name
        self.providers = providers
        self.aggregation_rules = aggregation_rules
        self.provider_weights = {}
        self.last_aggregation = datetime.utcnow()
    
    def add_provider(self, provider: DataProvider, weight: float = 1.0) -> None:
        """Add provider with weight."""
        self.providers.append(provider)
        self.provider_weights[provider.id] = weight
    
    def remove_provider(self, provider_id: UUID) -> None:
        """Remove provider."""
        self.providers = [p for p in self.providers if p.id != provider_id]
        if provider_id in self.provider_weights:
            del self.provider_weights[provider_id]
    
    def get_best_providers(self, market: str, data_type: str, count: int = 3) -> List[DataProvider]:
        """Get best providers for specific market and data type."""
        suitable_providers = [
            p for p in self.providers
            if p.is_active and p.supports_market(market) and p.supports_data_type(data_type)
        ]
        
        # Sort by quality score
        suitable_providers.sort(key=lambda p: p.quality_score, reverse=True)
        
        return suitable_providers[:count]
    
    def update_aggregation_timestamp(self) -> None:
        """Update last aggregation timestamp."""
        self.last_aggregation = datetime.utcnow()


class CacheEntry(ValueObject):
    """Cache entry with metadata."""
    
    def __init__(
        self,
        key: str,
        data: Dict,
        timestamp: datetime,
        ttl_seconds: int,
        provider: str,
        data_type: str,
        quality: DataQuality,
    ):
        self.key = key
        self.data = data
        self.timestamp = timestamp
        self.ttl_seconds = ttl_seconds
        self.provider = provider
        self.data_type = data_type
        self.quality = quality
        self.access_count = 0
        self.last_accessed = timestamp
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        expiry_time = self.timestamp.timestamp() + self.ttl_seconds
        return datetime.utcnow().timestamp() > expiry_time
    
    @property
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int((datetime.utcnow() - self.timestamp).total_seconds())
    
    def access(self) -> None:
        """Record cache access."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class RateLimiter(Entity):
    """Rate limiter for API requests."""
    
    def __init__(
        self,
        limiter_id: UUID,
        name: str,
        requests_per_second: int,
        burst_capacity: int,
        window_size_seconds: int = 60,
    ):
        super().__init__(limiter_id)
        self.name = name
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.window_size_seconds = window_size_seconds
        self.request_history: List[datetime] = []
        self.tokens = burst_capacity
        self.last_refill = datetime.utcnow()
    
    def can_make_request(self) -> bool:
        """Check if request can be made."""
        self._refill_tokens()
        return self.tokens > 0
    
    def consume_token(self) -> bool:
        """Consume a token if available."""
        if self.can_make_request():
            self.tokens -= 1
            self.request_history.append(datetime.utcnow())
            self._cleanup_history()
            return True
        return False
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed."""
        now = datetime.utcnow()
        time_elapsed = (now - self.last_refill).total_seconds()
        tokens_to_add = int(time_elapsed * self.requests_per_second)
        
        if tokens_to_add > 0:
            self.tokens = min(self.burst_capacity, self.tokens + tokens_to_add)
            self.last_refill = now
    
    def _cleanup_history(self) -> None:
        """Remove old requests from history."""
        cutoff_time = datetime.utcnow().timestamp() - self.window_size_seconds
        self.request_history = [
            req_time for req_time in self.request_history
            if req_time.timestamp() > cutoff_time
        ]
    
    @property
    def current_rate(self) -> float:
        """Get current request rate per second."""
        if not self.request_history:
            return 0.0
        
        recent_requests = len(self.request_history)
        return recent_requests / self.window_size_seconds
    
    @property
    def utilization_percent(self) -> float:
        """Get rate limit utilization percentage."""
        return (self.current_rate / self.requests_per_second) * 100