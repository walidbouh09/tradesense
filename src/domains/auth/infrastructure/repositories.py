"""Auth infrastructure repository implementations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.exceptions.base import InfrastructureError
from ..domain.entities import User
from ..domain.repositories import UserRepository
from ..domain.value_objects import Email, UserRole, AccountStatus
from .models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def save(self, aggregate: User) -> None:
        """Save a user aggregate."""
        try:
            # Check if user exists
            stmt = select(UserModel).where(UserModel.id == aggregate.id)
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing
                self._update_model_from_aggregate(existing, aggregate)
            else:
                # Create new
                model = self._create_model_from_aggregate(aggregate)
                self._session.add(model)
            
            await self._session.commit()
        except Exception as e:
            await self._session.rollback()
            raise InfrastructureError(f"Failed to save user: {e}") from e
    
    async def get_by_id(self, id: UUID) -> Optional[User]:
        """Get user by ID."""
        try:
            stmt = select(UserModel).where(UserModel.id == id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return self._create_aggregate_from_model(model)
        except Exception as e:
            raise InfrastructureError(f"Failed to get user: {e}") from e
    
    async def delete(self, aggregate: User) -> None:
        """Delete a user aggregate."""
        try:
            stmt = select(UserModel).where(UserModel.id == aggregate.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                await self._session.delete(model)
                await self._session.commit()
        except Exception as e:
            await self._session.rollback()
            raise InfrastructureError(f"Failed to delete user: {e}") from e
    
    async def find_by_email(self, email: Email) -> Optional[User]:
        """Find user by email."""
        try:
            stmt = select(UserModel).where(UserModel.email == str(email))
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return self._create_aggregate_from_model(model)
        except Exception as e:
            raise InfrastructureError(f"Failed to find user by email: {e}") from e
    
    async def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username."""
        try:
            stmt = select(UserModel).where(UserModel.username == username)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return self._create_aggregate_from_model(model)
        except Exception as e:
            raise InfrastructureError(f"Failed to find user by username: {e}") from e
    
    async def find_by_role(
        self,
        role: UserRole,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Find users by role."""
        try:
            stmt = select(UserModel).where(
                UserModel.role == role.value
            ).limit(limit).offset(offset).order_by(UserModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to find users by role: {e}") from e
    
    async def find_by_status(
        self,
        status: AccountStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Find users by status."""
        try:
            stmt = select(UserModel).where(
                UserModel.status == status.value
            ).limit(limit).offset(offset).order_by(UserModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to find users by status: {e}") from e
    
    async def search_users(
        self,
        email_pattern: Optional[str] = None,
        role: Optional[UserRole] = None,
        status: Optional[AccountStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Search users with filters."""
        try:
            stmt = select(UserModel)
            
            conditions = []
            
            if email_pattern:
                conditions.append(UserModel.email.ilike(f"%{email_pattern}%"))
            
            if role:
                conditions.append(UserModel.role == role.value)
            
            if status:
                conditions.append(UserModel.status == status.value)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.limit(limit).offset(offset).order_by(UserModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to search users: {e}") from e
    
    def _create_model_from_aggregate(self, aggregate: User) -> UserModel:
        """Create SQLAlchemy model from domain aggregate."""
        return UserModel(
            id=aggregate.id,
            username=str(aggregate.username),
            email=str(aggregate.email),
            password_hash=aggregate._password_hash,  # Access private field
            role=aggregate.role.value,
            status=aggregate.status.value,
            kyc_status=aggregate.kyc_status.value,
            email_verified=aggregate.is_email_verified,
            failed_login_count=aggregate.failed_login_count,
            last_login_at=aggregate.last_login_at,
            password_changed_at=aggregate.password_changed_at,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )
    
    def _update_model_from_aggregate(self, model: UserModel, aggregate: User) -> None:
        """Update SQLAlchemy model from domain aggregate."""
        model.username = str(aggregate.username)
        model.email = str(aggregate.email)
        model.password_hash = aggregate._password_hash
        model.role = aggregate.role.value
        model.status = aggregate.status.value
        model.kyc_status = aggregate.kyc_status.value
        model.email_verified = aggregate.is_email_verified
        model.failed_login_count = aggregate.failed_login_count
        model.last_login_at = aggregate.last_login_at
        model.password_changed_at = aggregate.password_changed_at
        model.updated_at = aggregate.updated_at
    
    def _create_aggregate_from_model(self, model: UserModel) -> User:
        """Create domain aggregate from SQLAlchemy model."""
        from ..domain.value_objects import Username, Email, UserRole, AccountStatus, KYCStatus
        
        # Create user with basic info
        user = User.__new__(User)  # Create without calling __init__
        
        # Set all attributes manually
        user._id = model.id
        user._created_at = model.created_at
        user._updated_at = model.updated_at
        user._domain_events = []
        
        user._username = Username(model.username)
        user._email = Email(model.email)
        user._password_hash = model.password_hash
        user._role = UserRole(model.role)
        user._status = AccountStatus(model.status)
        user._kyc_status = KYCStatus(model.kyc_status)
        user._email_verified = model.email_verified
        user._failed_login_count = model.failed_login_count
        user._last_login_at = model.last_login_at
        user._password_changed_at = model.password_changed_at
        
        # Initialize other fields with defaults
        user._login_attempts = []
        user._last_login_ip = None
        user._account_locked_until = None
        
        from ..domain.value_objects import SecuritySettings
        user._security_settings = SecuritySettings()
        user._active_sessions = []
        user._revoked_token_ids = []
        user._email_verification_token = None
        user._email_verification_expires_at = None
        
        return user