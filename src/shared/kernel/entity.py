"""Base entity and aggregate root abstractions."""

from abc import ABC
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID, uuid4

from .events import DomainEvent


class Entity(ABC):
    """Base entity with identity."""
    
    def __init__(self, id: Optional[UUID] = None) -> None:
        self._id = id or uuid4()
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
    
    @property
    def id(self) -> UUID:
        return self._id
    
    @property
    def created_at(self) -> datetime:
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        return self._updated_at
    
    def _touch(self) -> None:
        """Update the updated_at timestamp."""
        self._updated_at = datetime.utcnow()
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id
    
    def __hash__(self) -> int:
        return hash(self._id)


class AggregateRoot(Entity):
    """Aggregate root that can emit domain events."""
    
    def __init__(self, id: Optional[UUID] = None) -> None:
        super().__init__(id)
        self._domain_events: List[DomainEvent] = []
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Add a domain event to be published."""
        self._domain_events.append(event)
    
    def clear_domain_events(self) -> None:
        """Clear all domain events (called after publishing)."""
        self._domain_events.clear()
    
    @property
    def domain_events(self) -> List[DomainEvent]:
        """Get all pending domain events."""
        return self._domain_events.copy()