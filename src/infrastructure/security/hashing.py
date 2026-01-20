"""Cryptographically secure hashing for passwords and sensitive data."""

import hashlib
import hmac
import secrets
from typing import Optional

import bcrypt
import structlog

from ..config.settings import SecurityConfig
from ..common.exceptions import SecurityError

logger = structlog.get_logger()


class SecureHasher:
    """Cryptographically secure hashing with salt, pepper, and context-specific keys."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self._pepper = config.password_pepper.get_secret_value().encode('utf-8')
    
    def hash_password(self, password: str, custom_pepper: Optional[str] = None) -> str:
        """Hash password with bcrypt, salt, and pepper."""
        try:
            # Use custom pepper if provided, otherwise use global pepper
            pepper = custom_pepper.encode('utf-8') if custom_pepper else self._pepper
            
            # Add pepper to password before hashing
            peppered_password = password.encode('utf-8') + pepper
            
            # Generate salt and hash with bcrypt
            salt = bcrypt.gensalt(rounds=self.config.password_salt_rounds)
            hashed = bcrypt.hashpw(peppered_password, salt)
            
            logger.debug(
                "Password hashed",
                salt_rounds=self.config.password_salt_rounds,
                has_custom_pepper=custom_pepper is not None,
            )
            
            return hashed.decode('utf-8')
            
        except Exception as e:
            logger.error("Password hashing failed", error=str(e))
            raise SecurityError(f"Password hashing failed: {e}") from e
    
    def verify_password(
        self, 
        password: str, 
        hashed: str, 
        custom_pepper: Optional[str] = None
    ) -> bool:
        """Verify password against hash."""
        try:
            # Use custom pepper if provided, otherwise use global pepper
            pepper = custom_pepper.encode('utf-8') if custom_pepper else self._pepper
            
            # Add pepper to password before verification
            peppered_password = password.encode('utf-8') + pepper
            
            # Verify with bcrypt
            is_valid = bcrypt.checkpw(peppered_password, hashed.encode('utf-8'))
            
            logger.debug(
                "Password verification",
                is_valid=is_valid,
                has_custom_pepper=custom_pepper is not None,
            )
            
            return is_valid
            
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False
    
    def hash_sensitive_data(
        self, 
        data: str, 
        context: str,
        salt: Optional[str] = None,
    ) -> str:
        """Hash sensitive data with context-specific salt."""
        try:
            # Generate or use provided salt
            if salt is None:
                salt = secrets.token_hex(16)
            
            # Create context-specific key
            context_key = self._derive_context_key(context)
            
            # Combine data with salt and context key
            combined_data = f"{data}{salt}{context_key}".encode('utf-8')
            
            # Hash with SHA-256
            hash_obj = hashlib.sha256(combined_data)
            hashed = hash_obj.hexdigest()
            
            # Return salt + hash for storage
            return f"{salt}${hashed}"
            
        except Exception as e:
            logger.error("Sensitive data hashing failed", error=str(e), context=context)
            raise SecurityError(f"Sensitive data hashing failed: {e}") from e
    
    def verify_sensitive_data(self, data: str, hashed: str, context: str) -> bool:
        """Verify sensitive data against hash."""
        try:
            # Split salt and hash
            if '$' not in hashed:
                return False
            
            salt, stored_hash = hashed.split('$', 1)
            
            # Recreate hash with same salt
            recreated_hash = self.hash_sensitive_data(data, context, salt)
            
            # Compare hashes using constant-time comparison
            return hmac.compare_digest(hashed, recreated_hash)
            
        except Exception as e:
            logger.error("Sensitive data verification failed", error=str(e), context=context)
            return False
    
    def _derive_context_key(self, context: str) -> str:
        """Derive context-specific key from global pepper."""
        # Use HMAC to derive context-specific key
        context_bytes = context.encode('utf-8')
        derived_key = hmac.new(self._pepper, context_bytes, hashlib.sha256)
        return derived_key.hexdigest()
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for secure storage."""
        return self.hash_sensitive_data(api_key, "api_key")
    
    def verify_api_key(self, api_key: str, hashed: str) -> bool:
        """Verify API key against hash."""
        return self.verify_sensitive_data(api_key, hashed, "api_key")
    
    def hash_session_id(self, session_id: str) -> str:
        """Hash session ID for secure storage."""
        return self.hash_sensitive_data(session_id, "session")
    
    def verify_session_id(self, session_id: str, hashed: str) -> bool:
        """Verify session ID against hash."""
        return self.verify_sensitive_data(session_id, hashed, "session")
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token."""
        return secrets.token_urlsafe(length)
    
    def generate_api_key(self) -> tuple[str, str]:
        """Generate API key and return (key, hash) tuple."""
        api_key = f"tsa_{secrets.token_urlsafe(32)}"
        api_key_hash = self.hash_api_key(api_key)
        
        logger.info("API key generated", key_prefix=api_key[:8])
        
        return api_key, api_key_hash


class DataIntegrityHasher:
    """Specialized hasher for data integrity verification."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode('utf-8')
    
    def create_integrity_hash(self, data: str, timestamp: str) -> str:
        """Create integrity hash for data with timestamp."""
        combined_data = f"{data}|{timestamp}".encode('utf-8')
        integrity_hash = hmac.new(
            self.secret_key,
            combined_data,
            hashlib.sha256
        ).hexdigest()
        
        return integrity_hash
    
    def verify_integrity(self, data: str, timestamp: str, expected_hash: str) -> bool:
        """Verify data integrity hash."""
        calculated_hash = self.create_integrity_hash(data, timestamp)
        return hmac.compare_digest(expected_hash, calculated_hash)
    
    def create_audit_hash(self, audit_record: dict) -> str:
        """Create hash for audit record integrity."""
        # Sort keys for consistent hashing
        sorted_items = sorted(audit_record.items())
        data_string = "|".join(f"{k}:{v}" for k, v in sorted_items)
        
        return hmac.new(
            self.secret_key,
            data_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()


class PasswordStrengthValidator:
    """Password strength validation for financial security requirements."""
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, list[str]]:
        """Validate password meets financial security requirements."""
        errors = []
        
        # Length requirement
        if len(password) < 12:
            errors.append("Password must be at least 12 characters long")
        
        # Character requirements
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        # Common password patterns
        common_patterns = [
            "password", "123456", "qwerty", "admin", "user",
            "login", "welcome", "secret", "default"
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                errors.append(f"Password cannot contain common pattern: {pattern}")
        
        # Sequential characters
        if any(
            ord(password[i]) == ord(password[i-1]) + 1 and 
            ord(password[i]) == ord(password[i-2]) + 2
            for i in range(2, len(password))
        ):
            errors.append("Password cannot contain sequential characters")
        
        # Repeated characters
        if any(
            password[i] == password[i-1] == password[i-2]
            for i in range(2, len(password))
        ):
            errors.append("Password cannot contain more than 2 repeated characters")
        
        is_valid = len(errors) == 0
        return is_valid, errors