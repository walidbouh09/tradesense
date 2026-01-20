"""Evaluation domain repository interfaces."""

from abc import abstractmethod
from typing import List, Optional
from uuid import UUID

from ....shared.kernel.repository import Repository
from .entities import Challenge
from .value_objects import ChallengeState, ChallengeType


class ChallengeRepository(Repository[Challenge]):
    """Challenge repository interface."""
    
    @abstractmethod
    async def find_by_trader_id(
        self,
        trader_id: UUID,
        state: Optional[ChallengeState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Challenge]:
        """Find challenges by trader ID with optional state filter."""
        pass
    
    @abstractmethod
    async def find_active_challenges(self) -> List[Challenge]:
        """Find all active challenges for monitoring."""
        pass
    
    @abstractmethod
    async def find_expiring_challenges(self, hours_ahead: int = 24) -> List[Challenge]:
        """Find challenges expiring within specified hours."""
        pass
    
    @abstractmethod
    async def find_by_challenge_type(
        self,
        challenge_type: ChallengeType,
        state: Optional[ChallengeState] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Challenge]:
        """Find challenges by type with optional state filter."""
        pass
    
    @abstractmethod
    async def get_trader_statistics(self, trader_id: UUID) -> dict:
        """Get challenge statistics for a trader."""
        pass