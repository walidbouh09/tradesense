"""In-memory event bus implementation for development and testing."""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID

import structlog

from ...shared.kernel.events import DomainEvent
from ..common.context import ExecutionContext
from ..common.exceptions import EventBusError
from .event_bus import EventBus, EventBusHealth, EventHandler, EventSubscription

logger = structlog.get_logger()


class InMemoryEventStore:
    """In-memory event store for replay and debugging."""
    
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events: List[tuple[DomainEvent, datetime]] = []
        self.events_by_type: Dict[str, List[tuple[DomainEvent, datetime]]] = {}
        self.events_by_aggregate: Dict[UUID, List[tuple[DomainEvent, datetime]]] = {}
    
    def store_event(self, event: DomainEvent) -> None:
        """Store event in memory."""
        timestamp = datetime.utcnow()
        event_tuple = (event, timestamp)
        
        # Store in main list
        self.events.append(event_tuple)
        
        # Store by type
        if event.event_type not in self.events_by_type:
            self.events_by_type[event.event_type] = []
        self.events_by_type[event.event_type].append(event_tuple)
        
        # Store by aggregate
        if event.aggregate_id not in self.events_by_aggregate:
            self.events_by_aggregate[event.aggregate_id] = []
        self.events_by_aggregate[event.aggregate_id].append(event_tuple)
        
        # Cleanup old events if needed
        if len(self.events) > self.max_events:
            self._cleanup_old_events()
    
    def _cleanup_old_events(self) -> None:
        """Remove oldest events to maintain size limit."""
        # Remove oldest 10% of events
        remove_count = self.max_events // 10
        
        # Remove from main list
        removed_events = self.events[:remove_count]
        self.events = self.events[remove_count:]
        
        # Remove from type and aggregate indexes
        for event, _ in removed_events:
            # Remove from type index
            type_events = self.events_by_type.get(event.event_type, [])
            self.events_by_type[event.event_type] = [
                (e, t) for e, t in type_events if e.event_id != event.event_id
            ]
            
            # Remove from aggregate index
            aggregate_events = self.events_by_aggregate.get(event.aggregate_id, [])
            self.events_by_aggregate[event.aggregate_id] = [
                (e, t) for e, t in aggregate_events if e.event_id != event.event_id
            ]
    
    def get_events_by_type(self, event_type: str) -> List[DomainEvent]:
        """Get all events of specific type."""
        return [event for event, _ in self.events_by_type.get(event_type, [])]
    
    def get_events_by_aggregate(self, aggregate_id: UUID) -> List[DomainEvent]:
        """Get all events for specific aggregate."""
        return [event for event, _ in self.events_by_aggregate.get(aggregate_id, [])]
    
    def get_events_since(self, timestamp: datetime) -> List[DomainEvent]:
        """Get all events since timestamp."""
        return [
            event for event, event_time in self.events 
            if event_time >= timestamp
        ]
    
    def get_all_events(self) -> List[DomainEvent]:
        """Get all stored events."""
        return [event for event, _ in self.events]


class InMemoryEventBus(EventBus):
    """In-memory event bus for development and testing."""
    
    def __init__(self, enable_event_store: bool = True):
        super().__init__()
        self.enable_event_store = enable_event_store
        self.event_store = InMemoryEventStore() if enable_event_store else None
        self.dead_letter_queue: List[tuple[DomainEvent, Exception]] = []
        self._running = False
        self._processing_tasks: Set[asyncio.Task] = set()
    
    async def publish(
        self,
        event: DomainEvent,
        routing_key: Optional[str] = None,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish single event to in-memory subscribers."""
        if not self._running:
            raise EventBusError("Event bus is not running")
        
        try:
            # Store event if enabled
            if self.event_store:
                self.event_store.store_event(event)
            
            # Update metrics
            self.metrics.events_published += 1
            self.metrics.last_event_timestamp = datetime.utcnow()
            
            # Get subscriptions for this event type
            subscriptions = self.get_subscriptions(event.event_type)
            
            if not subscriptions:
                logger.debug(
                    "No subscribers for event",
                    event_type=event.event_type,
                    event_id=str(event.event_id),
                )
                return
            
            # Create execution context if not provided
            if context is None:
                context = ExecutionContext.create_for_worker("in_memory_event_bus")
            
            # Process subscriptions asynchronously
            tasks = []
            for subscription in subscriptions:
                if subscription.handler.can_handle(event):
                    task = asyncio.create_task(
                        self._handle_event_with_retry(event, subscription, context)
                    )
                    tasks.append(task)
                    self._processing_tasks.add(task)
            
            # Wait for all handlers to complete
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clean up completed tasks
            self._processing_tasks = {
                task for task in self._processing_tasks if not task.done()
            }
            
            logger.debug(
                "Event published and processed",
                event_type=event.event_type,
                event_id=str(event.event_id),
                handlers_count=len(tasks),
            )
            
        except Exception as e:
            logger.error(
                "Event publishing failed",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e),
            )
            raise EventBusError(f"Event publishing failed: {e}") from e
    
    async def publish_batch(
        self,
        events: List[DomainEvent],
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish multiple events."""
        if not events:
            return
        
        logger.debug("Publishing event batch", count=len(events))
        
        # Publish events sequentially to maintain order
        for event in events:
            await self.publish(event, context=context)
        
        logger.debug("Event batch published", count=len(events))
    
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        consumer_group: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Subscribe to event type with handler."""
        subscription = EventSubscription(
            event_type=event_type,
            handler=handler,
            consumer_group=consumer_group,
            **kwargs,
        )
        
        self.add_subscription(subscription)
        
        logger.info(
            "Handler subscribed to event type",
            event_type=event_type,
            handler=handler.handler_name,
            consumer_group=consumer_group,
        )
    
    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe handler from event type."""
        if event_type in self.subscriptions:
            self.subscriptions[event_type] = [
                sub for sub in self.subscriptions[event_type]
                if sub.handler != handler
            ]
            
            # Remove empty subscription lists
            if not self.subscriptions[event_type]:
                del self.subscriptions[event_type]
        
        logger.info(
            "Handler unsubscribed from event type",
            event_type=event_type,
            handler=handler.handler_name,
        )
    
    async def start(self) -> None:
        """Start event bus processing."""
        if self._running:
            return
        
        self._running = True
        self._set_health_status(EventBusHealth.HEALTHY)
        
        logger.info("In-memory event bus started")
    
    async def stop(self) -> None:
        """Stop event bus processing."""
        if not self._running:
            return
        
        self._running = False
        
        # Wait for all processing tasks to complete
        if self._processing_tasks:
            logger.info(
                "Waiting for event processing tasks to complete",
                task_count=len(self._processing_tasks),
            )
            
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            self._processing_tasks.clear()
        
        self._set_health_status(EventBusHealth.UNHEALTHY)
        
        logger.info("In-memory event bus stopped")
    
    async def health_check(self) -> EventBusHealth:
        """Check event bus health."""
        if not self._running:
            return EventBusHealth.UNHEALTHY
        
        # Check if there are too many failed events
        if self.metrics.events_failed > 0:
            failure_rate = self.metrics.events_failed / max(1, self.metrics.events_published)
            if failure_rate > 0.1:  # More than 10% failure rate
                return EventBusHealth.DEGRADED
        
        # Check dead letter queue size
        if len(self.dead_letter_queue) > 100:
            return EventBusHealth.DEGRADED
        
        return EventBusHealth.HEALTHY
    
    async def _send_to_dead_letter_queue(
        self,
        event: DomainEvent,
        subscription: EventSubscription,
        exception: Exception,
    ) -> None:
        """Send failed event to dead letter queue."""
        await super()._send_to_dead_letter_queue(event, subscription, exception)
        
        # Store in in-memory dead letter queue
        self.dead_letter_queue.append((event, exception))
        
        # Limit dead letter queue size
        if len(self.dead_letter_queue) > 1000:
            self.dead_letter_queue = self.dead_letter_queue[-500:]  # Keep last 500
    
    async def replay_events(
        self,
        from_timestamp: Optional[datetime] = None,
        event_type: Optional[str] = None,
        aggregate_id: Optional[UUID] = None,
    ) -> None:
        """Replay events for recovery or testing."""
        if not self.event_store:
            raise EventBusError("Event store is not enabled")
        
        # Get events to replay
        if aggregate_id:
            events = self.event_store.get_events_by_aggregate(aggregate_id)
        elif event_type:
            events = self.event_store.get_events_by_type(event_type)
        elif from_timestamp:
            events = self.event_store.get_events_since(from_timestamp)
        else:
            events = self.event_store.get_all_events()
        
        logger.info(
            "Replaying events",
            count=len(events),
            from_timestamp=from_timestamp.isoformat() if from_timestamp else None,
            event_type=event_type,
            aggregate_id=str(aggregate_id) if aggregate_id else None,
        )
        
        # Replay events
        for event in events:
            await self.publish(event)
        
        logger.info("Event replay completed", count=len(events))
    
    def get_dead_letter_queue(self) -> List[tuple[DomainEvent, Exception]]:
        """Get dead letter queue contents."""
        return self.dead_letter_queue.copy()
    
    def clear_dead_letter_queue(self) -> None:
        """Clear dead letter queue."""
        cleared_count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        self.metrics.dead_letter_queue_size = 0
        
        logger.info("Dead letter queue cleared", cleared_count=cleared_count)
    
    def get_event_store(self) -> Optional[InMemoryEventStore]:
        """Get event store for debugging."""
        return self.event_store