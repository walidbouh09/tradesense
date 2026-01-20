"""
Internal Event Bus with WebSocket Broadcasting

Enhanced event bus that forwards domain events to WebSocket clients.
Maintains simple emit API while adding real-time broadcasting capability.

Architecture:
- Domain events → Event Bus → Multiple handlers (including WebSocket)
- WebSocket emission happens AFTER domain state changes
- Clean separation: domain logic emits events, infrastructure broadcasts them

Future Extensibility:
- Replace with Redis pub/sub for distributed systems
- Replace with RabbitMQ for reliable messaging
- Replace with Kafka for high-throughput event streaming
- Add event versioning and schema validation
- Add event deduplication and idempotency
- Add event persistence for audit trails
"""

from typing import Any, Dict, List, Callable, Optional
from dataclasses import dataclass


@dataclass
class EventHandler:
    """Registered event handler."""
    event_type: str
    handler: Callable[[Any], None]
    priority: int = 0  # For future ordering


class EventBus:
    """
    Enhanced internal event bus with WebSocket broadcasting support.

    Simple publish-subscribe pattern for domain events with real-time output.
    All operations are synchronous for simplicity.
    """

    def __init__(self):
        """Initialize empty event bus."""
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._websocket_forwarder = None

    def emit(self, event_type: str, payload: Any) -> None:
        """
        Emit an event to all registered handlers.

        Args:
            event_type: String identifier for the event type
            payload: Event payload (can be any object)
        """
        if event_type in self._handlers:
            # Sort handlers by priority (higher priority first)
            sorted_handlers = sorted(
                self._handlers[event_type],
                key=lambda h: h.priority,
                reverse=True
            )

            # Call each handler
            for handler in sorted_handlers:
                try:
                    handler.handler(payload)
                except Exception as e:
                    # Log error but don't stop processing other handlers
                    # In production, this would use proper logging
                    print(f"Event handler error for {event_type}: {e}")
                    # Continue processing other handlers

        # Forward to WebSocket if configured
        # This happens AFTER all domain handlers complete
        if self._websocket_forwarder:
            try:
                self._websocket_forwarder(event_type, payload)
            except Exception as e:
                # WebSocket failures should not affect domain logic
                print(f"WebSocket forwarding error for {event_type}: {e}")

    def subscribe(self, event_type: str, handler: Callable[[Any], None], priority: int = 0) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Event type to subscribe to
            handler: Function to call when event is emitted
            priority: Handler priority (higher numbers called first)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(EventHandler(event_type, handler, priority))

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Event type to unsubscribe from
            handler: Handler function to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type]
                if h.handler != handler
            ]

    def set_websocket_forwarder(self, forwarder: Callable[[str, Any], None]) -> None:
        """
        Set the WebSocket forwarding function.

        This allows the event bus to forward events to WebSocket clients
        without importing SocketIO in domain code.

        Args:
            forwarder: Function that takes (event_type, payload) and emits to WebSocket
        """
        self._websocket_forwarder = forwarder

    def clear_websocket_forwarder(self) -> None:
        """Clear the WebSocket forwarder. Useful for testing."""
        self._websocket_forwarder = None

    def clear(self) -> None:
        """Clear all event handlers and WebSocket forwarder. Useful for testing."""
        self._handlers.clear()
        self._websocket_forwarder = None

    def get_handler_count(self, event_type: Optional[str] = None) -> int:
        """
        Get count of registered handlers.

        Args:
            event_type: Specific event type, or None for all handlers

        Returns:
            Number of registered handlers
        """
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(handlers) for handlers in self._handlers.values())


# Global event bus instance
# This is the single source of truth for domain events
event_bus = EventBus()