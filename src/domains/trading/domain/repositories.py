"""Trading domain repository interfaces."""

from abc import abstractmethod
from typing import List, Optional
from uuid import UUID

from ....shared.kernel.repository import Repository
from .entities import Order
from .value_objects import OrderStatus, Symbol


class OrderRepository(Repository[Order]):
    """Order repository interface."""
    
    @abstractmethod
    async def find_by_user_id(
        self,
        user_id: UUID,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Find orders by user ID with optional status filter."""
        pass
    
    @abstractmethod
    async def find_by_symbol(
        self,
        symbol: Symbol,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Find orders by symbol with optional status filter."""
        pass
    
    @abstractmethod
    async def find_active_orders(self, user_id: UUID) -> List[Order]:
        """Find all active (non-terminal) orders for a user."""
        pass