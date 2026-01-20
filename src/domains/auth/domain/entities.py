"""Auth domain entities."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from ....shared.kernel.entity import AggregateRoot
from .events import (
    AccountStatusChanged,
    LoginAttemptFailed,
    PasswordChanged,
    RoleChanged,
    SecuritySettingsChanged,
    SuspiciousActivityDetected,
    TokensRevoked,
    TwoFactorDisabled,
    TwoFactorEnabled,
    UserLoggedIn,
    UserLoggedOut,
    UserRegistered,
)
from .value_objects import (
    AccountStatus,
    Email,
    KYCStatus,
    LoginAttempt,
    Password,
    SecuritySettings,
    SessionToken,
    TwoFactorMethod,
    UserRole,
    Username,
)


class User(AggregateRoot):
    """User aggregate root managing authentication and authorization."""
    
    def __init__(
        self,
        username: Username,
        email: Email,
        password_hash: str,
        role: UserRole = UserRole.USER,
        id: Optional[UUID] = None,
    ) -> None:
        super().__init__(id)
        
        self._username = username
        self._email = email
        self._password_hash = password_hash
        self._role = role
        self._status = AccountStatus.PENDING
        self._kyc_status = KYCStatus.NOT_STARTED
        
        # Security tracking
        self._login_attempts: List[LoginAttempt] = []
        self._failed_login_count = 0
        self._last_login_at: Optional[datetime] = None
        self._last_login_ip: Optional[str] = None
        self._password_changed_at = datetime.utcnow()
        self._account_locked_until: Optional[datetime] = None
        
        # Security settings
        self._security_settings = SecuritySettings()
        
        # Session management
        self._active_sessions: List[SessionToken] = []
        self._revoked_token_ids: List[str] = []
        
        # Email verification
        self._email_verified = False
        self._email_verification_token: Optional[str] = None
        self._email_verification_expires_at: Optional[datetime] = None
        
        # Emit registration event
        self.add_domain_event(
            UserRegistered(
                aggregate_id=self.id,
                username=str(self._username),
                email=str(self._email),
                role=self._role.value,
            )
        )
    
    def verify_email(self, verification_token: str) -> None:
        """Verify user email with token."""
        if self._email_verified:
            raise BusinessRuleViolationError("Email is already verified")
        
        if not self._email_verification_token:
            raise BusinessRuleViolationError("No email verification token set")
        
        if self._email_verification_expires_at and datetime.utcnow() > self._email_verification_expires_at:
            raise BusinessRuleViolationError("Email verification token has expired")
        
        if self._email_verification_token != verification_token:
            raise BusinessRuleViolationError("Invalid email verification token")
        
        self._email_verified = True
        self._email_verification_token = None
        self._email_verification_expires_at = None
        
        # Activate account after email verification
        if self._status == AccountStatus.PENDING:
            self._status = AccountStatus.ACTIVE
        
        self._touch()
    
    def authenticate(
        self,
        password: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        password_hasher=None,
    ) -> bool:
        """Authenticate user with password."""
        # Check if account is locked
        if self.is_account_locked:
            raise BusinessRuleViolationError("Account is temporarily locked")
        
        # Check account status
        if not self._status.can_login:
            raise BusinessRuleViolationError(f"Cannot login with account status: {self._status.value}")
        
        # Verify password
        if not password_hasher or not password_hasher.verify_password(password, self._password_hash):
            self._record_failed_login(ip_address, user_agent, "Invalid password")
            return False
        
        # Check if password change is required
        if self._security_settings.require_password_change or self._security_settings.is_password_expired:
            raise BusinessRuleViolationError("Password change required")
        
        # Successful authentication
        self._record_successful_login(ip_address, user_agent)
        return True
    
    def login(
        self,
        ip_address: str,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Complete login process after authentication."""
        if not self._status.can_login:
            raise BusinessRuleViolationError("Cannot login with current account status")
        
        self._last_login_at = datetime.utcnow()
        self._last_login_ip = ip_address
        self._failed_login_count = 0  # Reset failed login count
        self._account_locked_until = None  # Clear any account lock
        
        # Clean up old login attempts
        self._cleanup_old_login_attempts()
        
        self._touch()
        
        # Emit login event
        self.add_domain_event(
            UserLoggedIn(
                aggregate_id=self.id,
                username=str(self._username),
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                two_factor_used=self._security_settings.two_factor_method.is_enabled,
            )
        )
    
    def logout(self, session_id: Optional[str] = None, reason: str = "user_requested") -> None:
        """Logout user and invalidate session."""
        # Remove active session if provided
        if session_id:
            self._active_sessions = [
                session for session in self._active_sessions 
                if getattr(session, 'session_id', None) != session_id
            ]
        
        self._touch()
        
        # Emit logout event
        self.add_domain_event(
            UserLoggedOut(
                aggregate_id=self.id,
                username=str(self._username),
                session_id=session_id,
                logout_reason=reason,
            )
        )
    
    def change_password(
        self,
        old_password: str,
        new_password: Password,
        ip_address: str,
        password_hasher=None,
        forced: bool = False,
    ) -> None:
        """Change user password."""
        if not forced:
            # Verify old password
            if not password_hasher or not password_hasher.verify_password(old_password, self._password_hash):
                raise BusinessRuleViolationError("Current password is incorrect")
        
        # Hash new password
        if not password_hasher:
            raise ValidationError("Password hasher is required")
        
        new_password_hash = password_hasher.hash_password(str(new_password))
        
        # Check if new password is different
        if password_hasher.verify_password(str(new_password), self._password_hash):
            raise BusinessRuleViolationError("New password must be different from current password")
        
        self._password_hash = new_password_hash
        self._password_changed_at = datetime.utcnow()
        
        # Update security settings
        self._security_settings = SecuritySettings(
            two_factor_method=self._security_settings.two_factor_method,
            login_notifications=self._security_settings.login_notifications,
            session_timeout_minutes=self._security_settings.session_timeout_minutes,
            require_password_change=False,  # Clear password change requirement
            password_expires_at=datetime.utcnow() + timedelta(days=90),  # Set new expiration
        )
        
        self._touch()
        
        # Emit password change event
        self.add_domain_event(
            PasswordChanged(
                aggregate_id=self.id,
                username=str(self._username),
                ip_address=ip_address,
                forced_change=forced,
            )
        )
    
    def change_role(self, new_role: UserRole, changed_by: UUID, reason: str) -> None:
        """Change user role."""
        if self._role == new_role:
            return  # No change needed
        
        old_role = self._role
        self._role = new_role
        self._touch()
        
        # Emit role change event
        self.add_domain_event(
            RoleChanged(
                aggregate_id=self.id,
                username=str(self._username),
                old_role=old_role.value,
                new_role=new_role.value,
                changed_by=changed_by,
                reason=reason,
            )
        )
    
    def change_status(
        self,
        new_status: AccountStatus,
        reason: str,
        changed_by: Optional[UUID] = None,
    ) -> None:
        """Change account status."""
        if self._status == new_status:
            return  # No change needed
        
        # Validate status transition
        if self._status.is_terminal and new_status != self._status:
            raise BusinessRuleViolationError(f"Cannot change status from terminal state: {self._status.value}")
        
        old_status = self._status
        self._status = new_status
        self._touch()
        
        # If suspending or banning, revoke all tokens
        if new_status in [AccountStatus.SUSPENDED, AccountStatus.BANNED]:
            self._revoke_all_tokens(reason)
        
        # Emit status change event
        self.add_domain_event(
            AccountStatusChanged(
                aggregate_id=self.id,
                username=str(self._username),
                old_status=old_status.value,
                new_status=new_status.value,
                reason=reason,
                changed_by=changed_by,
            )
        )
    
    def enable_two_factor(self, method: TwoFactorMethod, ip_address: str) -> None:
        """Enable two-factor authentication."""
        if method == TwoFactorMethod.NONE:
            raise ValidationError("Cannot enable 2FA with NONE method")
        
        old_method = self._security_settings.two_factor_method
        
        self._security_settings = SecuritySettings(
            two_factor_method=method,
            login_notifications=self._security_settings.login_notifications,
            session_timeout_minutes=self._security_settings.session_timeout_minutes,
            require_password_change=self._security_settings.require_password_change,
            password_expires_at=self._security_settings.password_expires_at,
        )
        
        self._touch()
        
        # Emit 2FA enabled event
        self.add_domain_event(
            TwoFactorEnabled(
                aggregate_id=self.id,
                username=str(self._username),
                method=method.value,
                ip_address=ip_address,
            )
        )
    
    def disable_two_factor(self, ip_address: str, reason: str = "user_requested") -> None:
        """Disable two-factor authentication."""
        if not self._security_settings.two_factor_method.is_enabled:
            return  # Already disabled
        
        old_method = self._security_settings.two_factor_method
        
        self._security_settings = SecuritySettings(
            two_factor_method=TwoFactorMethod.NONE,
            login_notifications=self._security_settings.login_notifications,
            session_timeout_minutes=self._security_settings.session_timeout_minutes,
            require_password_change=self._security_settings.require_password_change,
            password_expires_at=self._security_settings.password_expires_at,
        )
        
        self._touch()
        
        # Emit 2FA disabled event
        self.add_domain_event(
            TwoFactorDisabled(
                aggregate_id=self.id,
                username=str(self._username),
                method=old_method.value,
                ip_address=ip_address,
                reason=reason,
            )
        )
    
    def update_security_settings(
        self,
        settings: SecuritySettings,
        ip_address: str,
    ) -> None:
        """Update security settings."""
        old_settings = self._security_settings
        self._security_settings = settings
        self._touch()
        
        # Emit security settings change events for each changed setting
        if old_settings.login_notifications != settings.login_notifications:
            self.add_domain_event(
                SecuritySettingsChanged(
                    aggregate_id=self.id,
                    username=str(self._username),
                    setting_name="login_notifications",
                    old_value=str(old_settings.login_notifications),
                    new_value=str(settings.login_notifications),
                    ip_address=ip_address,
                )
            )
        
        if old_settings.session_timeout_minutes != settings.session_timeout_minutes:
            self.add_domain_event(
                SecuritySettingsChanged(
                    aggregate_id=self.id,
                    username=str(self._username),
                    setting_name="session_timeout_minutes",
                    old_value=str(old_settings.session_timeout_minutes),
                    new_value=str(settings.session_timeout_minutes),
                    ip_address=ip_address,
                )
            )
    
    def revoke_tokens(self, reason: str, revoked_by: Optional[UUID] = None) -> None:
        """Revoke all user tokens."""
        self._revoke_all_tokens(reason)
        
        # Emit tokens revoked event
        self.add_domain_event(
            TokensRevoked(
                aggregate_id=self.id,
                username=str(self._username),
                reason=reason,
                revoked_by=revoked_by,
            )
        )
    
    def detect_suspicious_activity(
        self,
        activity_type: str,
        description: str,
        ip_address: str,
        risk_score: int,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record suspicious activity detection."""
        # Emit suspicious activity event
        self.add_domain_event(
            SuspiciousActivityDetected(
                aggregate_id=self.id,
                username=str(self._username),
                activity_type=activity_type,
                description=description,
                ip_address=ip_address,
                risk_score=risk_score,
                user_agent=user_agent,
            )
        )
        
        # Auto-suspend account for high-risk activities
        if risk_score >= 80:
            self.change_status(
                AccountStatus.SUSPENDED,
                f"Suspicious activity detected: {description}",
            )
    
    def _record_failed_login(
        self,
        ip_address: str,
        user_agent: Optional[str],
        failure_reason: str,
    ) -> None:
        """Record failed login attempt."""
        attempt = LoginAttempt(
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason=failure_reason,
        )
        
        self._login_attempts.append(attempt)
        self._failed_login_count += 1
        
        # Check for account lockout
        if self._failed_login_count >= 5:
            self._account_locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        self._touch()
        
        # Emit failed login event
        self.add_domain_event(
            LoginAttemptFailed(
                aggregate_id=self.id,
                username=str(self._username),
                ip_address=ip_address,
                failure_reason=failure_reason,
                user_agent=user_agent,
                consecutive_failures=self._failed_login_count,
            )
        )
    
    def _record_successful_login(self, ip_address: str, user_agent: Optional[str]) -> None:
        """Record successful login attempt."""
        attempt = LoginAttempt(
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        
        self._login_attempts.append(attempt)
    
    def _cleanup_old_login_attempts(self) -> None:
        """Clean up old login attempts (keep last 30 days)."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        self._login_attempts = [
            attempt for attempt in self._login_attempts
            if attempt.timestamp >= cutoff
        ]
    
    def _revoke_all_tokens(self, reason: str) -> None:
        """Revoke all active tokens."""
        # In a real implementation, this would interact with the token blacklist
        # For now, we just clear active sessions
        self._active_sessions.clear()
        self._touch()
    
    # Properties
    @property
    def username(self) -> Username:
        return self._username
    
    @property
    def email(self) -> Email:
        return self._email
    
    @property
    def role(self) -> UserRole:
        return self._role
    
    @property
    def status(self) -> AccountStatus:
        return self._status
    
    @property
    def kyc_status(self) -> KYCStatus:
        return self._kyc_status
    
    @property
    def is_email_verified(self) -> bool:
        return self._email_verified
    
    @property
    def is_account_locked(self) -> bool:
        """Check if account is temporarily locked."""
        if not self._account_locked_until:
            return False
        return datetime.utcnow() < self._account_locked_until
    
    @property
    def can_login(self) -> bool:
        """Check if user can login."""
        return (
            self._status.can_login and
            not self.is_account_locked and
            self._email_verified
        )
    
    @property
    def can_trade(self) -> bool:
        """Check if user can perform trading operations."""
        return (
            self._status.can_trade and
            self._kyc_status.allows_trading
        )
    
    @property
    def security_settings(self) -> SecuritySettings:
        return self._security_settings
    
    @property
    def last_login_at(self) -> Optional[datetime]:
        return self._last_login_at
    
    @property
    def password_changed_at(self) -> datetime:
        return self._password_changed_at
    
    @property
    def failed_login_count(self) -> int:
        return self._failed_login_count
    
    @property
    def recent_login_attempts(self) -> List[LoginAttempt]:
        """Get recent login attempts (last 24 hours)."""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        return [
            attempt for attempt in self._login_attempts
            if attempt.timestamp >= cutoff
        ]