"""Auth domain value objects."""

import re
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from ....shared.exceptions.base import ValidationError
from ....shared.kernel.value_object import ValueObject


class UserRole(Enum):
    """User role enumeration with hierarchical permissions."""
    
    USER = "USER"
    ADMIN = "ADMIN"
    SUPERADMIN = "SUPERADMIN"
    
    @property
    def permissions(self) -> List[str]:
        """Get permissions for this role."""
        permission_map = {
            UserRole.USER: [
                "order:create", "order:read", "order:cancel",
                "position:read", "account:read",
            ],
            UserRole.ADMIN: [
                "order:create", "order:read", "order:cancel", "order:update",
                "position:read", "account:read", "account:update",
                "user:read", "audit:read",
            ],
            UserRole.SUPERADMIN: [
                "order:*", "position:*", "account:*", "user:*", 
                "audit:*", "system:*", "config:*",
            ],
        }
        return permission_map.get(self, [])
    
    @property
    def level(self) -> int:
        """Get role hierarchy level."""
        levels = {
            UserRole.USER: 1,
            UserRole.ADMIN: 2,
            UserRole.SUPERADMIN: 3,
        }
        return levels.get(self, 0)
    
    def can_manage_role(self, other_role: "UserRole") -> bool:
        """Check if this role can manage another role."""
        return self.level > other_role.level


class AccountStatus(Enum):
    """Account status enumeration."""
    
    PENDING = "PENDING"          # Account created, email verification pending
    ACTIVE = "ACTIVE"            # Account active and operational
    SUSPENDED = "SUSPENDED"      # Temporarily suspended (can be reactivated)
    BANNED = "BANNED"            # Permanently banned
    CLOSED = "CLOSED"            # Account closed by user request
    
    @property
    def can_login(self) -> bool:
        """Check if user can login with this status."""
        return self in [AccountStatus.ACTIVE]
    
    @property
    def can_trade(self) -> bool:
        """Check if user can perform trading operations."""
        return self == AccountStatus.ACTIVE
    
    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal status (cannot be changed)."""
        return self in [AccountStatus.BANNED, AccountStatus.CLOSED]


class Email(ValueObject):
    """Email value object with validation."""
    
    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Email cannot be empty")
        
        self.value = value.lower().strip()
        
        # Email validation regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.value):
            raise ValidationError("Invalid email format")
        
        # Additional security checks
        if len(self.value) > 254:  # RFC 5321 limit
            raise ValidationError("Email address too long")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'\.{2,}',  # Multiple consecutive dots
            r'^\.|\.$',  # Starting or ending with dot
            r'@.*@',  # Multiple @ symbols
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, self.value):
                raise ValidationError("Invalid email format")
    
    def __str__(self) -> str:
        return self.value
    
    @property
    def domain(self) -> str:
        """Get email domain."""
        return self.value.split('@')[1]
    
    @property
    def local_part(self) -> str:
        """Get email local part."""
        return self.value.split('@')[0]


class Username(ValueObject):
    """Username value object with validation."""
    
    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValidationError("Username cannot be empty")
        
        self.value = value.strip()
        
        # Username validation
        if len(self.value) < 3:
            raise ValidationError("Username must be at least 3 characters")
        
        if len(self.value) > 50:
            raise ValidationError("Username cannot exceed 50 characters")
        
        # Only allow alphanumeric, underscore, and hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.value):
            raise ValidationError("Username can only contain letters, numbers, underscore, and hyphen")
        
        # Must start with letter or number
        if not re.match(r'^[a-zA-Z0-9]', self.value):
            raise ValidationError("Username must start with a letter or number")
        
        # Check for reserved usernames
        reserved_usernames = {
            'admin', 'administrator', 'root', 'system', 'api', 'support',
            'help', 'info', 'contact', 'sales', 'marketing', 'security',
            'compliance', 'audit', 'test', 'demo', 'guest', 'anonymous',
        }
        
        if self.value.lower() in reserved_usernames:
            raise ValidationError("Username is reserved")
    
    def __str__(self) -> str:
        return self.value


class Password(ValueObject):
    """Password value object with strength validation."""
    
    def __init__(self, value: str) -> None:
        if not value:
            raise ValidationError("Password cannot be empty")
        
        self.value = value
        self._validate_strength()
    
    def _validate_strength(self) -> None:
        """Validate password strength for financial security."""
        errors = []
        
        # Length requirement
        if len(self.value) < 12:
            errors.append("Password must be at least 12 characters long")
        
        if len(self.value) > 128:
            errors.append("Password cannot exceed 128 characters")
        
        # Character requirements
        if not any(c.isupper() for c in self.value):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in self.value):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in self.value):
            errors.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in self.value):
            errors.append("Password must contain at least one special character")
        
        # Common password patterns
        common_patterns = [
            "password", "123456", "qwerty", "admin", "user",
            "login", "welcome", "secret", "default", "trading",
        ]
        
        password_lower = self.value.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                errors.append(f"Password cannot contain common pattern: {pattern}")
        
        # Sequential characters
        if self._has_sequential_chars():
            errors.append("Password cannot contain sequential characters")
        
        # Repeated characters
        if self._has_repeated_chars():
            errors.append("Password cannot contain more than 2 repeated characters")
        
        if errors:
            raise ValidationError("; ".join(errors))
    
    def _has_sequential_chars(self) -> bool:
        """Check for sequential characters."""
        for i in range(2, len(self.value)):
            if (ord(self.value[i]) == ord(self.value[i-1]) + 1 and 
                ord(self.value[i]) == ord(self.value[i-2]) + 2):
                return True
        return False
    
    def _has_repeated_chars(self) -> bool:
        """Check for repeated characters."""
        for i in range(2, len(self.value)):
            if (self.value[i] == self.value[i-1] == self.value[i-2]):
                return True
        return False
    
    def __str__(self) -> str:
        return "***MASKED***"  # Never expose password in logs


class SessionToken(ValueObject):
    """Session token value object."""
    
    def __init__(self, token: str, expires_at: datetime) -> None:
        if not token or not token.strip():
            raise ValidationError("Token cannot be empty")
        
        if expires_at <= datetime.utcnow():
            raise ValidationError("Token expiration must be in the future")
        
        self.token = token.strip()
        self.expires_at = expires_at
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() >= self.expires_at
    
    @property
    def expires_in_seconds(self) -> int:
        """Get seconds until expiration."""
        if self.is_expired:
            return 0
        
        delta = self.expires_at - datetime.utcnow()
        return int(delta.total_seconds())
    
    def __str__(self) -> str:
        return f"Token(expires_at={self.expires_at.isoformat()})"


class LoginAttempt(ValueObject):
    """Login attempt tracking value object."""
    
    def __init__(
        self,
        ip_address: str,
        user_agent: Optional[str] = None,
        success: bool = False,
        failure_reason: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if not ip_address or not ip_address.strip():
            raise ValidationError("IP address cannot be empty")
        
        self.ip_address = ip_address.strip()
        self.user_agent = user_agent
        self.success = success
        self.failure_reason = failure_reason
        self.timestamp = timestamp or datetime.utcnow()
    
    @property
    def is_recent(self, minutes: int = 15) -> bool:
        """Check if attempt is recent."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return self.timestamp >= cutoff


class KYCStatus(Enum):
    """KYC (Know Your Customer) status for future integration."""
    
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    
    @property
    def allows_trading(self) -> bool:
        """Check if KYC status allows trading."""
        return self == KYCStatus.APPROVED
    
    @property
    def requires_action(self) -> bool:
        """Check if KYC status requires user action."""
        return self in [KYCStatus.NOT_STARTED, KYCStatus.REJECTED, KYCStatus.EXPIRED]


class TwoFactorMethod(Enum):
    """Two-factor authentication methods."""
    
    NONE = "NONE"
    SMS = "SMS"
    EMAIL = "EMAIL"
    TOTP = "TOTP"  # Time-based One-Time Password (Google Authenticator, etc.)
    
    @property
    def is_enabled(self) -> bool:
        """Check if 2FA is enabled."""
        return self != TwoFactorMethod.NONE


class SecuritySettings(ValueObject):
    """User security settings value object."""
    
    def __init__(
        self,
        two_factor_method: TwoFactorMethod = TwoFactorMethod.NONE,
        login_notifications: bool = True,
        session_timeout_minutes: int = 60,
        require_password_change: bool = False,
        password_expires_at: Optional[datetime] = None,
    ) -> None:
        if session_timeout_minutes < 15 or session_timeout_minutes > 480:
            raise ValidationError("Session timeout must be between 15 and 480 minutes")
        
        self.two_factor_method = two_factor_method
        self.login_notifications = login_notifications
        self.session_timeout_minutes = session_timeout_minutes
        self.require_password_change = require_password_change
        self.password_expires_at = password_expires_at
    
    @property
    def is_password_expired(self) -> bool:
        """Check if password is expired."""
        if not self.password_expires_at:
            return False
        return datetime.utcnow() >= self.password_expires_at
    
    @property
    def session_timeout_seconds(self) -> int:
        """Get session timeout in seconds."""
        return self.session_timeout_minutes * 60