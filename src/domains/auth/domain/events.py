"""Auth domain events."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from ....shared.kernel.events import DomainEvent


class UserRegistered(DomainEvent):
    """Event emitted when a new user registers."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        email: str,
        role: str,
        registration_ip: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            email=email,
            role=role,
            registration_ip=registration_ip,
            **kwargs,
        )


class UserLoggedIn(DomainEvent):
    """Event emitted when user successfully logs in."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        two_factor_used: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            two_factor_used=two_factor_used,
            **kwargs,
        )


class UserLoggedOut(DomainEvent):
    """Event emitted when user logs out."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        session_id: Optional[str] = None,
        logout_reason: str = "user_requested",
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            session_id=session_id,
            logout_reason=logout_reason,
            **kwargs,
        )


class LoginAttemptFailed(DomainEvent):
    """Event emitted when login attempt fails."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        ip_address: str,
        failure_reason: str,
        user_agent: Optional[str] = None,
        consecutive_failures: int = 1,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            ip_address=ip_address,
            failure_reason=failure_reason,
            user_agent=user_agent,
            consecutive_failures=consecutive_failures,
            **kwargs,
        )


class AccountStatusChanged(DomainEvent):
    """Event emitted when account status changes."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        old_status: str,
        new_status: str,
        reason: str,
        changed_by: Optional[UUID] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by=str(changed_by) if changed_by else None,
            **kwargs,
        )


class PasswordChanged(DomainEvent):
    """Event emitted when user changes password."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        ip_address: str,
        forced_change: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            ip_address=ip_address,
            forced_change=forced_change,
            **kwargs,
        )


class RoleChanged(DomainEvent):
    """Event emitted when user role changes."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        old_role: str,
        new_role: str,
        changed_by: UUID,
        reason: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            old_role=old_role,
            new_role=new_role,
            changed_by=str(changed_by),
            reason=reason,
            **kwargs,
        )


class TwoFactorEnabled(DomainEvent):
    """Event emitted when 2FA is enabled."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        method: str,
        ip_address: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            method=method,
            ip_address=ip_address,
            **kwargs,
        )


class TwoFactorDisabled(DomainEvent):
    """Event emitted when 2FA is disabled."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        method: str,
        ip_address: str,
        reason: str = "user_requested",
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            method=method,
            ip_address=ip_address,
            reason=reason,
            **kwargs,
        )


class TokensRevoked(DomainEvent):
    """Event emitted when user tokens are revoked."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        reason: str,
        revoked_by: Optional[UUID] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            reason=reason,
            revoked_by=str(revoked_by) if revoked_by else None,
            session_id=session_id,
            **kwargs,
        )


class SecuritySettingsChanged(DomainEvent):
    """Event emitted when security settings change."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        setting_name: str,
        old_value: str,
        new_value: str,
        ip_address: str,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            setting_name=setting_name,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            **kwargs,
        )


class SuspiciousActivityDetected(DomainEvent):
    """Event emitted when suspicious activity is detected."""
    
    def __init__(
        self,
        aggregate_id: UUID,
        username: str,
        activity_type: str,
        description: str,
        ip_address: str,
        risk_score: int,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            aggregate_id=aggregate_id,
            username=username,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            risk_score=risk_score,
            user_agent=user_agent,
            **kwargs,
        )