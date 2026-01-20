"""Event bus abstraction for domain event publishing."""

from abc import ABC, abstractmethod
from typing import List

from ..kernel.events import DomainEvent


class EventBus(ABC):
    """Abstract event bus for publishing domain events."""
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        pass
    
    @abstractmethod
    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """Publish multiple domain events."""
        pass


class EventHandler(ABC):
    """Abstract event handler."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle a domain event."""
        pass
    
    @abstractmethod
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this handler can handle the event."""
        pass