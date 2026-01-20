"""Infrastructure decorators for cross-cutting concerns."""

import asyncio
import functools
import time
from typing import Any, Callable, Optional, Type, Union

import structlog

from .context import (
    AuditContext,
    ExecutionContext,
    get_current_audit_context,
    get_current_execution_context,
    set_audit_context,
    set_execution_context,
)
from .exceptions import InfrastructureError
from ..logging.audit_logger import AuditEventType, AuditLogger, AuditSeverity
from ..security.authorization import Action, ResourceType, RoleBasedAccessControl

logger = structlog.get_logger()


def with_execution_context(
    operation_type: Optional[str] = None,
    generate_correlation_id: bool = True,
):
    """Decorator to inject execution context into function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if context already exists
            existing_context = get_current_execution_context()
            if existing_context:
                return await func(*args, **kwargs)
            
            # Create new execution context
            context = ExecutionContext.create_for_system(
                operation_type=operation_type or func.__name__,
            )
            
            set_execution_context(context)
            try:
                return await func(*args, **kwargs)
            finally:
                set_execution_context(None)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Check if context already exists
            existing_context = get_current_execution_context()
            if existing_context:
                return func(*args, **kwargs)
            
            # Create new execution context
            context = ExecutionContext.create_for_system(
                operation_type=operation_type or func.__name__,
            )
            
            set_execution_context(context)
            try:
                return func(*args, **kwargs)
            finally:
                set_execution_context(None)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_audit_context(
    resource_type: str,
    action: str,
    business_justification: Optional[str] = None,
    regulatory_context: Optional[str] = None,
):
    """Decorator to inject audit context into function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get execution context
            execution_context = get_current_execution_context()
            if not execution_context:
                raise InfrastructureError("Execution context required for audit context")
            
            # Extract resource_id from kwargs if present
            resource_id = kwargs.get('resource_id') or kwargs.get('id')
            
            # Create audit context
            audit_context = AuditContext(
                execution_context=execution_context,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                business_justification=business_justification,
                regulatory_context=regulatory_context,
            )
            
            set_audit_context(audit_context)
            try:
                return await func(*args, **kwargs)
            finally:
                set_audit_context(None)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get execution context
            execution_context = get_current_execution_context()
            if not execution_context:
                raise InfrastructureError("Execution context required for audit context")
            
            # Extract resource_id from kwargs if present
            resource_id = kwargs.get('resource_id') or kwargs.get('id')
            
            # Create audit context
            audit_context = AuditContext(
                execution_context=execution_context,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                business_justification=business_justification,
                regulatory_context=regulatory_context,
            )
            
            set_audit_context(audit_context)
            try:
                return func(*args, **kwargs)
            finally:
                set_audit_context(None)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """Decorator for automatic retry with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            "Function failed after all retry attempts",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise
                    
                    # Calculate backoff delay
                    delay = backoff_factor * (2 ** attempt)
                    
                    logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        await on_retry(attempt, e)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # This should never be reached
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            "Function failed after all retry attempts",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise
                    
                    # Calculate backoff delay
                    delay = backoff_factor * (2 ** attempt)
                    
                    logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e)
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # This should never be reached
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_permission(
    resource: ResourceType,
    action: Action,
    context_extractor: Optional[Callable] = None,
):
    """Decorator for automatic permission checking."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get RBAC instance (in real implementation, this would be injected)
            rbac = RoleBasedAccessControl()
            
            # Extract user_id from kwargs or execution context
            user_id = kwargs.get('user_id')
            if not user_id:
                execution_context = get_current_execution_context()
                if execution_context and execution_context.user_id:
                    user_id = execution_context.user_id
            
            if not user_id:
                raise InfrastructureError("User ID required for permission check")
            
            # Extract context if extractor provided
            context = None
            if context_extractor:
                context = context_extractor(*args, **kwargs)
            
            # Get execution context for audit
            execution_context = get_current_execution_context()
            
            # Check permission
            await rbac.require_permission(
                user_id=user_id,
                resource=resource,
                action=action,
                context=context,
                execution_context=execution_context,
            )
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Sync version would need to be implemented differently
            # For now, raise error for sync functions
            raise InfrastructureError("Permission decorator only supports async functions")
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_performance_monitoring(
    log_slow_queries: bool = True,
    slow_threshold_ms: float = 1000.0,
):
    """Decorator for performance monitoring and logging."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Calculate execution time
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Log performance metrics
                log_data = {
                    "function": func.__name__,
                    "execution_time_ms": execution_time_ms,
                    "success": True,
                }
                
                if execution_time_ms > slow_threshold_ms and log_slow_queries:
                    logger.warning("Slow function execution", **log_data)
                else:
                    logger.debug("Function execution completed", **log_data)
                
                return result
                
            except Exception as e:
                # Calculate execution time even for failures
                execution_time_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    "Function execution failed",
                    function=func.__name__,
                    execution_time_ms=execution_time_ms,
                    success=False,
                    error=str(e),
                )
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Calculate execution time
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Log performance metrics
                log_data = {
                    "function": func.__name__,
                    "execution_time_ms": execution_time_ms,
                    "success": True,
                }
                
                if execution_time_ms > slow_threshold_ms and log_slow_queries:
                    logger.warning("Slow function execution", **log_data)
                else:
                    logger.debug("Function execution completed", **log_data)
                
                return result
                
            except Exception as e:
                # Calculate execution time even for failures
                execution_time_ms = (time.time() - start_time) * 1000
                
                logger.error(
                    "Function execution failed",
                    function=func.__name__,
                    execution_time_ms=execution_time_ms,
                    success=False,
                    error=str(e),
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_audit_logging(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
    message_template: Optional[str] = None,
):
    """Decorator for automatic audit logging."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get audit logger (in real implementation, this would be injected)
            audit_logger = AuditLogger("audit_key")  # This should come from config
            
            # Get contexts
            execution_context = get_current_execution_context()
            audit_context = get_current_audit_context()
            
            # Create audit message
            message = message_template or f"Function {func.__name__} executed"
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful execution
                await audit_logger.log_audit_event(
                    event_type=event_type,
                    message=f"{message} - SUCCESS",
                    severity=severity,
                    user_id=execution_context.user_id if execution_context else None,
                    resource_type=audit_context.resource_type if audit_context else None,
                    resource_id=audit_context.resource_id if audit_context else None,
                    action=audit_context.action if audit_context else func.__name__,
                    details={"success": True},
                    execution_context=execution_context,
                    business_justification=audit_context.business_justification if audit_context else None,
                    regulatory_context=audit_context.regulatory_context if audit_context else None,
                )
                
                return result
                
            except Exception as e:
                # Log failed execution
                await audit_logger.log_audit_event(
                    event_type=event_type,
                    message=f"{message} - FAILED",
                    severity=AuditSeverity.HIGH,
                    user_id=execution_context.user_id if execution_context else None,
                    resource_type=audit_context.resource_type if audit_context else None,
                    resource_id=audit_context.resource_id if audit_context else None,
                    action=audit_context.action if audit_context else func.__name__,
                    details={"success": False, "error": str(e)},
                    execution_context=execution_context,
                    business_justification=audit_context.business_justification if audit_context else None,
                    regulatory_context=audit_context.regulatory_context if audit_context else None,
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Sync version would need different implementation
            raise InfrastructureError("Audit logging decorator only supports async functions")
    
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
):
    """Circuit breaker decorator to prevent cascading failures."""
    def decorator(func: Callable) -> Callable:
        # Circuit breaker state
        state = {
            "failures": 0,
            "last_failure_time": None,
            "state": "closed",  # closed, open, half-open
        }
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Check if circuit should be half-open
            if (state["state"] == "open" and 
                state["last_failure_time"] and 
                current_time - state["last_failure_time"] > recovery_timeout):
                state["state"] = "half-open"
                logger.info(
                    "Circuit breaker transitioning to half-open",
                    function=func.__name__,
                )
            
            # Reject calls if circuit is open
            if state["state"] == "open":
                raise InfrastructureError(
                    f"Circuit breaker is open for {func.__name__}",
                    error_code="CIRCUIT_BREAKER_OPEN",
                    context={
                        "function": func.__name__,
                        "failures": state["failures"],
                        "last_failure_time": state["last_failure_time"],
                    },
                )
            
            try:
                result = await func(*args, **kwargs)
                
                # Reset on success
                if state["failures"] > 0:
                    logger.info(
                        "Circuit breaker reset after successful call",
                        function=func.__name__,
                        previous_failures=state["failures"],
                    )
                    state["failures"] = 0
                    state["last_failure_time"] = None
                    state["state"] = "closed"
                
                return result
                
            except expected_exception as e:
                state["failures"] += 1
                state["last_failure_time"] = current_time
                
                # Open circuit if threshold reached
                if state["failures"] >= failure_threshold:
                    state["state"] = "open"
                    logger.error(
                        "Circuit breaker opened due to failures",
                        function=func.__name__,
                        failures=state["failures"],
                        threshold=failure_threshold,
                    )
                
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Sync version would need different implementation
            raise InfrastructureError("Circuit breaker decorator only supports async functions")
    
    return decorator