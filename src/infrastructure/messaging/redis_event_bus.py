"""Redis-based event bus implementation."""

import json
from typing import List

import redis.asyncio as redis
import structlog

from ...shared.events.event_bus import EventBus
from ...shared.kernel.events import DomainEvent

logger = structlog.get_logger()


class RedisEventBus(EventBus):
    """Redis-based event bus implementation."""
    
    def __init__(self, redis_client: redis.Redis, stream_name: str = "domain_events") -> None:
        self._redis = redis_client
        self._stream_name = stream_name
    
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        try:
            event_data = event.to_dict()
            
            # Add to Redis stream
            await self._redis.xadd(
                self._stream_name,
                event_data,
                maxlen=10000,  # Keep last 10k events
                approximate=True,
            )
            
            logger.info(
                "Domain event published",
                event_type=event.event_type,
                event_id=str(event.event_id),
                aggregate_id=str(event.aggregate_id),
            )
        
        except Exception as e:
            logger.error(
                "Failed to publish domain event",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e),
            )
            raise
    
    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple domain events."""
        if not events:
            return
        
        try:
            # Use pipeline for batch operations
            pipe = self._redis.pipeline()
            
            for event in events:
                event_data = event.to_dict()
                pipe.xadd(
                    self._stream_name,
                    event_data,
                    maxlen=10000,
                    approximate=True,
                )
            
            await pipe.execute()
            
            logger.info(
                "Domain events batch published",
                count=len(events),
                event_types=[event.event_type for event in events],
            )
        
        except Exception as e:
            logger.error(
                "Failed to publish domain events batch",
                count=len(events),
                error=str(e),
            )
            raise