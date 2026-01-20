"""
Repository Interfaces for Challenge Engine.

These are abstract interfaces that define the contract for persistence operations.
Concrete implementations belong in the infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain.challenge import Challenge
from ..domain.value_objects import ChallengeId


class ChallengeRepository(ABC):
    """
    Repository interface for Challenge aggregates.

    Handles persistence and retrieval of challenge aggregates with optimistic locking.
    """

    @abstractmethod
    async def save(self, challenge: Challenge) -> None:
        """
        Save a challenge aggregate.

        Args:
            challenge: The challenge aggregate to save

        Raises:
            OptimisticLockException: If version conflict detected
            RepositoryException: For other persistence errors
        """
        pass

    @abstractmethod
    async def get_by_id(self, challenge_id: ChallengeId) -> Optional[Challenge]:
        """
        Get a challenge by ID.

        Args:
            challenge_id: The challenge identifier

        Returns:
            Challenge aggregate or None if not found
        """
        pass

    @abstractmethod
    async def exists(self, challenge_id: ChallengeId) -> bool:
        """
        Check if a challenge exists.

        Args:
            challenge_id: The challenge identifier

        Returns:
            True if challenge exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_challenges_by_trader(
        self,
        trader_id: str,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Challenge]:
        """
        Get challenges for a trader with optional filtering.

        Args:
            trader_id: The trader identifier
            status_filter: Optional status filter (ACTIVE, FAILED, FUNDED)
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of challenge aggregates
        """
        pass

    @abstractmethod
    async def get_version(self, challenge_id: ChallengeId) -> Optional[int]:
        """
        Get the current version of a challenge for optimistic locking.

        Args:
            challenge_id: The challenge identifier

        Returns:
            Current version number or None if not found
        """
        pass