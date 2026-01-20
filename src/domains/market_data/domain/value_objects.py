"""Market data domain value objects."""

from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ....shared.kernel.value_object import ValueObject


class TimeFrame(str, Enum):
    """Time frame for historical data."""
    TICK = "tick"
    SECOND_1 = "1s"
    SECOND_5 = "5s"
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class DataSource(str, Enum):
    """Data source types."""
    EXCHANGE = "exchange"
    MARKET_MAKER = "market_maker"
    AGGREGATOR = "aggregator"
    ESTIMATED = "estimated"
    CALCULATED = "calculated"


class PriceType(str, Enum):
    """Price type enumeration."""
    BID = "bid"
    ASK = "ask"
    LAST = "last"
    MID = "mid"
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VWAP = "vwap"
    TWAP = "twap"


class MarketDataRequest(ValueObject):
    """Market data request specification."""
    
    def __init__(
        self,
        symbols: List[str],
        data_types: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        timeframe: Optional[TimeFrame] = None,
        limit: Optional[int] = None,
        include_extended_hours: bool = False,
        adjust_for_splits: bool = True,
        adjust_for_dividends: bool = False,
        preferred_providers: Optional[List[str]] = None,
        max_latency_ms: Optional[int] = None,
        min_quality: Optional[str] = None,
    ):
        self.symbols = [s.upper() for s in symbols]
        self.data_types = data_types
        self.start_time = start_time
        self.end_time = end_time
        self.timeframe = timeframe
        self.limit = limit
        self.include_extended_hours = include_extended_hours
        self.adjust_for_splits = adjust_for_splits
        self.adjust_for_dividends = adjust_for_dividends
        self.preferred_providers = preferred_providers or []
        self.max_latency_ms = max_latency_ms
        self.min_quality = min_quality
        self.request_id = f"req_{datetime.utcnow().timestamp()}"
    
    @property
    def is_real_time(self) -> bool:
        """Check if this is a real-time data request."""
        return self.start_time is None and self.end_time is None
    
    @property
    def is_historical(self) -> bool:
        """Check if this is a historical data request."""
        return self.start_time is not None or self.end_time is not None
    
    def get_cache_key(self) -> str:
        """Generate cache key for this request."""
        key_parts = [
            "_".join(sorted(self.symbols)),
            "_".join(sorted(self.data_types)),
            str(self.start_time.timestamp()) if self.start_time else "none",
            str(self.end_time.timestamp()) if self.end_time else "none",
            self.timeframe.value if self.timeframe else "none",
            str(self.limit) if self.limit else "none",
        ]
        return "md_" + "_".join(key_parts)


class MarketDataResponse(ValueObject):
    """Market data response container."""
    
    def __init__(
        self,
        request_id: str,
        data: Dict,
        metadata: Dict,
        timestamp: datetime,
        latency_ms: int,
        provider: str,
        quality: str,
        cached: bool = False,
        errors: Optional[List[str]] = None,
    ):
        self.request_id = request_id
        self.data = data
        self.metadata = metadata
        self.timestamp = timestamp
        self.latency_ms = latency_ms
        self.provider = provider
        self.quality = quality
        self.cached = cached
        self.errors = errors or []
    
    @property
    def is_successful(self) -> bool:
        """Check if response is successful."""
        return len(self.errors) == 0
    
    @property
    def data_count(self) -> int:
        """Get count of data points."""
        if isinstance(self.data, dict):
            return sum(len(v) if isinstance(v, list) else 1 for v in self.data.values())
        elif isinstance(self.data, list):
            return len(self.data)
        return 1 if self.data else 0


class TradingSession(ValueObject):
    """Trading session information."""
    
    def __init__(
        self,
        session_name: str,
        start_time: time,
        end_time: time,
        timezone: str,
        is_primary: bool = True,
    ):
        self.session_name = session_name
        self.start_time = start_time
        self.end_time = end_time
        self.timezone = timezone
        self.is_primary = is_primary
    
    def is_active(self, current_time: time) -> bool:
        """Check if session is currently active."""
        if self.start_time <= self.end_time:
            # Same day session
            return self.start_time <= current_time <= self.end_time
        else:
            # Overnight session
            return current_time >= self.start_time or current_time <= self.end_time


class MarketHours(ValueObject):
    """Market trading hours configuration."""
    
    def __init__(
        self,
        market_code: str,
        timezone: str,
        regular_hours: Dict[str, TradingSession],
        extended_hours: Optional[Dict[str, TradingSession]] = None,
        holidays: Optional[List[datetime]] = None,
    ):
        self.market_code = market_code.upper()
        self.timezone = timezone
        self.regular_hours = regular_hours  # day_of_week -> TradingSession
        self.extended_hours = extended_hours or {}
        self.holidays = holidays or []
    
    def get_session(self, day_of_week: str, extended: bool = False) -> Optional[TradingSession]:
        """Get trading session for specific day."""
        sessions = self.extended_hours if extended else self.regular_hours
        return sessions.get(day_of_week.lower())
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if given date is a trading day."""
        # Check holidays
        for holiday in self.holidays:
            if holiday.date() == date.date():
                return False
        
        # Check if there's a session for this day
        day_name = date.strftime("%A").lower()
        return day_name in self.regular_hours


class PriceLevel(ValueObject):
    """Price level with size and order count."""
    
    def __init__(
        self,
        price: Decimal,
        size: Decimal,
        order_count: int = 1,
        timestamp: Optional[datetime] = None,
    ):
        self.price = price
        self.size = size
        self.order_count = order_count
        self.timestamp = timestamp or datetime.utcnow()
    
    @property
    def average_order_size(self) -> Decimal:
        """Calculate average order size."""
        if self.order_count == 0:
            return Decimal("0")
        return self.size / self.order_count


class MarketDepth(ValueObject):
    """Market depth (order book) data."""
    
    def __init__(
        self,
        symbol: str,
        bids: List[PriceLevel],
        asks: List[PriceLevel],
        timestamp: datetime,
        sequence_number: Optional[int] = None,
    ):
        self.symbol = symbol.upper()
        self.bids = sorted(bids, key=lambda x: x.price, reverse=True)
        self.asks = sorted(asks, key=lambda x: x.price)
        self.timestamp = timestamp
        self.sequence_number = sequence_number
    
    @property
    def best_bid(self) -> Optional[PriceLevel]:
        """Get best bid price level."""
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[PriceLevel]:
        """Get best ask price level."""
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
    
    def get_total_size(self, side: str, levels: int = 5) -> Decimal:
        """Get total size for specified levels."""
        price_levels = self.bids if side.lower() == "bid" else self.asks
        return sum(level.size for level in price_levels[:levels])


class CorporateAction(ValueObject):
    """Corporate action information."""
    
    def __init__(
        self,
        symbol: str,
        action_type: str,  # "split", "dividend", "merger", "spinoff"
        ex_date: datetime,
        record_date: Optional[datetime] = None,
        payment_date: Optional[datetime] = None,
        ratio: Optional[Decimal] = None,
        amount: Optional[Decimal] = None,
        currency: str = "USD",
        description: str = "",
    ):
        self.symbol = symbol.upper()
        self.action_type = action_type.lower()
        self.ex_date = ex_date
        self.record_date = record_date
        self.payment_date = payment_date
        self.ratio = ratio
        self.amount = amount
        self.currency = currency.upper()
        self.description = description
    
    @property
    def is_split(self) -> bool:
        """Check if this is a stock split."""
        return self.action_type == "split"
    
    @property
    def is_dividend(self) -> bool:
        """Check if this is a dividend payment."""
        return self.action_type == "dividend"
    
    def get_adjustment_factor(self) -> Decimal:
        """Get price adjustment factor."""
        if self.is_split and self.ratio:
            return self.ratio
        elif self.is_dividend and self.amount:
            # Dividend adjustment would need previous close price
            return Decimal("1.0")  # Placeholder
        return Decimal("1.0")


class DataQualityMetrics(ValueObject):
    """Data quality metrics."""
    
    def __init__(
        self,
        provider: str,
        symbol: str,
        data_type: str,
        timestamp: datetime,
        latency_ms: int,
        completeness_percent: float,
        accuracy_score: float,
        freshness_seconds: int,
        error_rate: float,
        sample_size: int,
    ):
        self.provider = provider
        self.symbol = symbol.upper()
        self.data_type = data_type
        self.timestamp = timestamp
        self.latency_ms = latency_ms
        self.completeness_percent = completeness_percent
        self.accuracy_score = accuracy_score
        self.freshness_seconds = freshness_seconds
        self.error_rate = error_rate
        self.sample_size = sample_size
    
    @property
    def overall_quality_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        # Weighted average of quality metrics
        latency_score = max(0, 100 - (self.latency_ms / 10))  # 10ms = 1 point
        freshness_score = max(0, 100 - (self.freshness_seconds / 6))  # 6s = 1 point
        error_score = max(0, 100 - (self.error_rate * 100))
        
        return (
            0.25 * self.completeness_percent +
            0.25 * (self.accuracy_score * 100) +
            0.20 * latency_score +
            0.15 * freshness_score +
            0.15 * error_score
        )
    
    @property
    def quality_grade(self) -> str:
        """Get quality grade (A-F)."""
        score = self.overall_quality_score
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


class ProviderConfiguration(ValueObject):
    """Provider configuration settings."""
    
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        base_url: str,
        websocket_url: Optional[str] = None,
        rate_limits: Optional[Dict[str, int]] = None,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        retry_delay_seconds: int = 1,
        priority: int = 1,
        enabled: bool = True,
        supported_markets: Optional[List[str]] = None,
        supported_data_types: Optional[List[str]] = None,
        cost_per_request: Optional[Decimal] = None,
    ):
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url
        self.websocket_url = websocket_url
        self.rate_limits = rate_limits or {}
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.priority = priority
        self.enabled = enabled
        self.supported_markets = supported_markets or []
        self.supported_data_types = supported_data_types or []
        self.cost_per_request = cost_per_request or Decimal("0")
    
    def supports_market(self, market: str) -> bool:
        """Check if provider supports market."""
        if not self.supported_markets:
            return True  # No restrictions
        return market.upper() in [m.upper() for m in self.supported_markets]
    
    def supports_data_type(self, data_type: str) -> bool:
        """Check if provider supports data type."""
        if not self.supported_data_types:
            return True  # No restrictions
        return data_type.lower() in [dt.lower() for dt in self.supported_data_types]


class CacheConfiguration(ValueObject):
    """Cache configuration settings."""
    
    def __init__(
        self,
        cache_name: str,
        ttl_seconds: Dict[str, int],  # data_type -> ttl
        max_size_mb: int,
        eviction_policy: str = "lru",
        compression_enabled: bool = True,
        encryption_enabled: bool = False,
        replication_factor: int = 1,
        write_through: bool = False,
        write_behind: bool = True,
    ):
        self.cache_name = cache_name
        self.ttl_seconds = ttl_seconds
        self.max_size_mb = max_size_mb
        self.eviction_policy = eviction_policy.lower()
        self.compression_enabled = compression_enabled
        self.encryption_enabled = encryption_enabled
        self.replication_factor = replication_factor
        self.write_through = write_through
        self.write_behind = write_behind
    
    def get_ttl(self, data_type: str) -> int:
        """Get TTL for specific data type."""
        return self.ttl_seconds.get(data_type.lower(), 300)  # Default 5 minutes


class AggregationRule(ValueObject):
    """Data aggregation rule."""
    
    def __init__(
        self,
        rule_name: str,
        data_type: str,
        aggregation_method: str,  # "latest", "average", "weighted_average", "consensus"
        conflict_resolution: str,  # "timestamp", "quality", "provider_priority"
        min_sources: int = 1,
        max_age_seconds: int = 60,
        quality_threshold: float = 0.7,
        provider_weights: Optional[Dict[str, float]] = None,
    ):
        self.rule_name = rule_name
        self.data_type = data_type
        self.aggregation_method = aggregation_method.lower()
        self.conflict_resolution = conflict_resolution.lower()
        self.min_sources = min_sources
        self.max_age_seconds = max_age_seconds
        self.quality_threshold = quality_threshold
        self.provider_weights = provider_weights or {}
    
    def get_provider_weight(self, provider: str) -> float:
        """Get weight for specific provider."""
        return self.provider_weights.get(provider, 1.0)


class MarketDataSubscription(ValueObject):
    """WebSocket subscription configuration."""
    
    def __init__(
        self,
        subscription_id: str,
        symbols: List[str],
        data_types: List[str],
        markets: Optional[List[str]] = None,
        filters: Optional[Dict] = None,
        throttle_ms: Optional[int] = None,
        conflation: bool = False,
        snapshot: bool = True,
    ):
        self.subscription_id = subscription_id
        self.symbols = [s.upper() for s in symbols]
        self.data_types = data_types
        self.markets = [m.upper() for m in markets] if markets else []
        self.filters = filters or {}
        self.throttle_ms = throttle_ms
        self.conflation = conflation
        self.snapshot = snapshot
        self.created_at = datetime.utcnow()
        self.last_update = datetime.utcnow()
    
    def matches_symbol(self, symbol: str) -> bool:
        """Check if subscription matches symbol."""
        return symbol.upper() in self.symbols or "*" in self.symbols
    
    def matches_data_type(self, data_type: str) -> bool:
        """Check if subscription matches data type."""
        return data_type.lower() in [dt.lower() for dt in self.data_types]
    
    def update_timestamp(self) -> None:
        """Update last update timestamp."""
        self.last_update = datetime.utcnow()