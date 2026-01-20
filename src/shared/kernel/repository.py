"""Repository pattern abstractions."""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar
from uuid import UUID

from .entity import AggregateRoot

T = TypeVar("T", bound=AggregateRoot)


class Repository(ABC, Generic[T]):
    """Base repository interface."""
    
    @abstractmethod
    async def save(self, aggregate: T) -> None:
        """Save an aggregate."""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get aggregate by ID."""
        pass
    
    @abstractmethod
    async def delete(self, aggregate: T) -> None:
        """Delete an aggregate."""
        pass


class ReadOnlyRepository(ABC, Generic[T]):
    """Base read-only repository interface."""
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get aggregate by ID."""
        pass
    
    @abstractmethod
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Find all aggregates with pagination."""
        pass