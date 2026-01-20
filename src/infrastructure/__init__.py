"""
TradeSense AI Infrastructure Layer

This module provides the core infrastructure components for the TradeSense AI platform:

- Configuration management with environment-based settings
- Database connection management with pooling and health monitoring
- Security primitives (JWT, RBAC, hashing, encryption)
- Event bus abstraction with pluggable implementations
- Financial-grade logging and audit trails
- Common utilities for context management and decorators

Key Features:
- Financial compliance by design
- Async-first architecture
- Comprehensive audit trails
- Circuit breaker patterns
- Structured logging with correlation tracking
- Role-based access control
- Token-based authentication with refresh
- Event-driven communication
"""

from .config.settings import AppSettings, get_settings, reload_settings
from .database.connection import DatabaseConnectionManager
from .database.session import DatabaseSessionManager, TransactionManager
from .security.authentication import JWTManager, TokenPayload
from .security.authorization import RoleBasedAccessControl, Permission, Role
from .security.hashing import SecureHasher, PasswordStrengthValidator
from .messaging.event_bus import EventBus, EventHandler, EventSubscription
from .messaging.in_memory_bus import InMemoryEventBus
from .logging.structured_logger import configure_logging, get_logger, get_business_logger
from .logging.audit_logger import AuditLogger, AuditEventType, AuditSeverity
from .common.context import ExecutionContext, AuditContext
from .common.exceptions import InfrastructureError
from .common.decorators import (
    with_execution_context,
    with_audit_context,
    with_retry,
    require_permission,
    with_performance_monitoring,
    circuit_breaker,
)

__all__ = [
    # Configuration
    "AppSettings",
    "get_settings",
    "reload_settings",
    
    # Database
    "DatabaseConnectionManager",
    "DatabaseSessionManager", 
    "TransactionManager",
    
    # Security
    "JWTManager",
    "TokenPayload",
    "RoleBasedAccessControl",
    "Permission",
    "Role",
    "SecureHasher",
    "PasswordStrengthValidator",
    
    # Messaging
    "EventBus",
    "EventHandler",
    "EventSubscription",
    "InMemoryEventBus",
    
    # Logging
    "configure_logging",
    "get_logger",
    "get_business_logger",
    "AuditLogger",
    "AuditEventType",
    "AuditSeverity",
    
    # Common
    "ExecutionContext",
    "AuditContext",
    "InfrastructureError",
    
    # Decorators
    "with_execution_context",
    "with_audit_context",
    "with_retry",
    "require_permission",
    "with_performance_monitoring",
    "circuit_breaker",
]