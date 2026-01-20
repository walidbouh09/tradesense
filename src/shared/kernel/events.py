"""Domain event abstractions."""

from abc import ABC
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from .value_object import ValueObject


class DomainEvent(ValueObject, ABC):
    """Base domain event."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        event_id: Optional[UUID] = None,
        occurred_at: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        self.event_id = event_id or uuid4()
        self.aggregate_id = aggregate_id
        self.occurred_at = occurred_at or datetime.utcnow()
        self.event_type = self.__class__.__name__
        
        # Store additional event data
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            **{k: v for k, v in self.__dict__.items() 
               if k not in ["event_id", "event_type", "aggregate_id", "occurred_at"]},
        }