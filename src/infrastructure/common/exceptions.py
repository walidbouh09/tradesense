"""Infrastructure-specific exceptions with detailed error context."""

from typing import Any, Dict, Optional
from uuid import UUID


class InfrastructureError(Exception):
    """Base exception for infrastructure-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.correlation_id = correlation_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "correlation_id": self.correlation_id,
        }


class ConfigurationError(InfrastructureError):
    """Configuration-related errors."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if config_key:
            context["config_key"] = config_key
        if config_value is not None:
            context["config_value"] = str(config_value)
        
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            context=context,
            **kwargs,
        )


class DatabaseConnectionError(InfrastructureError):
    """Database connection errors."""
    
    def __init__(
        self,
        message: str,
        database_url: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if database_url:
            # Mask password in URL for logging
            masked_url = self._mask_password_in_url(database_url)
            context["database_url"] = masked_url
        
        super().__init__(
            message,
            error_code="DB_CONNECTION_ERROR",
            context=context,
            **kwargs,
        )
    
    @staticmethod
    def _mask_password_in_url(url: str) -> str:
        """Mask password in database URL for safe logging."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)


class DatabaseSessionError(InfrastructureError):
    """Database session errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="DB_SESSION_ERROR",
            **kwargs,
        )


class DatabaseHealthCheckError(InfrastructureError):
    """Database health check errors."""
    
    def __init__(
        self,
        message: str,
        response_time_ms: Optional[float] = None,
        consecutive_failures: Optional[int] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if response_time_ms is not None:
            context["response_time_ms"] = response_time_ms
        if consecutive_failures is not None:
            context["consecutive_failures"] = consecutive_failures
        
        super().__init__(
            message,
            error_code="DB_HEALTH_CHECK_ERROR",
            context=context,
            **kwargs,
        )


class SecurityError(InfrastructureError):
    """Security-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="SECURITY_ERROR",
            **kwargs,
        )


class AuthenticationError(SecurityError):
    """Authentication errors."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if user_id:
            context["user_id"] = str(user_id)
        if ip_address:
            context["ip_address"] = ip_address
        
        super().__init__(
            message,
            error_code="AUTH_ERROR",
            context=context,
            **kwargs,
        )


class TokenValidationError(AuthenticationError):
    """JWT token validation errors."""
    
    def __init__(
        self,
        message: str,
        token_type: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if token_type:
            context["token_type"] = token_type
        
        super().__init__(
            message,
            error_code="TOKEN_VALIDATION_ERROR",
            context=context,
            **kwargs,
        )


class AuthorizationError(SecurityError):
    """Authorization errors."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[UUID] = None,
        required_permission: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if user_id:
            context["user_id"] = str(user_id)
        if required_permission:
            context["required_permission"] = required_permission
        
        super().__init__(
            message,
            error_code="AUTHORIZATION_ERROR",
            context=context,
            **kwargs,
        )


class PermissionDeniedError(AuthorizationError):
    """Permission denied errors."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if resource_type:
            context["resource_type"] = resource_type
        if action:
            context["action"] = action
        
        super().__init__(
            message,
            error_code="PERMISSION_DENIED",
            context=context,
            **kwargs,
        )


class EventBusError(InfrastructureError):
    """Event bus errors."""
    
    def __init__(
        self,
        message: str,
        event_type: Optional[str] = None,
        event_id: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if event_type:
            context["event_type"] = event_type
        if event_id:
            context["event_id"] = event_id
        
        super().__init__(
            message,
            error_code="EVENT_BUS_ERROR",
            context=context,
            **kwargs,
        )


class EventHandlingError(EventBusError):
    """Event handling errors."""
    
    def __init__(
        self,
        message: str,
        handler_name: Optional[str] = None,
        retry_count: Optional[int] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if handler_name:
            context["handler_name"] = handler_name
        if retry_count is not None:
            context["retry_count"] = retry_count
        
        super().__init__(
            message,
            error_code="EVENT_HANDLING_ERROR",
            context=context,
            **kwargs,
        )


class LoggingError(InfrastructureError):
    """Logging system errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code="LOGGING_ERROR",
            **kwargs,
        )


class AuditLogError(LoggingError):
    """Audit logging errors."""
    
    def __init__(
        self,
        message: str,
        audit_event_type: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if audit_event_type:
            context["audit_event_type"] = audit_event_type
        
        super().__init__(
            message,
            error_code="AUDIT_LOG_ERROR",
            context=context,
            **kwargs,
        )


class CacheError(InfrastructureError):
    """Cache-related errors."""
    
    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if cache_key:
            context["cache_key"] = cache_key
        
        super().__init__(
            message,
            error_code="CACHE_ERROR",
            context=context,
            **kwargs,
        )


class ExternalServiceError(InfrastructureError):
    """External service integration errors."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if service_name:
            context["service_name"] = service_name
        if status_code:
            context["status_code"] = status_code
        if response_body:
            # Truncate response body for logging
            context["response_body"] = response_body[:1000] + "..." if len(response_body) > 1000 else response_body
        
        super().__init__(
            message,
            error_code="EXTERNAL_SERVICE_ERROR",
            context=context,
            **kwargs,
        )


class RateLimitError(InfrastructureError):
    """Rate limiting errors."""
    
    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if limit:
            context["limit"] = limit
        if window_seconds:
            context["window_seconds"] = window_seconds
        if retry_after_seconds:
            context["retry_after_seconds"] = retry_after_seconds
        
        super().__init__(
            message,
            error_code="RATE_LIMIT_ERROR",
            context=context,
            **kwargs,
        )


class ValidationError(InfrastructureError):
    """Data validation errors."""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = str(field_value)
        if validation_rule:
            context["validation_rule"] = validation_rule
        
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            context=context,
            **kwargs,
        )