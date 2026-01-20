"""Redis-based enhanced event bus implementation."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import redis.asyncio as redis
import structlog

from ...shared.kernel.events import DomainEvent
from ...shared.events.domain_events import create_event_from_dict
from ..common.context import ExecutionContext
from ..common.exceptions import EventBusError
from .enhanced_event_bus import EnhancedEventBus, EventWorker, WorkerStatus

logger = structlog.get_logger()


class RedisEnhancedEventBus(EnhancedEventBus):
    """Redis-based enhanced event bus with worker support."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        stream_name: str = "tradesense_events",
        consumer_group_prefix: str = "tradesense",
        max_stream_length: int = 100000,
    ):
        super().__init__()
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.consumer_group_prefix = consumer_group_prefix
        self.max_stream_length = max_stream_length
        self._consumer_tasks: Set[asyncio.Task] = set()
        self._running = False
    
    async def publish(
        self,
        event: DomainEvent,
        routing_key: Optional[str] = None,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish event to Redis stream."""
        if not self._running:
            raise EventBusError("Event bus is not running")
        
        try:
            # Serialize event to dictionary
            event_data = event.to_dict()
            
            # Add routing key if provided
            if routing_key:
                event_data["routing_key"] = routing_key
            
            # Add context information
            if context:
                event_data["context"] = {
                    "correlation_id": str(context.correlation_id),
                    "user_id": str(context.user_id) if context.user_id else None,
                    "source": context.source,
                }
            
            # Publish to Redis stream
            message_id = await self.redis_client.xadd(
                self.stream_name,
                event_data,
                maxlen=self.max_stream_length,
                approximate=True,
            )
            
            # Update metrics
            self.metrics.events_published += 1
            self.metrics.last_event_timestamp = datetime.utcnow()
            
            logger.debug(
                "Event published to Redis stream",
                event_type=event.event_type,
                event_id=str(event.event_id),
                message_id=message_id.decode(),
                stream=self.stream_name,
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event to Redis",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e),
            )
            raise EventBusError(f"Failed to publish event: {e}") from e
    
    async def publish_batch(
        self,
        events: List[DomainEvent],
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish multiple events to Redis stream."""
        if not events:
            return
        
        try:
            # Use pipeline for batch operations
            pipe = self.redis_client.pipeline()
            
            for event in events:
                event_data = event.to_dict()
                
                if context:
                    event_data["context"] = {
                        "correlation_id": str(context.correlation_id),
                        "user_id": str(context.user_id) if context.user_id else None,
                        "source": context.source,
                    }
                
                pipe.xadd(
                    self.stream_name,
                    event_data,
                    maxlen=self.max_stream_length,
                    approximate=True,
                )
            
            # Execute pipeline
            await pipe.execute()
            
            # Update metrics
            self.metrics.events_published += len(events)
            self.metrics.last_event_timestamp = datetime.utcnow()
            
            logger.info(
                "Event batch published to Redis stream",
                count=len(events),
                stream=self.stream_name,
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event batch to Redis",
                count=len(events),
                error=str(e),
            )
            raise EventBusError(f"Failed to publish event batch: {e}") from e
    
    async def start(self) -> None:
        """Start the Redis event bus."""
        if self._running:
            return
        
        self._running = True
        
        # Create consumer groups for each worker
        for worker in self.worker_registry.get_all_workers():
            await self._create_consumer_group(worker)
        
        # Start worker consumers
        await self._start_worker_consumers()
        
        # Start workers
        await self.worker_registry.start_all_workers()
        
        logger.info(
            "Redis enhanced event bus started",
            stream=self.stream_name,
            worker_count=len(self.worker_registry.get_all_workers()),
        )
    
    async def stop(self) -> None:
        """Stop the Redis event bus."""
        if not self._running:
            return
        
        self._running = False
        
        # Stop worker consumers
        for task in self._consumer_tasks:
            task.cancel()
        
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            self._consumer_tasks.clear()
        
        # Stop workers
        await self.worker_registry.stop_all_workers()
        
        logger.info("Redis enhanced event bus stopped")
    
    async def register_worker(self, worker: EventWorker) -> None:
        """Register worker and create consumer group."""
        await super().register_worker(worker)
        
        # Create consumer group if bus is running
        if self._running:
            await self._create_consumer_group(worker)
            await self._start_worker_consumer(worker)
    
    async def _create_consumer_group(self, worker: EventWorker) -> None:
        """Create Redis consumer group for worker."""
        consumer_group = f"{self.consumer_group_prefix}_{worker.consumer_group}"
        
        try:
            await self.redis_client.xgroup_create(
                self.stream_name,
                consumer_group,
                id="0",
                mkstream=True,
            )
            
            logger.debug(
                "Consumer group created",
                group=consumer_group,
                stream=self.stream_name,
                worker=worker.worker_name,
            )
            
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                logger.error(
                    "Failed to create consumer group",
                    group=consumer_group,
                    error=str(e),
                )
                raise
    
    async def _start_worker_consumers(self) -> None:
        """Start consumer tasks for all workers."""
        for worker in self.worker_registry.get_all_workers():
            await self._start_worker_consumer(worker)
    
    async def _start_worker_consumer(self, worker: EventWorker) -> None:
        """Start consumer task for specific worker."""
        task = asyncio.create_task(self._consume_events_for_worker(worker))
        self._consumer_tasks.add(task)
        
        # Clean up completed tasks
        task.add_done_callback(lambda t: self._consumer_tasks.discard(t))
    
    async def _consume_events_for_worker(self, worker: EventWorker) -> None:
        """Consume events from Redis stream for specific worker."""
        consumer_group = f"{self.consumer_group_prefix}_{worker.consumer_group}"
        consumer_name = f"{worker.worker_name}_{worker.worker_id}"
        
        logger.info(
            "Starting event consumer",
            worker=worker.worker_name,
            group=consumer_group,
            consumer=consumer_name,
        )
        
        while self._running and worker.is_running():
            try:
                # Read messages from stream
                messages = await self.redis_client.xreadgroup(
                    consumer_group,
                    consumer_name,
                    {self.stream_name: ">"},
                    count=worker.batch_size,
                    block=1000,  # Block for 1 second
                )
                
                if not messages:
                    continue
                
                # Process messages
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        await self._process_redis_message(
                            worker, msg_id, fields, consumer_group
                        )
                
            except asyncio.CancelledError:
                logger.info(
                    "Event consumer cancelled",
                    worker=worker.worker_name,
                )
                break
                
            except Exception as e:
                logger.error(
                    "Error in event consumer",
                    worker=worker.worker_name,
                    error=str(e),
                )
                
                # Wait before retrying
                await asyncio.sleep(5)
        
        logger.info(
            "Event consumer stopped",
            worker=worker.worker_name,
        )
    
    async def _process_redis_message(
        self,
        worker: EventWorker,
        msg_id: bytes,
        fields: Dict[bytes, bytes],
        consumer_group: str,
    ) -> None:
        """Process a single Redis message."""
        start_time = datetime.utcnow()
        
        try:
            # Convert bytes to strings
            event_data = {k.decode(): v.decode() for k, v in fields.items()}
            
            # Deserialize event
            event = create_event_from_dict(event_data)
            
            # Check if worker can handle this event
            if not worker.can_handle(event):
                # Acknowledge message without processing
                await self.redis_client.xack(
                    self.stream_name, consumer_group, msg_id
                )
                return
            
            # Create execution context
            context_data = event_data.get("context", {})
            if isinstance(context_data, str):
                context_data = json.loads(context_data)
            
            context = ExecutionContext(
                correlation_id=UUID(context_data.get("correlation_id", str(UUID()))),
                user_id=UUID(context_data["user_id"]) if context_data.get("user_id") else None,
                source=context_data.get("source", "redis_event_bus"),
            )
            
            # Process event with circuit breaker
            circuit_breaker = self.circuit_breakers.get(worker.worker_id)
            if circuit_breaker:
                await circuit_breaker.call(
                    self._execute_worker_with_timeout,
                    worker,
                    event,
                    context,
                )
            else:
                await self._execute_worker_with_timeout(worker, event, context)
            
            # Acknowledge successful processing
            await self.redis_client.xack(
                self.stream_name, consumer_group, msg_id
            )
            
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            worker.update_metrics(processing_time, success=True)
            self.metrics.events_processed += 1
            
            logger.debug(
                "Redis message processed successfully",
                worker=worker.worker_name,
                event_type=event.event_type,
                event_id=str(event.event_id),
                msg_id=msg_id.decode(),
                processing_time_ms=processing_time,
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            worker.update_metrics(processing_time, success=False)
            self.metrics.events_failed += 1
            
            logger.error(
                "Failed to process Redis message",
                worker=worker.worker_name,
                msg_id=msg_id.decode(),
                error=str(e),
            )
            
            # For now, acknowledge failed messages to prevent infinite retries
            # In production, you might want to implement dead letter queues
            await self.redis_client.xack(
                self.stream_name, consumer_group, msg_id
            )
    
    async def health_check(self) -> str:
        """Check Redis event bus health."""
        try:
            # Check Redis connection
            await self.redis_client.ping()
            
            # Check stream exists
            stream_info = await self.redis_client.xinfo_stream(self.stream_name)
            
            # Check worker health
            unhealthy_workers = [
                worker for worker in self.worker_registry.get_all_workers()
                if worker.status != WorkerStatus.RUNNING
            ]
            
            if unhealthy_workers:
                return "degraded"
            
            return "healthy"
            
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return "unhealthy"
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """Get Redis stream information."""
        try:
            stream_info = await self.redis_client.xinfo_stream(self.stream_name)
            
            # Convert bytes to strings for JSON serialization
            return {
                k.decode() if isinstance(k, bytes) else k: 
                v.decode() if isinstance(v, bytes) else v
                for k, v in stream_info.items()
            }
            
        except Exception as e:
            logger.error("Failed to get stream info", error=str(e))
            return {}
    
    async def get_consumer_group_info(self) -> List[Dict[str, Any]]:
        """Get consumer group information."""
        try:
            groups_info = await self.redis_client.xinfo_groups(self.stream_name)
            
            result = []
            for group_info in groups_info:
                group_dict = {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in group_info.items()
                }
                result.append(group_dict)
            
            return result
            
        except Exception as e:
            logger.error("Failed to get consumer group info", error=str(e))
            return []
    
    async def replay_events(
        self,
        from_message_id: str = "0",
        to_message_id: str = "+",
        count: Optional[int] = None,
    ) -> None:
        """Replay events from Redis stream."""
        logger.info(
            "Starting event replay",
            from_id=from_message_id,
            to_id=to_message_id,
            count=count,
        )
        
        try:
            # Read events from stream
            messages = await self.redis_client.xrange(
                self.stream_name,
                min=from_message_id,
                max=to_message_id,
                count=count,
            )
            
            replayed_count = 0
            
            for msg_id, fields in messages:
                try:
                    # Convert and deserialize event
                    event_data = {k.decode(): v.decode() for k, v in fields.items()}
                    event = create_event_from_dict(event_data)
                    
                    # Republish event (this will create new message ID)
                    await self.publish(event)
                    replayed_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to replay event",
                        msg_id=msg_id.decode(),
                        error=str(e),
                    )
            
            logger.info(
                "Event replay completed",
                replayed_count=replayed_count,
                total_messages=len(messages),
            )
            
        except Exception as e:
            logger.error("Event replay failed", error=str(e))
            raise EventBusError(f"Event replay failed: {e}") from e