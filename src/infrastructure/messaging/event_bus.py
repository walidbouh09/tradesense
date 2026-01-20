"""Event bus abstraction with pluggable implementations and reliability patterns."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import structlog
from pydantic import BaseModel

from ...shared.kernel.events import DomainEvent
from ..common.context import ExecutionContext
from ..common.exceptions import EventBusError, EventHandlingError

logger = structlog.get_logger()


class EventBusHealth(Enum):
    """Event bus health status."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class EventBusMetrics(BaseModel):
    """Event bus metrics for monitoring."""
    
    events_published: int = 0
    events_processed: int = 0
    events_failed: int = 0
    average_processing_time_ms: float = 0.0
    dead_letter_queue_size: int = 0
    last_event_timestamp: Optional[datetime] = None


class EventHandler(ABC):
    """Abstract event handler interface."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle a domain event."""
        pass
    
    @abstractmethod
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can handle the event."""
        pass
    
    @property
    @abstractmethod
    def handler_name(self) -> str:
        """Get handler name for logging and monitoring."""
        pass
    
    @property
    def max_retries(self) -> int:
        """Maximum retry attempts for failed events."""
        return 3
    
    @property
    def retry_delay_seconds(self) -> int:
        """Delay between retry attempts."""
        return 5


class EventSubscription(BaseModel):
    """Event subscription configuration."""
    
    event_type: str
    handler: EventHandler
    consumer_group: Optional[str] = None
    max_retries: int = 3
    retry_delay_seconds: int = 5
    dead_letter_enabled: bool = True
    
    class Config:
        arbitrary_types_allowed = True


class EventBus(ABC):
    """Abstract event bus for reliable message delivery."""
    
    def __init__(self):
        self.subscriptions: Dict[str, List[EventSubscription]] = {}
        self.metrics = EventBusMetrics()
        self._health_status = EventBusHealth.HEALTHY
    
    @abstractmethod
    async def publish(
        self, 
        event: DomainEvent, 
        routing_key: Optional[str] = None,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish single event."""
        pass
    
    @abstractmethod
    async def publish_batch(
        self, 
        events: List[DomainEvent],
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish multiple events atomically."""
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        consumer_group: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Subscribe to event type with handler."""
        pass
    
    @abstractmethod
    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe handler from event type."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start event bus processing."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop event bus processing."""
        pass
    
    @abstractmethod
    async def health_check(self) -> EventBusHealth:
        """Check event bus health."""
        pass
    
    def add_subscription(self, subscription: EventSubscription) -> None:
        """Add event subscription."""
        if subscription.event_type not in self.subscriptions:
            self.subscriptions[subscription.event_type] = []
        
        self.subscriptions[subscription.event_type].append(subscription)
        
        logger.info(
            "Event subscription added",
            event_type=subscription.event_type,
            handler=subscription.handler.handler_name,
            consumer_group=subscription.consumer_group,
        )
    
    def get_subscriptions(self, event_type: str) -> List[EventSubscription]:
        """Get subscriptions for event type."""
        return self.subscriptions.get(event_type, [])
    
    async def _handle_event_with_retry(
        self,
        event: DomainEvent,
        subscription: EventSubscription,
        context: ExecutionContext,
    ) -> None:
        """Handle event with retry logic."""
        handler = subscription.handler
        max_retries = subscription.max_retries
        retry_delay = subscription.retry_delay_seconds
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                start_time = datetime.utcnow()
                
                await handler.handle(event, context)
                
                # Update metrics
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                self.metrics.events_processed += 1
                self._update_average_processing_time(processing_time)
                
                logger.debug(
                    "Event handled successfully",
                    event_type=event.event_type,
                    event_id=str(event.event_id),
                    handler=handler.handler_name,
                    attempt=attempt + 1,
                    processing_time_ms=processing_time,
                )
                
                return  # Success
                
            except Exception as e:
                last_exception = e
                
                logger.warning(
                    "Event handling failed",
                    event_type=event.event_type,
                    event_id=str(event.event_id),
                    handler=handler.handler_name,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                )
                
                if attempt < max_retries:
                    # Wait before retry
                    import asyncio
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    # Max retries exceeded
                    self.metrics.events_failed += 1
                    
                    if subscription.dead_letter_enabled:
                        await self._send_to_dead_letter_queue(event, subscription, last_exception)
                    
                    raise EventHandlingError(
                        f"Event handling failed after {max_retries} retries: {last_exception}"
                    ) from last_exception
    
    def _update_average_processing_time(self, processing_time_ms: float) -> None:
        """Update average processing time metric."""
        if self.metrics.events_processed == 1:
            self.metrics.average_processing_time_ms = processing_time_ms
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_processing_time_ms = (
                alpha * processing_time_ms + 
                (1 - alpha) * self.metrics.average_processing_time_ms
            )
    
    async def _send_to_dead_letter_queue(
        self,
        event: DomainEvent,
        subscription: EventSubscription,
        exception: Exception,
    ) -> None:
        """Send failed event to dead letter queue."""
        self.metrics.dead_letter_queue_size += 1
        
        logger.error(
            "Event sent to dead letter queue",
            event_type=event.event_type,
            event_id=str(event.event_id),
            handler=subscription.handler.handler_name,
            error=str(exception),
        )
        
        # In a real implementation, this would persist the event
        # to a dead letter queue for manual processing
    
    def get_metrics(self) -> EventBusMetrics:
        """Get event bus metrics."""
        return self.metrics
    
    def get_health_status(self) -> EventBusHealth:
        """Get current health status."""
        return self._health_status
    
    def _set_health_status(self, status: EventBusHealth) -> None:
        """Set health status."""
        if self._health_status != status:
            logger.info(
                "Event bus health status changed",
                old_status=self._health_status.value,
                new_status=status.value,
            )
            self._health_status = status


class EventFilter:
    """Event filtering for conditional subscriptions."""
    
    def __init__(self, conditions: Dict[str, Any]):
        self.conditions = conditions
    
    def matches(self, event: DomainEvent) -> bool:
        """Check if event matches filter conditions."""
        event_dict = event.to_dict()
        
        for key, expected_value in self.conditions.items():
            if key not in event_dict:
                return False
            
            actual_value = event_dict[key]
            
            if isinstance(expected_value, dict):
                # Handle operators
                if "$eq" in expected_value:
                    if actual_value != expected_value["$eq"]:
                        return False
                elif "$in" in expected_value:
                    if actual_value not in expected_value["$in"]:
                        return False
                elif "$regex" in expected_value:
                    import re
                    if not re.match(expected_value["$regex"], str(actual_value)):
                        return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True


class ConditionalEventHandler(EventHandler):
    """Event handler with filtering conditions."""
    
    def __init__(self, base_handler: EventHandler, event_filter: EventFilter):
        self.base_handler = base_handler
        self.event_filter = event_filter
    
    async def handle(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle event if it matches filter conditions."""
        if self.event_filter.matches(event):
            await self.base_handler.handle(event, context)
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if handler can handle event."""
        return (
            self.base_handler.can_handle(event) and 
            self.event_filter.matches(event)
        )
    
    @property
    def handler_name(self) -> str:
        """Get handler name."""
        return f"conditional_{self.base_handler.handler_name}"