"""Role-based access control with fine-grained permissions and caching."""

from enum import Enum
from functools import wraps
from typing import Dict, List, Optional, Set
from uuid import UUID

import structlog
from pydantic import BaseModel

from ..common.context import ExecutionContext
from ..common.exceptions import AuthorizationError, PermissionDeniedError

logger = structlog.get_logger()


class ResourceType(Enum):
    """System resource types."""
    
    USER = "user"
    ACCOUNT = "account"
    ORDER = "order"
    POSITION = "position"
    TRANSACTION = "transaction"
    AUDIT_LOG = "audit_log"
    SYSTEM_CONFIG = "system_config"


class Action(Enum):
    """System actions."""
    
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    CANCEL = "cancel"


class Permission(BaseModel):
    """Permission definition."""
    
    resource: ResourceType
    action: Action
    conditions: Optional[Dict[str, any]] = None
    
    def __str__(self) -> str:
        return f"{self.resource.value}:{self.action.value}"
    
    def matches(self, resource: ResourceType, action: Action) -> bool:
        """Check if permission matches resource and action."""
        return self.resource == resource and self.action == action


class Role(BaseModel):
    """Role definition with permissions."""
    
    name: str
    description: str
    permissions: List[Permission]
    is_system_role: bool = False
    
    def has_permission(self, resource: ResourceType, action: Action) -> bool:
        """Check if role has specific permission."""
        return any(
            perm.matches(resource, action) 
            for perm in self.permissions
        )


class UserPermissions(BaseModel):
    """User's effective permissions from all roles."""
    
    user_id: UUID
    roles: List[Role]
    direct_permissions: List[Permission] = []
    
    @property
    def all_permissions(self) -> List[Permission]:
        """Get all permissions from roles and direct grants."""
        permissions = self.direct_permissions.copy()
        
        for role in self.roles:
            permissions.extend(role.permissions)
        
        return permissions
    
    def has_permission(
        self, 
        resource: ResourceType, 
        action: Action,
        context: Optional[Dict[str, any]] = None,
    ) -> bool:
        """Check if user has specific permission."""
        for permission in self.all_permissions:
            if permission.matches(resource, action):
                # Check conditions if present
                if permission.conditions and context:
                    if not self._check_conditions(permission.conditions, context):
                        continue
                return True
        
        return False
    
    def _check_conditions(
        self, 
        conditions: Dict[str, any], 
        context: Dict[str, any]
    ) -> bool:
        """Check if permission conditions are met."""
        for key, expected_value in conditions.items():
            if key not in context:
                return False
            
            context_value = context[key]
            
            # Handle different condition types
            if isinstance(expected_value, dict):
                if "$eq" in expected_value:
                    if context_value != expected_value["$eq"]:
                        return False
                elif "$in" in expected_value:
                    if context_value not in expected_value["$in"]:
                        return False
                elif "$owner" in expected_value:
                    # Check if user owns the resource
                    if str(self.user_id) != str(context_value):
                        return False
            else:
                if context_value != expected_value:
                    return False
        
        return True


class PermissionCache:
    """In-memory permission cache (in production, use Redis)."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[UUID, UserPermissions] = {}
        self._cache_timestamps: Dict[UUID, float] = {}
    
    async def get_user_permissions(self, user_id: UUID) -> Optional[UserPermissions]:
        """Get cached user permissions."""
        import time
        
        if user_id not in self._cache:
            return None
        
        # Check if cache entry is expired
        if time.time() - self._cache_timestamps[user_id] > self.ttl_seconds:
            del self._cache[user_id]
            del self._cache_timestamps[user_id]
            return None
        
        return self._cache[user_id]
    
    async def set_user_permissions(self, user_permissions: UserPermissions) -> None:
        """Cache user permissions."""
        import time
        
        self._cache[user_permissions.user_id] = user_permissions
        self._cache_timestamps[user_permissions.user_id] = time.time()
    
    async def invalidate_user(self, user_id: UUID) -> None:
        """Invalidate cached permissions for user."""
        self._cache.pop(user_id, None)
        self._cache_timestamps.pop(user_id, None)
    
    async def clear_cache(self) -> None:
        """Clear entire permission cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


class RoleBasedAccessControl:
    """Role-based access control system with fine-grained permissions."""
    
    def __init__(self):
        self.permission_cache = PermissionCache()
        self._system_roles = self._initialize_system_roles()
    
    def _initialize_system_roles(self) -> Dict[str, Role]:
        """Initialize system roles with default permissions."""
        roles = {}
        
        # Super Admin - full system access
        roles["super_admin"] = Role(
            name="super_admin",
            description="Full system administrator",
            permissions=[
                Permission(resource=resource, action=action)
                for resource in ResourceType
                for action in Action
            ],
            is_system_role=True,
        )
        
        # Trader - trading operations
        roles["trader"] = Role(
            name="trader",
            description="Trading operations",
            permissions=[
                Permission(resource=ResourceType.ORDER, action=Action.CREATE),
                Permission(resource=ResourceType.ORDER, action=Action.READ),
                Permission(resource=ResourceType.ORDER, action=Action.CANCEL),
                Permission(
                    resource=ResourceType.ORDER, 
                    action=Action.UPDATE,
                    conditions={"owner": {"$owner": True}},
                ),
                Permission(resource=ResourceType.POSITION, action=Action.READ),
                Permission(resource=ResourceType.ACCOUNT, action=Action.READ),
            ],
        )
        
        # Risk Manager - risk monitoring and controls
        roles["risk_manager"] = Role(
            name="risk_manager",
            description="Risk management and monitoring",
            permissions=[
                Permission(resource=ResourceType.ORDER, action=Action.READ),
                Permission(resource=ResourceType.ORDER, action=Action.CANCEL),
                Permission(resource=ResourceType.POSITION, action=Action.READ),
                Permission(resource=ResourceType.ACCOUNT, action=Action.READ),
                Permission(resource=ResourceType.TRANSACTION, action=Action.READ),
                Permission(resource=ResourceType.AUDIT_LOG, action=Action.READ),
            ],
        )
        
        # Compliance Officer - audit and compliance
        roles["compliance_officer"] = Role(
            name="compliance_officer",
            description="Compliance and audit access",
            permissions=[
                Permission(resource=ResourceType.AUDIT_LOG, action=Action.READ),
                Permission(resource=ResourceType.USER, action=Action.READ),
                Permission(resource=ResourceType.ACCOUNT, action=Action.READ),
                Permission(resource=ResourceType.TRANSACTION, action=Action.READ),
            ],
        )
        
        # Read Only - view access only
        roles["read_only"] = Role(
            name="read_only",
            description="Read-only access",
            permissions=[
                Permission(resource=ResourceType.ORDER, action=Action.READ),
                Permission(resource=ResourceType.POSITION, action=Action.READ),
                Permission(resource=ResourceType.ACCOUNT, action=Action.READ),
            ],
        )
        
        return roles
    
    async def get_user_permissions(self, user_id: UUID) -> UserPermissions:
        """Get user permissions with caching."""
        # Check cache first
        cached_permissions = await self.permission_cache.get_user_permissions(user_id)
        if cached_permissions:
            return cached_permissions
        
        # In a real implementation, this would query the database
        # For now, return default permissions
        user_permissions = UserPermissions(
            user_id=user_id,
            roles=[self._system_roles["trader"]],  # Default role
        )
        
        # Cache the permissions
        await self.permission_cache.set_user_permissions(user_permissions)
        
        return user_permissions
    
    async def check_permission(
        self,
        user_id: UUID,
        resource: ResourceType,
        action: Action,
        context: Optional[Dict[str, any]] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> bool:
        """Check if user has permission for resource action."""
        try:
            user_permissions = await self.get_user_permissions(user_id)
            
            has_permission = user_permissions.has_permission(resource, action, context)
            
            # Log permission check for audit
            logger.info(
                "Permission check",
                user_id=str(user_id),
                resource=resource.value,
                action=action.value,
                granted=has_permission,
                context=context,
                correlation_id=execution_context.correlation_id if execution_context else None,
            )
            
            return has_permission
            
        except Exception as e:
            logger.error(
                "Permission check error",
                user_id=str(user_id),
                resource=resource.value,
                action=action.value,
                error=str(e),
            )
            return False
    
    async def require_permission(
        self,
        user_id: UUID,
        resource: ResourceType,
        action: Action,
        context: Optional[Dict[str, any]] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> None:
        """Require permission or raise exception."""
        has_permission = await self.check_permission(
            user_id, resource, action, context, execution_context
        )
        
        if not has_permission:
            raise PermissionDeniedError(
                f"User {user_id} does not have permission {resource.value}:{action.value}"
            )
    
    async def assign_role(
        self,
        user_id: UUID,
        role_name: str,
        execution_context: ExecutionContext,
    ) -> None:
        """Assign role to user."""
        if role_name not in self._system_roles:
            raise AuthorizationError(f"Role {role_name} does not exist")
        
        # In a real implementation, this would update the database
        # and invalidate the cache
        await self.permission_cache.invalidate_user(user_id)
        
        logger.info(
            "Role assigned",
            user_id=str(user_id),
            role=role_name,
            correlation_id=execution_context.correlation_id,
        )
    
    async def revoke_role(
        self,
        user_id: UUID,
        role_name: str,
        execution_context: ExecutionContext,
    ) -> None:
        """Revoke role from user."""
        # In a real implementation, this would update the database
        # and invalidate the cache
        await self.permission_cache.invalidate_user(user_id)
        
        logger.info(
            "Role revoked",
            user_id=str(user_id),
            role=role_name,
            correlation_id=execution_context.correlation_id,
        )
    
    def require_permission_decorator(
        self,
        resource: ResourceType,
        action: Action,
        context_extractor: Optional[callable] = None,
    ):
        """Decorator for automatic permission checking."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user_id and execution_context from function arguments
                # This is a simplified implementation - in practice, you'd extract
                # these from the request context or dependency injection
                
                user_id = kwargs.get('user_id')
                execution_context = kwargs.get('execution_context')
                
                if not user_id:
                    raise AuthorizationError("User ID not found in request context")
                
                # Extract context if extractor provided
                context = None
                if context_extractor:
                    context = context_extractor(*args, **kwargs)
                
                # Check permission
                await self.require_permission(
                    user_id, resource, action, context, execution_context
                )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    async def get_user_roles(self, user_id: UUID) -> List[Role]:
        """Get all roles assigned to user."""
        user_permissions = await self.get_user_permissions(user_id)
        return user_permissions.roles
    
    async def get_available_roles(self) -> List[Role]:
        """Get all available system roles."""
        return list(self._system_roles.values())