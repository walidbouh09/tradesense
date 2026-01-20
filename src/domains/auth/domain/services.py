"""Auth domain services."""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from ....shared.exceptions.base import BusinessRuleViolationError, ValidationError
from .entities import User
from .repositories import UserRepository
from .value_objects import AccountStatus, Email, LoginAttempt, UserRole, Username


class UserRegistrationService:
    """Domain service for user registration business rules."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def validate_registration(
        self,
        username: Username,
        email: Email,
    ) -> None:
        """Validate user registration requirements."""
        # Check username uniqueness
        if await self.user_repository.username_exists(username):
            raise BusinessRuleViolationError("Username is already taken")
        
        # Check email uniqueness
        if await self.user_repository.email_exists(email):
            raise BusinessRuleViolationError("Email is already registered")
        
        # Additional business rules can be added here
        # e.g., domain restrictions, blacklisted emails, etc.
    
    def generate_email_verification_token(self) -> str:
        """Generate secure email verification token."""
        return secrets.token_urlsafe(32)
    
    def calculate_verification_expiry(self) -> datetime:
        """Calculate email verification token expiry."""
        return datetime.utcnow() + timedelta(hours=24)


class AuthenticationService:
    """Domain service for authentication business rules."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def authenticate_user(
        self,
        username_or_email: str,
        password: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        password_hasher=None,
    ) -> User:
        """Authenticate user by username or email."""
        # Find user by username or email
        user = await self._find_user_by_login(username_or_email)
        
        if not user:
            # Don't reveal whether username/email exists
            raise BusinessRuleViolationError("Invalid credentials")
        
        # Check for suspicious activity
        self._check_suspicious_login_patterns(user, ip_address)
        
        # Authenticate
        if not user.authenticate(password, ip_address, user_agent, password_hasher):
            raise BusinessRuleViolationError("Invalid credentials")
        
        return user
    
    async def _find_user_by_login(self, username_or_email: str) -> Optional[User]:
        """Find user by username or email."""
        # Try as username first
        try:
            username = Username(username_or_email)
            user = await self.user_repository.find_by_username(username)
            if user:
                return user
        except ValidationError:
            pass  # Not a valid username format
        
        # Try as email
        try:
            email = Email(username_or_email)
            return await self.user_repository.find_by_email(email)
        except ValidationError:
            pass  # Not a valid email format
        
        return None
    
    def _check_suspicious_login_patterns(self, user: User, ip_address: str) -> None:
        """Check for suspicious login patterns."""
        recent_attempts = user.recent_login_attempts
        
        # Check for too many attempts from same IP
        ip_attempts = [
            attempt for attempt in recent_attempts
            if attempt.ip_address == ip_address and not attempt.success
        ]
        
        if len(ip_attempts) >= 10:  # 10 failed attempts from same IP in 24h
            user.detect_suspicious_activity(
                activity_type="excessive_failed_logins",
                description=f"10+ failed login attempts from IP {ip_address}",
                ip_address=ip_address,
                risk_score=70,
            )
        
        # Check for login from new location (simplified)
        if user.last_login_at and user._last_login_ip != ip_address:
            # In a real implementation, this would use geolocation
            user.detect_suspicious_activity(
                activity_type="new_location_login",
                description=f"Login from new IP address {ip_address}",
                ip_address=ip_address,
                risk_score=30,
            )


class RoleManagementService:
    """Domain service for role management business rules."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def can_assign_role(
        self,
        assigner_user: User,
        target_role: UserRole,
    ) -> bool:
        """Check if user can assign a specific role."""
        # Only admins and superadmins can assign roles
        if assigner_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
            return False
        
        # Users can only assign roles at or below their level
        return assigner_user.role.can_manage_role(target_role)
    
    async def validate_role_assignment(
        self,
        assigner_user: User,
        target_user: User,
        new_role: UserRole,
    ) -> None:
        """Validate role assignment business rules."""
        # Check if assigner can assign this role
        if not await self.can_assign_role(assigner_user, new_role):
            raise BusinessRuleViolationError(
                f"User with role {assigner_user.role.value} cannot assign role {new_role.value}"
            )
        
        # Prevent self-demotion for superadmins
        if (assigner_user.id == target_user.id and 
            assigner_user.role == UserRole.SUPERADMIN and 
            new_role != UserRole.SUPERADMIN):
            raise BusinessRuleViolationError("Superadmins cannot demote themselves")
        
        # Ensure at least one superadmin remains
        if (target_user.role == UserRole.SUPERADMIN and 
            new_role != UserRole.SUPERADMIN):
            superadmin_count = await self._count_superadmins()
            if superadmin_count <= 1:
                raise BusinessRuleViolationError("Cannot remove the last superadmin")
    
    async def _count_superadmins(self) -> int:
        """Count number of superadmin users."""
        superadmins = await self.user_repository.find_by_role(UserRole.SUPERADMIN)
        return len(superadmins)


class AccountSecurityService:
    """Domain service for account security business rules."""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def validate_status_change(
        self,
        changer_user: User,
        target_user: User,
        new_status: AccountStatus,
    ) -> None:
        """Validate account status change business rules."""
        # Only admins and superadmins can change account status
        if changer_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
            raise BusinessRuleViolationError("Insufficient permissions to change account status")
        
        # Prevent self-suspension/banning
        if changer_user.id == target_user.id and new_status in [AccountStatus.SUSPENDED, AccountStatus.BANNED]:
            raise BusinessRuleViolationError("Cannot suspend or ban your own account")
        
        # Superadmins can only be managed by other superadmins
        if (target_user.role == UserRole.SUPERADMIN and 
            changer_user.role != UserRole.SUPERADMIN):
            raise BusinessRuleViolationError("Only superadmins can manage superadmin accounts")
        
        # Validate status transition
        if target_user.status.is_terminal and new_status != target_user.status:
            raise BusinessRuleViolationError(
                f"Cannot change status from terminal state: {target_user.status.value}"
            )
    
    def calculate_password_strength_score(self, password: str) -> int:
        """Calculate password strength score (0-100)."""
        score = 0
        
        # Length scoring
        if len(password) >= 12:
            score += 25
        elif len(password) >= 8:
            score += 15
        
        # Character variety scoring
        if any(c.isupper() for c in password):
            score += 15
        if any(c.islower() for c in password):
            score += 15
        if any(c.isdigit() for c in password):
            score += 15
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 20
        
        # Complexity bonus
        char_types = sum([
            any(c.isupper() for c in password),
            any(c.islower() for c in password),
            any(c.isdigit() for c in password),
            any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password),
        ])
        
        if char_types >= 4:
            score += 10
        
        return min(score, 100)
    
    def is_password_compromised(self, password: str) -> bool:
        """Check if password appears in known breach databases."""
        # In a real implementation, this would check against
        # services like HaveIBeenPwned API or local breach databases
        
        # For now, just check against common passwords
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master",
        }
        
        return password.lower() in common_passwords
    
    async def detect_account_takeover_indicators(
        self,
        user: User,
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> List[str]:
        """Detect potential account takeover indicators."""
        indicators = []
        
        # Check for rapid password changes
        if user.password_changed_at and (datetime.utcnow() - user.password_changed_at).days < 1:
            indicators.append("Recent password change")
        
        # Check for login from new location
        if user.last_login_at and user._last_login_ip != ip_address:
            indicators.append("Login from new IP address")
        
        # Check for unusual login patterns
        recent_attempts = user.recent_login_attempts
        failed_attempts = [a for a in recent_attempts if not a.success]
        
        if len(failed_attempts) >= 3:
            indicators.append("Multiple recent failed login attempts")
        
        # Check for disabled security features
        if not user.security_settings.two_factor_method.is_enabled:
            indicators.append("Two-factor authentication disabled")
        
        return indicators


class SessionSecurityService:
    """Domain service for session security business rules."""
    
    def validate_session_creation(
        self,
        user: User,
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> None:
        """Validate session creation requirements."""
        # Check account status
        if not user.can_login:
            raise BusinessRuleViolationError("Account cannot create sessions")
        
        # Check for concurrent session limits
        active_session_count = len(user._active_sessions)
        max_sessions = 5  # Configurable limit
        
        if active_session_count >= max_sessions:
            raise BusinessRuleViolationError(f"Maximum concurrent sessions ({max_sessions}) exceeded")
    
    def calculate_session_timeout(self, user: User) -> int:
        """Calculate session timeout in seconds."""
        base_timeout = user.security_settings.session_timeout_seconds
        
        # Reduce timeout for high-privilege users
        if user.role in [UserRole.ADMIN, UserRole.SUPERADMIN]:
            return min(base_timeout, 3600)  # Max 1 hour for admins
        
        return base_timeout
    
    def should_require_reauthentication(
        self,
        user: User,
        action: str,
        last_auth_time: datetime,
    ) -> bool:
        """Determine if action requires reauthentication."""
        # High-risk actions require recent authentication
        high_risk_actions = {
            "change_password", "change_email", "disable_2fa",
            "change_role", "change_account_status", "delete_account",
        }
        
        if action in high_risk_actions:
            # Require authentication within last 15 minutes
            return (datetime.utcnow() - last_auth_time).seconds > 900
        
        return False