"""Auth application command and query handlers."""

import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import structlog

from ....infrastructure.security.authentication import JWTManager, TokenPayload
from ....infrastructure.security.authorization import RoleBasedAccessControl
from ....infrastructure.security.hashing import SecureHasher, PasswordStrengthValidator
from ....infrastructure.logging.audit_logger import AuditLogger, AuditEventType
from ....infrastructure.common.context import ExecutionContext
from ....shared.events.event_bus import EventBus
from ....shared.exceptions.base import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from ..domain.entities import User
from ..domain.repositories import UserRepository
from ..domain.value_objects import Email, Password, UserRole, UserStatus
from .commands import (
    RegisterUserCommand,
    LoginUserCommand,
    LogoutUserCommand,
    ChangePasswordCommand,
    ResetPasswordCommand,
    ActivateUserCommand,
    DeactivateUserCommand,
    AssignRoleCommand,
)
from .queries import (
    GetUserQuery,
    GetUserByEmailQuery,
    GetUserPermissionsQuery,
    ValidateTokenQuery,
)

logger = structlog.get_logger()


class RegisterUserHandler:
    """Handler for user registration."""
    
    def __init__(
        self,
        user_repository: UserRepository,
        hasher: SecureHasher,
        event_bus: EventBus,
        audit_logger: AuditLogger,
    ):
        self.user_repository = user_repository
        self.hasher = hasher
        self.event_bus = event_bus
        self.audit_logger = audit_logger
    
    async def handle(self, command: RegisterUserCommand, context: ExecutionContext) -> UUID:
        """Handle user registration command."""
        logger.info(
            "Processing user registration",
            email=command.email,
            correlation_id=context.correlation_id,
        )
        
        # Validate password strength
        validator = PasswordStrengthValidator()
        is_valid, errors = validator.validate_password_strength(command.password)
        if not is_valid:
            raise ValidationError(f"Password validation failed: {'; '.join(errors)}")
        
        # Check if user already exists
        existing_user = await self.user_repository.find_by_email(Email(command.email))
        if existing_user:
            raise BusinessRuleViolationError("User with this email already exists")
        
        # Hash password
        password_hash = self.hasher.hash_password(command.password)
        
        # Create user entity
        user = User.create(
            email=Email(command.email),
            password_hash=Password(password_hash),
            first_name=command.first_name,
            last_name=command.last_name,
            role=UserRole(command.role) if command.role else UserRole.TRADER,
        )
        
        # Save user
        await self.user_repository.save(user)
        
        # Publish domain events
        for event in user.domain_events:
            await self.event_bus.publish(event)
        user.clear_domain_events()
        
        # Log audit event
        await self.audit_logger.log_business_event(
            event_type=AuditEventType.USER_LOGIN,  # Should be USER_REGISTERED
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            action="register",
            details={
                "email": command.email,
                "role": command.role or "trader",
            },
            execution_context=context,
        )
        
        logger.info(
            "User registered successfully",
            user_id=str(user.id),
            email=command.email,
        )
        
        return user.id


class LoginUserHandler:
    """Handler for user login."""
    
    def __init__(
        self,
        user_repository: UserRepository,
        hasher: SecureHasher,
        jwt_manager: JWTManager,
        rbac: RoleBasedAccessControl,
        audit_logger: AuditLogger,
    ):
        self.user_repository = user_repository
        self.hasher = hasher
        self.jwt_manager = jwt_manager
        self.rbac = rbac
        self.audit_logger = audit_logger
    
    async def handle(
        self, 
        command: LoginUserCommand, 
        context: ExecutionContext
    ) -> Tuple[str, str, Dict[str, any]]:
        """Handle user login command."""
        logger.info(
            "Processing user login",
            email=command.email,
            ip_address=command.ip_address,
            correlation_id=context.correlation_id,
        )
        
        try:
            # Find user by email
            user = await self.user_repository.find_by_email(Email(command.email))
            if not user:
                await self._log_failed_login(
                    None, command.email, command.ip_address, 
                    "User not found", context
                )
                raise ValidationError("Invalid credentials")
            
            # Check if user is active
            if user.status != UserStatus.ACTIVE:
                await self._log_failed_login(
                    user.id, command.email, command.ip_address,
                    f"User status: {user.status.value}", context
                )
                raise BusinessRuleViolationError("User account is not active")
            
            # Verify password
            if not self.hasher.verify_password(command.password, user.password_hash.value):
                await self._log_failed_login(
                    user.id, command.email, command.ip_address,
                    "Invalid password", context
                )
                raise ValidationError("Invalid credentials")
            
            # Get user permissions
            user_permissions = await self.rbac.get_user_permissions(user.id)
            permissions = [str(perm) for perm in user_permissions.all_permissions]
            
            # Create tokens
            session_id = secrets.token_urlsafe(32)
            
            access_token = await self.jwt_manager.create_access_token(
                user_id=user.id,
                permissions=permissions,
                execution_context=context,
                session_id=session_id,
            )
            
            refresh_token = await self.jwt_manager.create_refresh_token(
                user_id=user.id,
                execution_context=context,
                session_id=session_id,
            )
            
            # Update user login timestamp
            user.record_login(command.ip_address)
            await self.user_repository.save(user)
            
            # Log successful login
            await self.audit_logger.log_authentication_event(
                event_type=AuditEventType.USER_LOGIN,
                user_id=user.id,
                success=True,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                execution_context=context,
            )
            
            user_info = {
                "user_id": str(user.id),
                "email": user.email.value,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "permissions": permissions,
                "session_id": session_id,
            }
            
            logger.info(
                "User login successful",
                user_id=str(user.id),
                email=command.email,
                ip_address=command.ip_address,
            )
            
            return access_token, refresh_token, user_info
            
        except (ValidationError, BusinessRuleViolationError):
            raise
        except Exception as e:
            logger.error(
                "Login processing error",
                email=command.email,
                error=str(e),
                correlation_id=context.correlation_id,
            )
            raise ValidationError("Login failed due to system error")
    
    async def _log_failed_login(
        self,
        user_id: Optional[UUID],
        email: str,
        ip_address: str,
        reason: str,
        context: ExecutionContext,
    ) -> None:
        """Log failed login attempt."""
        await self.audit_logger.log_authentication_event(
            event_type=AuditEventType.LOGIN_FAILED,
            user_id=user_id,
            success=False,
            ip_address=ip_address,
            failure_reason=reason,
            execution_context=context,
        )
        
        logger.warning(
            "Login attempt failed",
            user_id=str(user_id) if user_id else None,
            email=email,
            ip_address=ip_address,
            reason=reason,
        )


class LogoutUserHandler:
    """Handler for user logout."""
    
    def __init__(
        self,
        jwt_manager: JWTManager,
        audit_logger: AuditLogger,
    ):
        self.jwt_manager = jwt_manager
        self.audit_logger = audit_logger
    
    async def handle(self, command: LogoutUserCommand, context: ExecutionContext) -> None:
        """Handle user logout command."""
        logger.info(
            "Processing user logout",
            user_id=str(command.user_id),
            correlation_id=context.correlation_id,
        )
        
        # Revoke access token
        if command.access_token:
            await self.jwt_manager.revoke_token(
                token=command.access_token,
                reason="User logout",
                execution_context=context,
            )
        
        # Revoke refresh token
        if command.refresh_token:
            await self.jwt_manager.revoke_token(
                token=command.refresh_token,
                reason="User logout",
                execution_context=context,
            )
        
        # Log logout event
        await self.audit_logger.log_authentication_event(
            event_type=AuditEventType.USER_LOGOUT,
            user_id=command.user_id,
            success=True,
            execution_context=context,
        )
        
        logger.info(
            "User logout successful",
            user_id=str(command.user_id),
        )


class ChangePasswordHandler:
    """Handler for password change."""
    
    def __init__(
        self,
        user_repository: UserRepository,
        hasher: SecureHasher,
        jwt_manager: JWTManager,
        audit_logger: AuditLogger,
    ):
        self.user_repository = user_repository
        self.hasher = hasher
        self.jwt_manager = jwt_manager
        self.audit_logger = audit_logger
    
    async def handle(self, command: ChangePasswordCommand, context: ExecutionContext) -> None:
        """Handle password change command."""
        logger.info(
            "Processing password change",
            user_id=str(command.user_id),
            correlation_id=context.correlation_id,
        )
        
        # Get user
        user = await self.user_repository.get_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError("User", str(command.user_id))
        
        # Verify current password
        if not self.hasher.verify_password(command.current_password, user.password_hash.value):
            raise ValidationError("Current password is incorrect")
        
        # Validate new password strength
        validator = PasswordStrengthValidator()
        is_valid, errors = validator.validate_password_strength(command.new_password)
        if not is_valid:
            raise ValidationError(f"New password validation failed: {'; '.join(errors)}")
        
        # Hash new password
        new_password_hash = self.hasher.hash_password(command.new_password)
        
        # Update user password
        user.change_password(Password(new_password_hash))
        await self.user_repository.save(user)
        
        # Revoke all existing tokens for security
        await self.jwt_manager.revoke_all_user_tokens(
            user_id=command.user_id,
            reason="Password changed",
            execution_context=context,
        )
        
        # Log password change
        await self.audit_logger.log_authentication_event(
            event_type=AuditEventType.PASSWORD_CHANGED,
            user_id=command.user_id,
            success=True,
            execution_context=context,
        )
        
        logger.info(
            "Password changed successfully",
            user_id=str(command.user_id),
        )


class GetUserHandler:
    """Handler for getting user information."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def handle(self, query: GetUserQuery) -> Optional[User]:
        """Handle get user query."""
        return await self.user_repository.get_by_id(query.user_id)


class GetUserByEmailHandler:
    """Handler for getting user by email."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def handle(self, query: GetUserByEmailQuery) -> Optional[User]:
        """Handle get user by email query."""
        return await self.user_repository.find_by_email(Email(query.email))


class GetUserPermissionsHandler:
    """Handler for getting user permissions."""
    
    def __init__(self, rbac: RoleBasedAccessControl):
        self.rbac = rbac
    
    async def handle(self, query: GetUserPermissionsQuery) -> List[str]:
        """Handle get user permissions query."""
        user_permissions = await self.rbac.get_user_permissions(query.user_id)
        return [str(perm) for perm in user_permissions.all_permissions]


class ValidateTokenHandler:
    """Handler for token validation."""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
    
    async def handle(self, query: ValidateTokenQuery) -> TokenPayload:
        """Handle token validation query."""
        return await self.jwt_manager.validate_token(query.token)


class RefreshTokenHandler:
    """Handler for token refresh."""
    
    def __init__(
        self,
        jwt_manager: JWTManager,
        rbac: RoleBasedAccessControl,
        audit_logger: AuditLogger,
    ):
        self.jwt_manager = jwt_manager
        self.rbac = rbac
        self.audit_logger = audit_logger
    
    async def handle(
        self, 
        refresh_token: str, 
        context: ExecutionContext
    ) -> Tuple[str, str]:
        """Handle token refresh."""
        logger.info(
            "Processing token refresh",
            correlation_id=context.correlation_id,
        )
        
        # Validate refresh token
        token_payload = await self.jwt_manager.validate_token(refresh_token)
        
        if token_payload.type != "refresh":
            raise ValidationError("Invalid token type for refresh")
        
        # Get fresh user permissions
        user_permissions = await self.rbac.get_user_permissions(token_payload.user_id)
        permissions = [str(perm) for perm in user_permissions.all_permissions]
        
        # Create new tokens
        new_access_token, new_refresh_token = await self.jwt_manager.refresh_access_token(
            refresh_token=refresh_token,
            new_permissions=permissions,
            execution_context=context,
        )
        
        logger.info(
            "Token refresh successful",
            user_id=token_payload.sub,
        )
        
        return new_access_token, new_refresh_token