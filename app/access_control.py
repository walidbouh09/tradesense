"""
Access Control Module - TradeSense AI

Ensures users cannot trade without an active challenge.
Implements authorization checks for all trading operations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from enum import Enum
from functools import wraps
from flask import request, jsonify, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """System permissions."""
    VIEW_CHALLENGES = "view_challenges"
    CREATE_CHALLENGE = "create_challenge"
    TRADE = "trade"
    VIEW_ANALYTICS = "view_analytics"
    ADMIN_ACCESS = "admin_access"


class AccessDeniedReason(str, Enum):
    """Reasons for access denial."""
    NO_ACTIVE_CHALLENGE = "no_active_challenge"
    CHALLENGE_NOT_STARTED = "challenge_not_started"
    CHALLENGE_ENDED = "challenge_ended"
    CHALLENGE_FAILED = "challenge_failed"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    PAYMENT_REQUIRED = "payment_required"
    ACCOUNT_SUSPENDED = "account_suspended"


class AccessControlService:
    """
    Service for managing access control and permissions.
    
    Core principle: Users CANNOT trade without an active, paid challenge.
    """
    
    def __init__(self):
        """Initialize access control service."""
        self.role_permissions = {
            'USER': [
                Permission.VIEW_CHALLENGES,
                Permission.CREATE_CHALLENGE,
                Permission.TRADE,
                Permission.VIEW_ANALYTICS
            ],
            'ADMIN': [
                Permission.VIEW_CHALLENGES,
                Permission.CREATE_CHALLENGE,
                Permission.TRADE,
                Permission.VIEW_ANALYTICS,
                Permission.ADMIN_ACCESS
            ],
            'SUPERADMIN': [
                Permission.VIEW_CHALLENGES,
                Permission.CREATE_CHALLENGE,
                Permission.TRADE,
                Permission.VIEW_ANALYTICS,
                Permission.ADMIN_ACCESS
            ]
        }
        
        logger.info("Access control service initialized")
    
    def get_db_session(self) -> Session:
        """Get database session."""
        database_url = current_app.config.get(
            'DATABASE_URL',
            'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense'
        )
        engine = create_engine(database_url, echo=False)
        return Session(engine)
    
    def check_user_active(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user account is active.
        
        Args:
            user_id: User identifier
            
        Returns:
            Tuple of (is_active, reason_if_not)
        """
        try:
            session = self.get_db_session()
            
            user = session.execute(text("""
                SELECT status, deleted_at
                FROM users
                WHERE id = :user_id
            """), {'user_id': user_id}).fetchone()
            
            session.close()
            
            if not user:
                return False, "User not found"
            
            if user.deleted_at is not None:
                return False, "Account deleted"
            
            if user.status != 'ACTIVE':
                return False, f"Account status: {user.status}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking user status: {e}")
            return False, "Error checking account status"
    
    def get_active_challenge(self, user_id: str) -> Optional[Dict]:
        """
        Get user's active challenge.
        
        Args:
            user_id: User identifier
            
        Returns:
            Active challenge data or None
        """
        try:
            session = self.get_db_session()
            
            challenge = session.execute(text("""
                SELECT
                    c.id,
                    c.status,
                    c.challenge_type,
                    c.initial_balance,
                    c.current_equity,
                    c.started_at,
                    c.ended_at,
                    c.created_at,
                    p.status as payment_status,
                    p.amount as payment_amount,
                    p.provider as payment_provider
                FROM challenges c
                LEFT JOIN payments p ON c.id = p.challenge_id
                WHERE c.user_id = :user_id
                AND c.status = 'ACTIVE'
                ORDER BY c.created_at DESC
                LIMIT 1
            """), {'user_id': user_id}).fetchone()
            
            session.close()
            
            if not challenge:
                return None
            
            return {
                'id': str(challenge.id),
                'status': challenge.status,
                'challenge_type': challenge.challenge_type,
                'initial_balance': float(challenge.initial_balance),
                'current_equity': float(challenge.current_equity),
                'started_at': challenge.started_at.isoformat() if challenge.started_at else None,
                'ended_at': challenge.ended_at.isoformat() if challenge.ended_at else None,
                'created_at': challenge.created_at.isoformat(),
                'payment_status': challenge.payment_status,
                'payment_amount': float(challenge.payment_amount) if challenge.payment_amount else None,
                'payment_provider': challenge.payment_provider
            }
            
        except Exception as e:
            logger.error(f"Error getting active challenge: {e}")
            return None
    
    def can_trade(self, user_id: str) -> Tuple[bool, Optional[AccessDeniedReason], Optional[str]]:
        """
        Check if user can execute trades.
        
        CRITICAL: Users CANNOT trade without an active, paid challenge.
        
        Args:
            user_id: User identifier
            
        Returns:
            Tuple of (can_trade, denial_reason, message)
        """
        # Check user account status
        is_active, reason = self.check_user_active(user_id)
        if not is_active:
            return False, AccessDeniedReason.ACCOUNT_SUSPENDED, reason
        
        # Get active challenge
        challenge = self.get_active_challenge(user_id)
        
        if not challenge:
            return (
                False,
                AccessDeniedReason.NO_ACTIVE_CHALLENGE,
                "No active challenge found. Please purchase a challenge to start trading."
            )
        
        # Verify challenge is paid
        if challenge['payment_status'] != 'SUCCESS':
            return (
                False,
                AccessDeniedReason.PAYMENT_REQUIRED,
                "Challenge payment not completed. Please complete payment to start trading."
            )
        
        # Verify challenge is started
        if not challenge['started_at']:
            return (
                False,
                AccessDeniedReason.CHALLENGE_NOT_STARTED,
                "Challenge not started yet. Please start your challenge to begin trading."
            )
        
        # Verify challenge hasn't ended
        if challenge['ended_at']:
            return (
                False,
                AccessDeniedReason.CHALLENGE_ENDED,
                "Challenge has ended. Please purchase a new challenge to continue trading."
            )
        
        # All checks passed
        return True, None, None
    
    def can_access_challenge(self, user_id: str, challenge_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can access a specific challenge.
        
        Args:
            user_id: User identifier
            challenge_id: Challenge identifier
            
        Returns:
            Tuple of (can_access, reason_if_not)
        """
        try:
            session = self.get_db_session()
            
            challenge = session.execute(text("""
                SELECT user_id
                FROM challenges
                WHERE id = :challenge_id
            """), {'challenge_id': challenge_id}).fetchone()
            
            session.close()
            
            if not challenge:
                return False, "Challenge not found"
            
            if str(challenge.user_id) != user_id:
                return False, "You don't have permission to access this challenge"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking challenge access: {e}")
            return False, "Error checking challenge access"
    
    def has_permission(self, user_role: str, permission: Permission) -> bool:
        """
        Check if user role has a specific permission.
        
        Args:
            user_role: User's role
            permission: Permission to check
            
        Returns:
            True if user has permission
        """
        role_perms = self.role_permissions.get(user_role, [])
        return permission in role_perms
    
    def get_user_permissions(self, user_role: str) -> list:
        """
        Get all permissions for a user role.
        
        Args:
            user_role: User's role
            
        Returns:
            List of permissions
        """
        return [p.value for p in self.role_permissions.get(user_role, [])]
    
    def enforce_trading_access(self, user_id: str) -> Dict:
        """
        Enforce trading access and return detailed status.
        
        Used by trading endpoints to verify access before execution.
        
        Args:
            user_id: User identifier
            
        Returns:
            Access status with details
        """
        can_trade, denial_reason, message = self.can_trade(user_id)
        
        if can_trade:
            challenge = self.get_active_challenge(user_id)
            return {
                'allowed': True,
                'challenge': challenge,
                'message': 'Trading access granted'
            }
        else:
            return {
                'allowed': False,
                'reason': denial_reason.value if denial_reason else 'unknown',
                'message': message or 'Trading access denied',
                'action_required': self._get_action_required(denial_reason)
            }
    
    def _get_action_required(self, denial_reason: Optional[AccessDeniedReason]) -> str:
        """Get user-friendly action required message."""
        actions = {
            AccessDeniedReason.NO_ACTIVE_CHALLENGE: "Purchase a challenge to start trading",
            AccessDeniedReason.PAYMENT_REQUIRED: "Complete payment for your challenge",
            AccessDeniedReason.CHALLENGE_NOT_STARTED: "Start your challenge from the dashboard",
            AccessDeniedReason.CHALLENGE_ENDED: "Purchase a new challenge to continue",
            AccessDeniedReason.CHALLENGE_FAILED: "Purchase a new challenge to try again",
            AccessDeniedReason.ACCOUNT_SUSPENDED: "Contact support to reactivate your account",
            AccessDeniedReason.INSUFFICIENT_PERMISSIONS: "Upgrade your account for access"
        }
        return actions.get(denial_reason, "Contact support for assistance")


# Global access control service instance
access_control = AccessControlService()


# Decorator for protecting trading endpoints
def require_active_challenge(f):
    """
    Decorator to require active challenge for trading operations.
    
    Usage:
        @require_active_challenge
        def execute_trade():
            # Trade execution logic
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get user_id from request (would normally come from JWT token)
        user_id = request.json.get('user_id') if request.json else None
        
        if not user_id:
            return jsonify({
                'error': 'User ID required',
                'code': 'MISSING_USER_ID'
            }), 401
        
        # Check trading access
        access_status = access_control.enforce_trading_access(user_id)
        
        if not access_status['allowed']:
            return jsonify({
                'error': access_status['message'],
                'reason': access_status['reason'],
                'action_required': access_status['action_required'],
                'code': 'TRADING_ACCESS_DENIED'
            }), 403
        
        # Add challenge info to request context
        request.active_challenge = access_status['challenge']
        
        return f(*args, **kwargs)
    
    return decorated_function


# Decorator for checking permissions
def require_permission(permission: Permission):
    """
    Decorator to require specific permission.
    
    Usage:
        @require_permission(Permission.ADMIN_ACCESS)
        def admin_function():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user role from request (would normally come from JWT token)
            user_role = request.headers.get('X-User-Role', 'USER')
            
            if not access_control.has_permission(user_role, permission):
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required_permission': permission.value,
                    'code': 'PERMISSION_DENIED'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
