"""
Market Data Engine Usage Examples

This file demonstrates how to use the TradeSense AI Market Data Engine
for retrieving real-time and historical market data from multiple providers.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import aiohttp

from src.domains.market_data.application.services import (
    MarketDataService,
    CacheService,
    DataQualityService,
)
from src.domains.market_data.domain.entities import (
    DataProvider,
    DataAggregator,
    Market,
    Symbol,
    MarketType,
    RateLimiter,
    ProviderTier,
)
from src.domains.market_data.domain.value_objects import (
    TimeFrame,
    MarketDataRequest,
    MarketDataSubscription,
    ProviderConfiguration,
)
from src.domains.market_data.infrastructure.providers.alpha_vantage_provider import AlphaVantageProvider
from src.domains.market_data.infrastructure.providers.yahoo_finance_provider import YahooFinanceProvider
from src.infrastructure.messaging.in_memory_bus import InMemoryEventBus


async def example_1_basic_provider_setup():
    """Example 1: Basic provider setup and configuration."""
    
    print("=== Example 1: Basic Provider Setup ===")
    
    # Create HTTP session
    session = aiohttp.ClientSession()
    
    try:
        # Configure Alpha Vantage provider
        alpha_vantage_config = {
            "name": "alpha_vantage",
            "api_key": "YOUR_API_KEY_HERE",
            "base_url": "https://www.alphavantage.co/query",
            "supported_markets": ["US", "GLOBAL"],
            "supported_data_types": ["quote", "historical", "search"],
            "rate_limits": {"requests_per_minute": 5, "daily_limit": 500},
            "timeout_seconds": 30,
            "retry_attempts": 3,
        }
        
        # Configure Yahoo Finance provider
        yahoo_finance_config = {
            "name": "yahoo_finance",
            "base_url": "https://query1.finance.yahoo.com",
            "supported_markets": ["US", "GLOBAL", "MOROCCO"],
            "supported_data_types": ["quote", "historical", "chart", "news"],
            "rate_limits": {"requests_per_hour": 2000},
            "timeout_seconds": 15,
            "retry_attempts": 2,
        }
        
        # Create provider instances
        alpha_vantage = AlphaVantageProvider(alpha_vantage_config, session)
        yahoo_finance = YahooFinanceProvider(yahoo_finance_config, session)
        
        print(f"✅ Alpha Vantage Provider: {alpha_vantage.name}")
        print(f"   Supported Markets: {alpha_vantage_config['supported_markets']}")
        print(f"   Supported Data Types: {alpha_vantage_config['supported_data_types']}")
        
        print(f"✅ Yahoo Finance Provider: {yahoo_finance.name}")
        print(f"   Supported Markets: {yahoo_finance_config['supported_markets']}")
        print(f"   Supported Data Types: {yahoo_finance_config['supported_data_types']}")
        
        # Test provider connections
        print("\n🔍 Testing provider connections...")
        
        alpha_health = await alpha_vantage.health_check()
        yahoo_health = await yahoo_finance.health_check()
        
        print(f"Alpha Vantage Health: {alpha_health['status']} (Latency: {alpha_health.get('latency_ms', 'N/A')}ms)")
        print(f"Yahoo Finance Health: {yahoo_health['status']} (Latency: {yahoo_health.get('latency_ms', 'N/A')}ms)")
        
        return [alpha_vantage, yahoo_finance]
    
    finally:
        await session.close()


async def example_2_real_time_data_retrieval():
    """Example 2: Real-time data retrieval with multiple providers."""
    
    print("\n=== Example 2: Real-time Data Retrieval ===")
    
    # Setup providers (simplified for example)
    session = aiohttp.ClientSession()
    
    try:
        # Create mock providers for demonstration
        providers = []
        
        # Create data aggregator
        aggregator = DataAggregator(
            aggregator_id=uuid4(),
            name="main_aggregator",
            providers=providers,
            aggregation_rules={
                "quote": {"method": "latest", "min_sources": 1},
                "historical": {"method": "primary_fallback", "min_sources": 1},
            }
        )
        
        # Create cache service
        cache_service = CacheService()
        
        # Create rate limiter
        rate_limiter = RateLimiter(
            limiter_id=uuid4(),
            name="api_rate_limiter",
            requests_per_second=10,
            burst_capacity=50,
        )
        
        # Create event bus
        event_bus = InMemoryEventBus()
        await event_bus.start()
        
        # Create market data service
        market_data_service = MarketDataService(
            providers=providers,
            aggregator=aggregator,
            cache_service=cache_service,
            rate_limiter=rate_limiter,
            event_bus=event_bus,
        )
        
        # Define symbols to query
        symbols = ["AAPL", "MSFT", "GOOGL", "ATW.CSE", "BCP.CSE"]
        
        print(f"📊 Requesting real-time quotes for: {', '.join(symbols)}")
        
        # Get real-time data
        response = await market_data_service.get_real_time_data(
            symbols=symbols,
            data_types=["quote"],
            preferred_providers=["yahoo_finance", "alpha_vantage"],
        )
        
        print(f"📈 Response Status: {'Success' if response.is_successful else 'Failed'}")
        print(f"⏱️ Latency: {response.latency_ms}ms")
        print(f"🏢 Provider: {response.provider}")
        print(f"🎯 Quality: {response.quality}")
        print(f"💾 Cached: {response.cached}")
        
        if response.is_successful:
            print("\n📋 Quote Data:")
            for symbol in symbols:
                quote_data = response.data.get(symbol, {})
                if quote_data:
                    print(f"  {symbol}: ${quote_data.get('price', 'N/A')} "
                          f"(Vol: {quote_data.get('volume', 'N/A')})")
        else:
            print(f"❌ Errors: {', '.join(response.errors)}")
        
        await event_bus.stop()
    
    finally:
        await session.close()


async def example_3_historical_data_analysis():
    """Example 3: Historical data retrieval and analysis."""
    
    print("\n=== Example 3: Historical Data Analysis ===")
    
    session = aiohttp.ClientSession()
    
    try:
        # Setup simplified service (mock for demonstration)
        cache_service = CacheService()
        rate_limiter = RateLimiter(
            limiter_id=uuid4(),
            name="historical_limiter",
            requests_per_second=5,
            burst_capacity=20,
        )
        event_bus = InMemoryEventBus()
        await event_bus.start()
        
        aggregator = DataAggregator(
            aggregator_id=uuid4(),
            name="historical_aggregator",
            providers=[],
            aggregation_rules={}
        )
        
        market_data_service = MarketDataService(
            providers=[],
            aggregator=aggregator,
            cache_service=cache_service,
            rate_limiter=rate_limiter,
            event_bus=event_bus,
        )
        
        # Define historical data request
        symbols = ["AAPL", "MSFT"]
        start_date = datetime.utcnow() - timedelta(days=30)  # Last 30 days
        end_date = datetime.utcnow()
        
        print(f"📈 Requesting historical data for: {', '.join(symbols)}")
        print(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"⏰ Timeframe: {TimeFrame.DAY_1.value}")
        
        # Get historical data
        response = await market_data_service.get_historical_data(
            symbols=symbols,
            data_types=["ohlcv"],
            start_time=start_date,
            end_time=end_date,
            timeframe=TimeFrame.DAY_1.value,
            preferred_providers=["yahoo_finance"],
        )
        
        print(f"📊 Response Status: {'Success' if response.is_successful else 'Failed'}")
        print(f"⏱️ Latency: {response.latency_ms}ms")
        print(f"🏢 Provider: {response.provider}")
        
        if response.is_successful:
            print("\n📋 Historical Data Summary:")
            for symbol in symbols:
                historical_data = response.data.get(symbol, [])
                if historical_data:
                    print(f"  {symbol}: {len(historical_data)} data points")
                    
                    # Calculate simple statistics
                    if len(historical_data) > 0:
                        prices = [float(point.get('close', 0)) for point in historical_data]
                        if prices:
                            avg_price = sum(prices) / len(prices)
                            min_price = min(prices)
                            max_price = max(prices)
                            
                            print(f"    Average: ${avg_price:.2f}")
                            print(f"    Range: ${min_price:.2f} - ${max_price:.2f}")
        
        await event_bus.stop()
    
    finally:
        await session.close()


async def example_4_websocket_subscriptions():
    """Example 4: WebSocket real-time subscriptions."""
    
    print("\n=== Example 4: WebSocket Subscriptions ===")
    
    # Setup service (simplified)
    cache_service = CacheService()
    rate_limiter = RateLimiter(
        limiter_id=uuid4(),
        name="ws_limiter",
        requests_per_second=100,
        burst_capacity=200,
    )
    event_bus = InMemoryEventBus()
    await event_bus.start()
    
    aggregator = DataAggregator(
        aggregator_id=uuid4(),
        name="ws_aggregator",
        providers=[],
        aggregation_rules={}
    )
    
    market_data_service = MarketDataService(
        providers=[],
        aggregator=aggregator,
        cache_service=cache_service,
        rate_limiter=rate_limiter,
        event_bus=event_bus,
    )
    
    # Create subscriptions
    subscriptions = []
    
    # US Stocks subscription
    us_subscription = MarketDataSubscription(
        subscription_id="us_stocks_001",
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        data_types=["quote", "trade"],
        markets=["US"],
        throttle_ms=1000,  # 1 second throttle
        conflation=True,   # Conflate rapid updates
    )
    subscriptions.append(us_subscription)
    
    # Moroccan Stocks subscription
    morocco_subscription = MarketDataSubscription(
        subscription_id="morocco_stocks_001",
        symbols=["ATW.CSE", "BCP.CSE", "IAM.CSE", "LHM.CSE"],
        data_types=["quote"],
        markets=["MOROCCO"],
        throttle_ms=5000,  # 5 second throttle
    )
    subscriptions.append(morocco_subscription)
    
    # Forex subscription
    forex_subscription = MarketDataSubscription(
        subscription_id="forex_001",
        symbols=["EURUSD", "GBPUSD", "USDMAD"],
        data_types=["quote"],
        markets=["FOREX"],
        throttle_ms=500,   # 500ms throttle
    )
    subscriptions.append(forex_subscription)
    
    print("📡 Creating WebSocket subscriptions...")
    
    # Subscribe to all
    for subscription in subscriptions:
        success = await market_data_service.subscribe_real_time(subscription)
        
        print(f"{'✅' if success else '❌'} Subscription {subscription.subscription_id}")
        print(f"   Symbols: {', '.join(subscription.symbols)}")
        print(f"   Data Types: {', '.join(subscription.data_types)}")
        print(f"   Markets: {', '.join(subscription.markets)}")
        print(f"   Throttle: {subscription.throttle_ms}ms")
    
    # Simulate running for a while
    print("\n⏳ Simulating real-time data streaming for 10 seconds...")
    await asyncio.sleep(10)
    
    # Unsubscribe
    print("\n🛑 Unsubscribing from real-time data...")
    for subscription in subscriptions:
        success = await market_data_service.unsubscribe_real_time(subscription.subscription_id)
        print(f"{'✅' if success else '❌'} Unsubscribed {subscription.subscription_id}")
    
    await event_bus.stop()


async def example_5_cache_and_performance():
    """Example 5: Cache performance and statistics."""
    
    print("\n=== Example 5: Cache Performance ===")
    
    # Create cache service
    cache_service = CacheService()
    
    # Simulate cache operations
    print("💾 Testing cache operations...")
    
    # Set some test data
    test_data = {
        "AAPL": {"price": 150.25, "volume": 1000000, "timestamp": datetime.utcnow().isoformat()},
        "MSFT": {"price": 305.50, "volume": 800000, "timestamp": datetime.utcnow().isoformat()},
        "GOOGL": {"price": 2750.75, "volume": 500000, "timestamp": datetime.utcnow().isoformat()},
    }
    
    # Cache the data
    for symbol, data in test_data.items():
        await cache_service.set(
            key=f"quote_{symbol}",
            data=data,
            ttl_seconds=60,
            provider="yahoo_finance",
            data_type="quote",
            quality="good",
        )
        print(f"📝 Cached data for {symbol}")
    
    # Retrieve from cache
    print("\n🔍 Retrieving from cache...")
    for symbol in test_data.keys():
        cached_entry = await cache_service.get(f"quote_{symbol}")
        if cached_entry:
            print(f"✅ Cache hit for {symbol}: ${cached_entry.data.get('price', 'N/A')}")
        else:
            print(f"❌ Cache miss for {symbol}")
    
    # Test cache miss
    print("\n🔍 Testing cache miss...")
    missing_entry = await cache_service.get("quote_NONEXISTENT")
    print(f"{'❌ Cache miss' if not missing_entry else '✅ Unexpected hit'} for NONEXISTENT")
    
    # Get cache statistics
    stats = cache_service.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total Requests: {stats['total_requests']}")
    print(f"   Cache Hits: {stats['hits']}")
    print(f"   Cache Misses: {stats['misses']}")
    print(f"   Hit Rate: {stats['hit_rate_percent']:.1f}%")
    print(f"   Local Cache Size: {stats['local_cache_size']} entries")
    
    # Test cache invalidation
    print(f"\n🗑️ Testing cache invalidation...")
    await cache_service.invalidate("quote_")
    
    # Verify invalidation
    print("🔍 Verifying cache invalidation...")
    for symbol in test_data.keys():
        cached_entry = await cache_service.get(f"quote_{symbol}")
        print(f"{'❌ Invalidated' if not cached_entry else '⚠️ Still cached'} for {symbol}")


async def example_6_data_quality_monitoring():
    """Example 6: Data quality monitoring and reporting."""
    
    print("\n=== Example 6: Data Quality Monitoring ===")
    
    # Create data quality service
    quality_service = DataQualityService()
    
    print("📊 Recording quality metrics...")
    
    # Simulate quality metrics for different providers
    providers_metrics = [
        {
            "provider": "yahoo_finance",
            "symbol": "AAPL",
            "data_type": "quote",
            "latency_ms": 85,
            "completeness_percent": 98.5,
            "accuracy_score": 0.99,
            "freshness_seconds": 2,
            "error_rate": 0.01,
            "sample_size": 1000,
        },
        {
            "provider": "alpha_vantage",
            "symbol": "AAPL",
            "data_type": "quote",
            "latency_ms": 150,
            "completeness_percent": 95.0,
            "accuracy_score": 0.97,
            "freshness_seconds": 15,
            "error_rate": 0.03,
            "sample_size": 500,
        },
        {
            "provider": "yahoo_finance",
            "symbol": "ATW.CSE",
            "data_type": "quote",
            "latency_ms": 120,
            "completeness_percent": 92.0,
            "accuracy_score": 0.95,
            "freshness_seconds": 30,
            "error_rate": 0.05,
            "sample_size": 200,
        },
    ]
    
    # Record metrics
    for metrics in providers_metrics:
        await quality_service.record_quality_metrics(**metrics)
        print(f"📝 Recorded metrics for {metrics['provider']} - {metrics['symbol']}")
    
    # Generate quality reports
    print(f"\n📋 Quality Reports:")
    
    # Overall report
    overall_report = quality_service.get_quality_report(hours=24)
    if "message" not in overall_report:
        print(f"🌐 Overall Quality (24h):")
        print(f"   Metrics Count: {overall_report['metrics_count']}")
        print(f"   Avg Latency: {overall_report['average_latency_ms']:.1f}ms")
        print(f"   Avg Completeness: {overall_report['average_completeness_percent']:.1f}%")
        print(f"   Avg Accuracy: {overall_report['average_accuracy_score']:.3f}")
        print(f"   Quality Score: {overall_report['overall_quality_score']:.1f}")
        print(f"   Quality Grade: {overall_report['quality_grade']}")
    
    # Provider-specific report
    yahoo_report = quality_service.get_quality_report(provider="yahoo_finance", hours=24)
    if "message" not in yahoo_report:
        print(f"\n🏢 Yahoo Finance Quality:")
        print(f"   Quality Score: {yahoo_report['overall_quality_score']:.1f}")
        print(f"   Quality Grade: {yahoo_report['quality_grade']}")
        print(f"   Avg Latency: {yahoo_report['average_latency_ms']:.1f}ms")
        print(f"   Error Rate: {yahoo_report['average_error_rate']:.3f}")
    
    # Symbol-specific report
    aapl_report = quality_service.get_quality_report(symbol="AAPL", hours=24)
    if "message" not in aapl_report:
        print(f"\n📈 AAPL Data Quality:")
        print(f"   Quality Score: {aapl_report['overall_quality_score']:.1f}")
        print(f"   Quality Grade: {aapl_report['quality_grade']}")
        print(f"   Providers: {aapl_report['metrics_count']} metrics")


async def example_7_multi_market_support():
    """Example 7: Multi-market support (US + Morocco)."""
    
    print("\n=== Example 7: Multi-Market Support ===")
    
    # Define symbols from different markets
    us_symbols = [
        Symbol("AAPL", "NASDAQ", "US", MarketType.STOCK, "USD"),
        Symbol("MSFT", "NASDAQ", "US", MarketType.STOCK, "USD"),
        Symbol("JPM", "NYSE", "US", MarketType.STOCK, "USD"),
    ]
    
    moroccan_symbols = [
        Symbol("ATW", "CSE", "MOROCCO", MarketType.STOCK, "MAD"),
        Symbol("BCP", "CSE", "MOROCCO", MarketType.STOCK, "MAD"),
        Symbol("IAM", "CSE", "MOROCCO", MarketType.STOCK, "MAD"),
    ]
    
    forex_symbols = [
        Symbol("EURUSD", "FOREX", "GLOBAL", MarketType.FOREX, "USD"),
        Symbol("USDMAD", "FOREX", "GLOBAL", MarketType.FOREX, "MAD"),
    ]
    
    print("🌍 Multi-Market Symbol Analysis:")
    
    print(f"\n🇺🇸 US Market Symbols:")
    for symbol in us_symbols:
        print(f"   {symbol.full_symbol} - {symbol.currency}")
        print(f"     Market: {symbol.market}, Type: {symbol.instrument_type.value}")
        print(f"     US Market: {symbol.is_us_market}")
    
    print(f"\n🇲🇦 Moroccan Market Symbols:")
    for symbol in moroccan_symbols:
        print(f"   {symbol.full_symbol} - {symbol.currency}")
        print(f"     Market: {symbol.market}, Type: {symbol.instrument_type.value}")
        print(f"     Moroccan Market: {symbol.is_moroccan_market}")
    
    print(f"\n💱 Forex Symbols:")
    for symbol in forex_symbols:
        print(f"   {symbol.full_symbol} - {symbol.currency}")
        print(f"     Market: {symbol.market}, Type: {symbol.instrument_type.value}")
    
    # Simulate market hours for different markets
    print(f"\n🕐 Market Hours Simulation:")
    
    current_time = datetime.utcnow()
    
    # US Market (EST)
    us_open = current_time.replace(hour=14, minute=30, second=0)  # 9:30 AM EST in UTC
    us_close = current_time.replace(hour=21, minute=0, second=0)   # 4:00 PM EST in UTC
    us_is_open = us_open <= current_time <= us_close
    
    print(f"   🇺🇸 US Market: {'OPEN' if us_is_open else 'CLOSED'}")
    print(f"      Hours: 09:30-16:00 EST (14:30-21:00 UTC)")
    
    # Moroccan Market (WET)
    morocco_open = current_time.replace(hour=9, minute=30, second=0)   # 9:30 AM WET
    morocco_close = current_time.replace(hour=15, minute=30, second=0) # 3:30 PM WET
    morocco_is_open = morocco_open <= current_time <= morocco_close
    
    print(f"   🇲🇦 Morocco Market: {'OPEN' if morocco_is_open else 'CLOSED'}")
    print(f"      Hours: 09:30-15:30 WET (09:30-15:30 UTC)")
    
    # Forex Market (24/5)
    forex_is_open = current_time.weekday() < 5  # Monday-Friday
    
    print(f"   💱 Forex Market: {'OPEN' if forex_is_open else 'CLOSED'}")
    print(f"      Hours: 24/5 (Sunday 22:00 - Friday 22:00 UTC)")


async def main():
    """Run all market data examples."""
    print("🚀 TradeSense AI Market Data Engine Examples\n")
    
    try:
        await example_1_basic_provider_setup()
        await example_2_real_time_data_retrieval()
        await example_3_historical_data_analysis()
        await example_4_websocket_subscriptions()
        await example_5_cache_and_performance()
        await example_6_data_quality_monitoring()
        await example_7_multi_market_support()
        
        print("\n✅ All market data examples completed successfully!")
    
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())