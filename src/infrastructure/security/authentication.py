"""JWT authentication with token management, refresh, and blacklisting."""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

import jwt
import structlog
from pydantic import BaseModel

from ..config.settings import SecurityConfig
from ..common.context import ExecutionContext
from ..common.exceptions import AuthenticationError, TokenValidationError

logger = structlog.get_logger()


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    
    sub: str  # Subject (user ID)
    iat: int  # Issued at
    exp: int  # Expiration
    jti: str  # JWT ID (for blacklisting)
    type: str  # Token type (access/refresh)
    permissions: List[str] = []
    session_id: Optional[str] = None
    
    @property
    def user_id(self) -> UUID:
        """Get user ID as UUID."""
        return UUID(self.sub)
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow().timestamp() > self.exp
    
    @property
    def expires_at(self) -> datetime:
        """Get expiration datetime."""
        return datetime.fromtimestamp(self.exp)


class TokenBlacklist:
    """In-memory token blacklist (in production, use Redis or database)."""
    
    def __init__(self):
        self._blacklisted_tokens: Set[str] = set()
        self._blacklist_reasons: Dict[str, str] = {}
    
    async def add_token(self, jti: str, reason: str = "revoked") -> None:
        """Add token to blacklist."""
        self._blacklisted_tokens.add(jti)
        self._blacklist_reasons[jti] = reason
        
        logger.info("Token blacklisted", jti=jti, reason=reason)
    
    async def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted."""
        return jti in self._blacklisted_tokens
    
    async def get_blacklist_reason(self, jti: str) -> Optional[str]:
        """Get reason for token blacklisting."""
        return self._blacklist_reasons.get(jti)
    
    async def cleanup_expired_tokens(self, current_time: datetime) -> None:
        """Remove expired tokens from blacklist to save memory."""
        # In a real implementation, this would query the database
        # to find expired tokens and remove them from the blacklist
        pass


class JWTManager:
    """JWT token management with refresh, blacklisting, and audit trail."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.blacklist = TokenBlacklist()
        self._secret_key = config.jwt_secret_key.get_secret_value()
    
    async def create_access_token(
        self,
        user_id: UUID,
        permissions: List[str],
        execution_context: ExecutionContext,
        session_id: Optional[str] = None,
    ) -> str:
        """Create JWT access token with permissions and audit context."""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.config.access_token_expire_minutes)
        jti = str(uuid4())
        
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": jti,
            "type": "access",
            "permissions": permissions,
            "session_id": session_id,
        }
        
        token = jwt.encode(
            payload,
            self._secret_key,
            algorithm=self.config.jwt_algorithm,
        )
        
        logger.info(
            "Access token created",
            user_id=str(user_id),
            jti=jti,
            expires_at=expires_at.isoformat(),
            permissions_count=len(permissions),
            correlation_id=execution_context.correlation_id,
        )
        
        return token
    
    async def create_refresh_token(
        self,
        user_id: UUID,
        execution_context: ExecutionContext,
        session_id: Optional[str] = None,
    ) -> str:
        """Create JWT refresh token for token renewal."""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.config.refresh_token_expire_days)
        jti = str(uuid4())
        
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": jti,
            "type": "refresh",
            "session_id": session_id,
        }
        
        token = jwt.encode(
            payload,
            self._secret_key,
            algorithm=self.config.jwt_algorithm,
        )
        
        logger.info(
            "Refresh token created",
            user_id=str(user_id),
            jti=jti,
            expires_at=expires_at.isoformat(),
            correlation_id=execution_context.correlation_id,
        )
        
        return token
    
    async def validate_token(self, token: str) -> TokenPayload:
        """Validate JWT token and return payload."""
        try:
            # Decode token
            payload_dict = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self.config.jwt_algorithm],
            )
            
            payload = TokenPayload(**payload_dict)
            
            # Check if token is blacklisted
            if await self.blacklist.is_blacklisted(payload.jti):
                reason = await self.blacklist.get_blacklist_reason(payload.jti)
                raise TokenValidationError(f"Token is blacklisted: {reason}")
            
            # Additional validation
            if payload.is_expired:
                raise TokenValidationError("Token has expired")
            
            logger.debug(
                "Token validated successfully",
                user_id=payload.sub,
                jti=payload.jti,
                token_type=payload.type,
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise TokenValidationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise TokenValidationError(f"Invalid token: {e}")
        except Exception as e:
            logger.error("Token validation error", error=str(e))
            raise TokenValidationError(f"Token validation failed: {e}")
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        new_permissions: List[str],
        execution_context: ExecutionContext,
    ) -> tuple[str, str]:
        """Refresh access token using refresh token."""
        # Validate refresh token
        refresh_payload = await self.validate_token(refresh_token)
        
        if refresh_payload.type != "refresh":
            raise TokenValidationError("Invalid token type for refresh")
        
        # Blacklist old refresh token
        await self.blacklist.add_token(refresh_payload.jti, "refreshed")
        
        # Create new tokens
        new_access_token = await self.create_access_token(
            user_id=refresh_payload.user_id,
            permissions=new_permissions,
            execution_context=execution_context,
            session_id=refresh_payload.session_id,
        )
        
        new_refresh_token = await self.create_refresh_token(
            user_id=refresh_payload.user_id,
            execution_context=execution_context,
            session_id=refresh_payload.session_id,
        )
        
        logger.info(
            "Tokens refreshed",
            user_id=refresh_payload.sub,
            old_jti=refresh_payload.jti,
            correlation_id=execution_context.correlation_id,
        )
        
        return new_access_token, new_refresh_token
    
    async def revoke_token(
        self,
        token: str,
        reason: str,
        execution_context: ExecutionContext,
    ) -> None:
        """Revoke token by adding to blacklist."""
        try:
            payload = await self.validate_token(token)
            await self.blacklist.add_token(payload.jti, reason)
            
            logger.info(
                "Token revoked",
                user_id=payload.sub,
                jti=payload.jti,
                reason=reason,
                correlation_id=execution_context.correlation_id,
            )
            
        except TokenValidationError:
            # Token is already invalid, but we still want to blacklist it
            # if we can decode the JTI
            try:
                payload_dict = jwt.decode(
                    token,
                    self._secret_key,
                    algorithms=[self.config.jwt_algorithm],
                    options={"verify_exp": False},  # Ignore expiration for revocation
                )
                jti = payload_dict.get("jti")
                if jti:
                    await self.blacklist.add_token(jti, reason)
            except Exception:
                pass  # Can't decode token, nothing to blacklist
    
    async def revoke_all_user_tokens(
        self,
        user_id: UUID,
        reason: str,
        execution_context: ExecutionContext,
    ) -> None:
        """Revoke all tokens for a user (requires token store)."""
        # In a real implementation, this would query a token store
        # to find all active tokens for the user and blacklist them
        logger.info(
            "All user tokens revoked",
            user_id=str(user_id),
            reason=reason,
            correlation_id=execution_context.correlation_id,
        )
    
    async def get_token_info(self, token: str) -> Dict[str, any]:
        """Get token information for debugging/monitoring."""
        try:
            payload = await self.validate_token(token)
            
            return {
                "valid": True,
                "user_id": payload.sub,
                "jti": payload.jti,
                "type": payload.type,
                "issued_at": datetime.fromtimestamp(payload.iat).isoformat(),
                "expires_at": payload.expires_at.isoformat(),
                "permissions": payload.permissions,
                "session_id": payload.session_id,
            }
            
        except TokenValidationError as e:
            return {
                "valid": False,
                "error": str(e),
            }
    
    async def cleanup_expired_tokens(self) -> None:
        """Cleanup expired tokens from blacklist."""
        await self.blacklist.cleanup_expired_tokens(datetime.utcnow())