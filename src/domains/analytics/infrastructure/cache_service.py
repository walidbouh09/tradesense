"""
Analytics Caching Service

Provides Redis-based caching for:
- Leaderboard snapshots
- Trader performance data
- Query result caching
- Cache invalidation strategies
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

import redis.asyncio as redis

from ..domain.read_models import LeaderboardEntry, AnalyticsMetadata


class AnalyticsCacheService:
    """Redis-based caching service for analytics data."""

    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl_seconds: int = 3600,  # 1 hour
        leaderboard_ttl_seconds: int = 300,  # 5 minutes
    ):
        self.redis = redis_client
        self.default_ttl = default_ttl_seconds
        self.leaderboard_ttl = leaderboard_ttl_seconds

    async def store_leaderboard_entry(self, entry: LeaderboardEntry) -> None:
        """Store leaderboard entry in cache."""
        key = self._leaderboard_key(entry.metric_type, entry.period, entry.challenge_type)
        field = f"rank:{entry.rank}"

        entry_data = {
            "rank": entry.rank,
            "trader_id": entry.trader_id,
            "username": entry.username,
            "metric_value": str(entry.metric_value),
            "metric_type": entry.metric_type,
            "period": entry.period,
            "challenge_type": entry.challenge_type,
            "total_challenges": entry.total_challenges,
            "pass_rate": str(entry.pass_rate),
            "trading_days": entry.trading_days,
            "rank_change": entry.rank_change,
            "value_change": str(entry.value_change),
            "last_updated": entry.last_updated.isoformat(),
        }

        await self.redis.hset(key, field, json.dumps(entry_data))
        await self.redis.expire(key, self.leaderboard_ttl)

    async def get_leaderboard_entries(
        self,
        metric_type: str,
        period: str,
        challenge_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[LeaderboardEntry]:
        """Get leaderboard entries from cache."""
        key = self._leaderboard_key(metric_type, period, challenge_type)

        # Get all entries for this leaderboard
        entries_data = await self.redis.hgetall(key)
        if not entries_data:
            return []

        # Parse and sort by rank
        entries = []
        for field, data_json in entries_data.items():
            try:
                data = json.loads(data_json)
                entry = LeaderboardEntry(
                    rank=data["rank"],
                    trader_id=data["trader_id"],
                    username=data["username"],
                    metric_value=Decimal(data["metric_value"]),
                    metric_type=data["metric_type"],
                    period=data["period"],
                    challenge_type=data.get("challenge_type"),
                    total_challenges=data["total_challenges"],
                    pass_rate=Decimal(data["pass_rate"]),
                    trading_days=data["trading_days"],
                    rank_change=data["rank_change"],
                    value_change=Decimal(data["value_change"]),
                    last_updated=datetime.fromisoformat(data["last_updated"]),
                )
                entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue  # Skip malformed entries

        # Sort by rank
        entries.sort(key=lambda x: x.rank)
        return entries[:limit]

    async def store_trader_performance(self, trader_id: str, performance_data: Dict[str, Any]) -> None:
        """Cache trader performance data."""
        key = f"trader_performance:{trader_id}"
        await self.redis.setex(key, self.default_ttl, json.dumps(performance_data))

    async def get_trader_performance(self, trader_id: str) -> Optional[Dict[str, Any]]:
        """Get cached trader performance."""
        key = f"trader_performance:{trader_id}"
        data = await self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    async def store_query_result(self, query_key: str, result: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache query results."""
        key = f"query:{query_key}"
        ttl_seconds = ttl or self.default_ttl
        await self.redis.setex(key, ttl_seconds, json.dumps(result))

    async def get_query_result(self, query_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached query result."""
        key = f"query:{query_key}"
        data = await self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    async def invalidate_trader_cache(self, trader_id: str) -> None:
        """Invalidate all cache entries for a trader."""
        pattern = f"trader_performance:{trader_id}"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

    async def invalidate_leaderboard_cache(self, metric_type: Optional[str] = None, period: Optional[str] = None) -> None:
        """Invalidate leaderboard cache."""
        pattern = "leaderboard:*"
        if metric_type:
            pattern += f"*{metric_type}*"
        if period:
            pattern += f"*{period}*"

        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

    async def update_metadata(self, metadata: Optional[AnalyticsMetadata] = None) -> None:
        """Update analytics metadata in cache."""
        if not metadata:
            # Create default metadata
            metadata = AnalyticsMetadata(
                last_full_recalculation=datetime.utcnow(),
                total_traders=0,
                total_challenges=0,
                total_trades=0,
            )

        key = "analytics_metadata"
        metadata_data = {
            "last_full_recalculation": metadata.last_full_recalculation.isoformat(),
            "total_traders": metadata.total_traders,
            "total_challenges": metadata.total_challenges,
            "total_trades": metadata.total_trades,
            "cache_hit_rate": str(metadata.cache_hit_rate),
            "average_calculation_time": metadata.average_calculation_time,
            "last_updated": datetime.utcnow().isoformat(),
        }

        await self.redis.setex(key, self.default_ttl * 24, json.dumps(metadata_data))  # 24 hour TTL

    async def get_metadata(self) -> Optional[AnalyticsMetadata]:
        """Get analytics metadata from cache."""
        key = "analytics_metadata"
        data = await self.redis.get(key)
        if data:
            try:
                metadata_dict = json.loads(data)
                return AnalyticsMetadata(
                    last_full_recalculation=datetime.fromisoformat(metadata_dict["last_full_recalculation"]),
                    total_traders=metadata_dict["total_traders"],
                    total_challenges=metadata_dict["total_challenges"],
                    total_trades=metadata_dict["total_trades"],
                    cache_hit_rate=Decimal(metadata_dict["cache_hit_rate"]),
                    average_calculation_time=metadata_dict["average_calculation_time"],
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                return None
        return None

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        info = await self.redis.info()
        keys = await self.redis.keys("*")

        # Count keys by type
        key_counts = {}
        for key in keys[:1000]:  # Sample first 1000 keys
            key_str = key.decode() if isinstance(key, bytes) else key
            key_type = key_str.split(":")[0]
            key_counts[key_type] = key_counts.get(key_type, 0) + 1

        return {
            "redis_info": {
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_days": info.get("uptime_in_days", 0),
            },
            "key_counts": key_counts,
            "total_keys_sampled": len(keys[:1000]),
            "cache_timestamp": datetime.utcnow().isoformat(),
        }

    def _leaderboard_key(self, metric_type: str, period: str, challenge_type: Optional[str]) -> str:
        """Generate Redis key for leaderboard."""
        key_parts = ["leaderboard", metric_type, period]
        if challenge_type:
            key_parts.append(challenge_type)
        return ":".join(key_parts)

    async def warmup_leaderboard_cache(self, metric_types: List[str], periods: List[str]) -> None:
        """Warm up leaderboard cache by pre-calculating common queries."""
        # This would be called periodically to ensure popular leaderboards are cached
        # Implementation would depend on the query service
        pass

    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries (Redis does this automatically)."""
        # Redis automatically expires keys, but we can implement monitoring
        return 0