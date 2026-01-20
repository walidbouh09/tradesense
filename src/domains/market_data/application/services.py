"""Market data application services."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import structlog

from ..domain.entities import (
    DataAggregator,
    DataProvider,
    Market,
    MarketDataPoint,
    OHLCV,
    OrderBook,
    Trade,
    MarketNews,
    CacheEntry,
    RateLimiter,
)
from ..domain.value_objects import (
    MarketDataRequest,
    MarketDataResponse,
    DataQualityMetrics,
    AggregationRule,
    MarketDataSubscription,
)
from ...shared.kernel.events import DomainEvent
from ....infrastructure.messaging.event_bus import EventBus

logger = structlog.get_logger()


class MarketDataService:
    """Core market data service for data retrieval and management."""
    
    def __init__(
        self,
        providers: List[DataProvider],
        aggregator: DataAggregator,
        cache_service: 'CacheService',
        rate_limiter: RateLimiter,
        event_bus: EventBus,
    ):
        self.providers = {p.name: p for p in providers}
        self.aggregator = aggregator
        self.cache_service = cache_service
        self.rate_limiter = rate_limiter
        self.event_bus = event_bus
        self.active_subscriptions: Dict[str, MarketDataSubscription] = {}
    
    async def get_real_time_data(
        self,
        symbols: List[str],
        data_types: List[str],
        preferred_providers: Optional[List[str]] = None,
    ) -> MarketDataResponse:
        """Get real-time market data."""
        request = MarketDataRequest(
            symbols=symbols,
            data_types=data_types,
            preferred_providers=preferred_providers,
        )
        
        # Check cache first
        cache_key = request.get_cache_key()
        cached_data = await self.cache_service.get(cache_key)
        
        if cached_data and not cached_data.is_expired:
            logger.debug("Serving real-time data from cache", symbols=symbols)
            return MarketDataResponse(
                request_id=request.request_id,
                data=cached_data.data,
                metadata={"source": "cache"},
                timestamp=cached_data.timestamp,
                latency_ms=0,
                provider=cached_data.provider,
                quality=cached_data.quality.value,
                cached=True,
            )
        
        # Get data from providers
        start_time = datetime.utcnow()
        
        try:
            aggregated_data = await self._aggregate_real_time_data(request)
            
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            response = MarketDataResponse(
                request_id=request.request_id,
                data=aggregated_data["data"],
                metadata=aggregated_data["metadata"],
                timestamp=datetime.utcnow(),
                latency_ms=latency_ms,
                provider=aggregated_data["primary_provider"],
                quality=aggregated_data["quality"],
                cached=False,
            )
            
            # Cache the response
            await self.cache_service.set(
                cache_key,
                response.data,
                ttl_seconds=30,  # Short TTL for real-time data
                provider=response.provider,
                data_type="real_time",
                quality=response.quality,
            )
            
            return response
            
        except Exception as e:
            logger.error("Failed to get real-time data", error=str(e), symbols=symbols)
            return MarketDataResponse(
                request_id=request.request_id,
                data={},
                metadata={},
                timestamp=datetime.utcnow(),
                latency_ms=0,
                provider="",
                quality="error",
                errors=[str(e)],
            )
    
    async def get_historical_data(
        self,
        symbols: List[str],
        data_types: List[str],
        start_time: datetime,
        end_time: datetime,
        timeframe: str = "1D",
        preferred_providers: Optional[List[str]] = None,
    ) -> MarketDataResponse:
        """Get historical market data."""
        request = MarketDataRequest(
            symbols=symbols,
            data_types=data_types,
            start_time=start_time,
            end_time=end_time,
            timeframe=timeframe,
            preferred_providers=preferred_providers,
        )
        
        # Check cache first
        cache_key = request.get_cache_key()
        cached_data = await self.cache_service.get(cache_key)
        
        if cached_data and not cached_data.is_expired:
            logger.debug("Serving historical data from cache", symbols=symbols)
            return MarketDataResponse(
                request_id=request.request_id,
                data=cached_data.data,
                metadata={"source": "cache"},
                timestamp=cached_data.timestamp,
                latency_ms=0,
                provider=cached_data.provider,
                quality=cached_data.quality.value,
                cached=True,
            )
        
        # Get data from providers
        start_request_time = datetime.utcnow()
        
        try:
            aggregated_data = await self._aggregate_historical_data(request)
            
            latency_ms = int((datetime.utcnow() - start_request_time).total_seconds() * 1000)
            
            response = MarketDataResponse(
                request_id=request.request_id,
                data=aggregated_data["data"],
                metadata=aggregated_data["metadata"],
                timestamp=datetime.utcnow(),
                latency_ms=latency_ms,
                provider=aggregated_data["primary_provider"],
                quality=aggregated_data["quality"],
                cached=False,
            )
            
            # Cache the response with longer TTL for historical data
            await self.cache_service.set(
                cache_key,
                response.data,
                ttl_seconds=3600,  # 1 hour TTL for historical data
                provider=response.provider,
                data_type="historical",
                quality=response.quality,
            )
            
            return response
            
        except Exception as e:
            logger.error("Failed to get historical data", error=str(e), symbols=symbols)
            return MarketDataResponse(
                request_id=request.request_id,
                data={},
                metadata={},
                timestamp=datetime.utcnow(),
                latency_ms=0,
                provider="",
                quality="error",
                errors=[str(e)],
            )
    
    async def subscribe_real_time(
        self,
        subscription: MarketDataSubscription,
    ) -> bool:
        """Subscribe to real-time data updates."""
        try:
            # Store subscription
            self.active_subscriptions[subscription.subscription_id] = subscription
            
            # Start WebSocket connections for required providers
            await self._start_websocket_subscriptions(subscription)
            
            logger.info(
                "Real-time subscription created",
                subscription_id=subscription.subscription_id,
                symbols=subscription.symbols,
                data_types=subscription.data_types,
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to create real-time subscription",
                subscription_id=subscription.subscription_id,
                error=str(e),
            )
            return False
    
    async def unsubscribe_real_time(self, subscription_id: str) -> bool:
        """Unsubscribe from real-time data updates."""
        try:
            if subscription_id in self.active_subscriptions:
                subscription = self.active_subscriptions[subscription_id]
                
                # Stop WebSocket connections
                await self._stop_websocket_subscriptions(subscription)
                
                # Remove subscription
                del self.active_subscriptions[subscription_id]
                
                logger.info(
                    "Real-time subscription removed",
                    subscription_id=subscription_id,
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                "Failed to remove real-time subscription",
                subscription_id=subscription_id,
                error=str(e),
            )
            return False
    
    async def _aggregate_real_time_data(self, request: MarketDataRequest) -> Dict:
        """Aggregate real-time data from multiple providers."""
        # Get best providers for this request
        providers = self._select_providers(request)
        
        # Fetch data from providers concurrently
        tasks = []
        for provider in providers:
            if self.rate_limiter.can_make_request():
                task = self._fetch_from_provider(provider, request)
                tasks.append(task)
        
        if not tasks:
            raise Exception("No available providers or rate limit exceeded")
        
        # Wait for all providers to respond
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = [
            result for result in results
            if not isinstance(result, Exception) and result is not None
        ]
        
        if not successful_results:
            raise Exception("All providers failed to return data")
        
        # Aggregate the results
        return self._merge_provider_results(successful_results, "real_time")
    
    async def _aggregate_historical_data(self, request: MarketDataRequest) -> Dict:
        """Aggregate historical data from multiple providers."""
        # Get best providers for this request
        providers = self._select_providers(request)
        
        # For historical data, we might use primary provider first
        primary_provider = providers[0] if providers else None
        
        if not primary_provider:
            raise Exception("No suitable providers available")
        
        # Try primary provider first
        if self.rate_limiter.can_make_request():
            try:
                result = await self._fetch_from_provider(primary_provider, request)
                if result:
                    return {
                        "data": result["data"],
                        "metadata": result["metadata"],
                        "primary_provider": primary_provider.name,
                        "quality": result.get("quality", "good"),
                    }
            except Exception as e:
                logger.warning(
                    "Primary provider failed, trying fallback",
                    provider=primary_provider.name,
                    error=str(e),
                )
        
        # Try fallback providers
        for provider in providers[1:]:
            if self.rate_limiter.can_make_request():
                try:
                    result = await self._fetch_from_provider(provider, request)
                    if result:
                        return {
                            "data": result["data"],
                            "metadata": result["metadata"],
                            "primary_provider": provider.name,
                            "quality": result.get("quality", "good"),
                        }
                except Exception as e:
                    logger.warning(
                        "Fallback provider failed",
                        provider=provider.name,
                        error=str(e),
                    )
        
        raise Exception("All providers failed to return historical data")
    
    def _select_providers(self, request: MarketDataRequest) -> List[DataProvider]:
        """Select best providers for the request."""
        # Start with preferred providers if specified
        if request.preferred_providers:
            preferred = [
                self.providers[name] for name in request.preferred_providers
                if name in self.providers and self.providers[name].is_active
            ]
            if preferred:
                return preferred
        
        # Get all suitable providers
        suitable_providers = []
        for provider in self.providers.values():
            if not provider.is_active:
                continue
            
            # Check if provider supports required markets
            symbols_markets = [self._get_market_for_symbol(symbol) for symbol in request.symbols]
            if not all(provider.supports_market(market) for market in symbols_markets):
                continue
            
            # Check if provider supports required data types
            if not all(provider.supports_data_type(dt) for dt in request.data_types):
                continue
            
            suitable_providers.append(provider)
        
        # Sort by quality score
        suitable_providers.sort(key=lambda p: p.quality_score, reverse=True)
        
        return suitable_providers[:3]  # Return top 3 providers
    
    def _get_market_for_symbol(self, symbol: str) -> str:
        """Determine market for symbol."""
        # Simple heuristic - in production, this would use a symbol master
        if "." in symbol:
            exchange = symbol.split(".")[-1]
            if exchange.upper() in ["CSE", "CASABLANCA"]:
                return "MOROCCO"
        
        return "US"  # Default to US market
    
    async def _fetch_from_provider(self, provider: DataProvider, request: MarketDataRequest) -> Optional[Dict]:
        """Fetch data from specific provider."""
        # This would be implemented by specific provider adapters
        # For now, return mock data
        
        logger.debug(
            "Fetching data from provider",
            provider=provider.name,
            symbols=request.symbols,
            data_types=request.data_types,
        )
        
        # Simulate API call delay
        await asyncio.sleep(0.1)
        
        # Mock response
        return {
            "data": {
                symbol: {
                    "price": 100.0,
                    "volume": 1000,
                    "timestamp": datetime.utcnow().isoformat(),
                } for symbol in request.symbols
            },
            "metadata": {
                "provider": provider.name,
                "timestamp": datetime.utcnow().isoformat(),
                "symbols_count": len(request.symbols),
            },
            "quality": "good",
        }
    
    def _merge_provider_results(self, results: List[Dict], data_type: str) -> Dict:
        """Merge results from multiple providers."""
        if not results:
            return {"data": {}, "metadata": {}, "primary_provider": "", "quality": "poor"}
        
        # For now, use the first result as primary
        primary_result = results[0]
        
        # In production, this would implement sophisticated merging logic
        # based on aggregation rules, quality scores, timestamps, etc.
        
        return {
            "data": primary_result["data"],
            "metadata": {
                **primary_result["metadata"],
                "sources_count": len(results),
                "aggregation_method": "primary_with_fallback",
            },
            "primary_provider": primary_result["metadata"]["provider"],
            "quality": primary_result.get("quality", "good"),
        }
    
    async def _start_websocket_subscriptions(self, subscription: MarketDataSubscription) -> None:
        """Start WebSocket connections for subscription."""
        # This would start WebSocket connections to relevant providers
        logger.info(
            "Starting WebSocket subscriptions",
            subscription_id=subscription.subscription_id,
            symbols=subscription.symbols,
        )
    
    async def _stop_websocket_subscriptions(self, subscription: MarketDataSubscription) -> None:
        """Stop WebSocket connections for subscription."""
        # This would stop WebSocket connections
        logger.info(
            "Stopping WebSocket subscriptions",
            subscription_id=subscription.subscription_id,
        )


class CacheService:
    """Market data caching service."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.local_cache: Dict[str, CacheEntry] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get data from cache."""
        # Try local cache first
        if key in self.local_cache:
            entry = self.local_cache[key]
            if not entry.is_expired:
                entry.access()
                self.cache_stats["hits"] += 1
                return entry
            else:
                # Remove expired entry
                del self.local_cache[key]
        
        # Try Redis cache if available
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(key)
                if cached_data:
                    # Deserialize and return
                    # Implementation would deserialize the cached data
                    self.cache_stats["hits"] += 1
                    return None  # Placeholder
            except Exception as e:
                logger.warning("Redis cache get failed", key=key, error=str(e))
        
        self.cache_stats["misses"] += 1
        return None
    
    async def set(
        self,
        key: str,
        data: Dict,
        ttl_seconds: int,
        provider: str,
        data_type: str,
        quality: str,
    ) -> None:
        """Set data in cache."""
        entry = CacheEntry(
            key=key,
            data=data,
            timestamp=datetime.utcnow(),
            ttl_seconds=ttl_seconds,
            provider=provider,
            data_type=data_type,
            quality=quality,
        )
        
        # Store in local cache
        self.local_cache[key] = entry
        
        # Store in Redis if available
        if self.redis_client:
            try:
                # Serialize and store
                await self.redis_client.setex(key, ttl_seconds, str(data))
            except Exception as e:
                logger.warning("Redis cache set failed", key=key, error=str(e))
        
        self.cache_stats["sets"] += 1
        
        # Cleanup local cache if too large
        if len(self.local_cache) > 10000:
            await self._cleanup_local_cache()
    
    async def invalidate(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        # Remove from local cache
        keys_to_remove = [key for key in self.local_cache.keys() if pattern in key]
        for key in keys_to_remove:
            del self.local_cache[key]
        
        # Remove from Redis if available
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(f"*{pattern}*")
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning("Redis cache invalidation failed", pattern=pattern, error=str(e))
        
        logger.info("Cache invalidated", pattern=pattern, keys_removed=len(keys_to_remove))
    
    async def _cleanup_local_cache(self) -> None:
        """Cleanup local cache by removing expired and least accessed entries."""
        # Remove expired entries
        expired_keys = [
            key for key, entry in self.local_cache.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            del self.local_cache[key]
        
        # If still too large, remove least accessed entries
        if len(self.local_cache) > 8000:
            # Sort by access count and age
            entries_by_usage = sorted(
                self.local_cache.items(),
                key=lambda x: (x[1].access_count, x[1].last_accessed),
            )
            
            # Remove bottom 20%
            remove_count = len(entries_by_usage) // 5
            for key, _ in entries_by_usage[:remove_count]:
                del self.local_cache[key]
                self.cache_stats["evictions"] += 1
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_rate_percent": hit_rate,
            "local_cache_size": len(self.local_cache),
            "total_requests": total_requests,
        }


class DataQualityService:
    """Service for monitoring and reporting data quality."""
    
    def __init__(self):
        self.quality_metrics: Dict[str, List[DataQualityMetrics]] = {}
        self.quality_thresholds = {
            "latency_ms": 1000,
            "completeness_percent": 95.0,
            "accuracy_score": 0.95,
            "freshness_seconds": 60,
            "error_rate": 0.05,
        }
    
    async def record_quality_metrics(
        self,
        provider: str,
        symbol: str,
        data_type: str,
        latency_ms: int,
        completeness_percent: float,
        accuracy_score: float,
        freshness_seconds: int,
        error_rate: float,
        sample_size: int,
    ) -> None:
        """Record quality metrics for provider."""
        metrics = DataQualityMetrics(
            provider=provider,
            symbol=symbol,
            data_type=data_type,
            timestamp=datetime.utcnow(),
            latency_ms=latency_ms,
            completeness_percent=completeness_percent,
            accuracy_score=accuracy_score,
            freshness_seconds=freshness_seconds,
            error_rate=error_rate,
            sample_size=sample_size,
        )
        
        key = f"{provider}_{symbol}_{data_type}"
        if key not in self.quality_metrics:
            self.quality_metrics[key] = []
        
        self.quality_metrics[key].append(metrics)
        
        # Keep only last 100 metrics per key
        if len(self.quality_metrics[key]) > 100:
            self.quality_metrics[key] = self.quality_metrics[key][-100:]
        
        # Check for quality issues
        await self._check_quality_thresholds(metrics)
    
    async def _check_quality_thresholds(self, metrics: DataQualityMetrics) -> None:
        """Check if metrics exceed quality thresholds."""
        issues = []
        
        if metrics.latency_ms > self.quality_thresholds["latency_ms"]:
            issues.append(f"High latency: {metrics.latency_ms}ms")
        
        if metrics.completeness_percent < self.quality_thresholds["completeness_percent"]:
            issues.append(f"Low completeness: {metrics.completeness_percent}%")
        
        if metrics.accuracy_score < self.quality_thresholds["accuracy_score"]:
            issues.append(f"Low accuracy: {metrics.accuracy_score}")
        
        if metrics.freshness_seconds > self.quality_thresholds["freshness_seconds"]:
            issues.append(f"Stale data: {metrics.freshness_seconds}s")
        
        if metrics.error_rate > self.quality_thresholds["error_rate"]:
            issues.append(f"High error rate: {metrics.error_rate}")
        
        if issues:
            logger.warning(
                "Data quality issues detected",
                provider=metrics.provider,
                symbol=metrics.symbol,
                data_type=metrics.data_type,
                issues=issues,
            )
    
    def get_quality_report(
        self,
        provider: Optional[str] = None,
        symbol: Optional[str] = None,
        data_type: Optional[str] = None,
        hours: int = 24,
    ) -> Dict:
        """Generate quality report."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        relevant_metrics = []
        for key, metrics_list in self.quality_metrics.items():
            for metrics in metrics_list:
                if metrics.timestamp < cutoff_time:
                    continue
                
                if provider and metrics.provider != provider:
                    continue
                
                if symbol and metrics.symbol != symbol:
                    continue
                
                if data_type and metrics.data_type != data_type:
                    continue
                
                relevant_metrics.append(metrics)
        
        if not relevant_metrics:
            return {"message": "No metrics found for criteria"}
        
        # Calculate aggregated metrics
        avg_latency = sum(m.latency_ms for m in relevant_metrics) / len(relevant_metrics)
        avg_completeness = sum(m.completeness_percent for m in relevant_metrics) / len(relevant_metrics)
        avg_accuracy = sum(m.accuracy_score for m in relevant_metrics) / len(relevant_metrics)
        avg_freshness = sum(m.freshness_seconds for m in relevant_metrics) / len(relevant_metrics)
        avg_error_rate = sum(m.error_rate for m in relevant_metrics) / len(relevant_metrics)
        avg_quality_score = sum(m.overall_quality_score for m in relevant_metrics) / len(relevant_metrics)
        
        return {
            "period_hours": hours,
            "metrics_count": len(relevant_metrics),
            "average_latency_ms": avg_latency,
            "average_completeness_percent": avg_completeness,
            "average_accuracy_score": avg_accuracy,
            "average_freshness_seconds": avg_freshness,
            "average_error_rate": avg_error_rate,
            "overall_quality_score": avg_quality_score,
            "quality_grade": self._get_grade_from_score(avg_quality_score),
        }
    
    def _get_grade_from_score(self, score: float) -> str:
        """Convert quality score to grade."""
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