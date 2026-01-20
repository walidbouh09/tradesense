"""Auth domain repository interfaces."""

from abc import abstractmethod
from typing import List, Optional
from uuid import UUID

from ....shared.kernel.repository import Repository
from .entities import User
from .value_objects import AccountStatus, Email, UserRole, Username


class UserRepository(Repository[User]):
    """User repository interface."""
    
    @abstractmethod
    async def find_by_username(self, username: Username) -> Optional[User]:
        """Find user by username."""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: Email) -> Optional[User]:
        """Find user by email."""
        pass
    
    @abstractmethod
    async def find_by_email_verification_token(self, token: str) -> Optional[User]:
        """Find user by email verification token."""
        pass
    
    @abstractmethod
    async def username_exists(self, username: Username) -> bool:
        """Check if username already exists."""
        pass
    
    @abstractmethod
    async def email_exists(self, email: Email) -> bool:
        """Check if email already exists."""
        pass
    
    @abstractmethod
    async def find_by_status(
        self,
        status: AccountStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Find users by account status."""
        pass
    
    @abstractmethod
    async def find_by_role(
        self,
        role: UserRole,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Find users by role."""
        pass
    
    @abstractmethod
    async def find_users_with_failed_logins(
        self,
        min_failed_attempts: int = 3,
        limit: int = 100,
    ) -> List[User]:
        """Find users with multiple failed login attempts."""
        pass
    
    @abstractmethod
    async def find_inactive_users(
        self,
        days_inactive: int = 90,
        limit: int = 100,
    ) -> List[User]:
        """Find users who haven't logged in for specified days."""
        pass
    
    @abstractmethod
    async def count_users_by_status(self) -> dict[AccountStatus, int]:
        """Count users by account status."""
        pass
    
    @abstractmethod
    async def count_users_by_role(self) -> dict[UserRole, int]:
        """Count users by role."""
        pass