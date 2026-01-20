"""Execution context management for request tracking and audit trails."""

import contextvars
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel


class ExecutionContext(BaseModel):
    """Execution context for request/operation tracking."""
    
    correlation_id: str
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime
    operation_type: Optional[str] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() + "Z",
        }
    
    @classmethod
    def create_for_request(
        cls,
        request: Request,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ) -> "ExecutionContext":
        """Create execution context from HTTP request."""
        # Extract correlation ID from headers or generate new one
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        
        # Extract client information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        
        return cls(
            correlation_id=correlation_id,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
            operation_type="http_request",
        )
    
    @classmethod
    def create_for_worker(
        cls,
        worker_name: str,
        correlation_id: Optional[str] = None,
    ) -> "ExecutionContext":
        """Create execution context for background worker."""
        return cls(
            correlation_id=correlation_id or f"worker_{uuid4()}",
            timestamp=datetime.utcnow(),
            operation_type=f"worker_{worker_name}",
        )
    
    @classmethod
    def create_for_system(
        cls,
        operation_type: str,
        correlation_id: Optional[str] = None,
    ) -> "ExecutionContext":
        """Create execution context for system operations."""
        return cls(
            correlation_id=correlation_id or f"system_{uuid4()}",
            timestamp=datetime.utcnow(),
            operation_type=operation_type,
        )
    
    def with_user(self, user_id: UUID, session_id: Optional[str] = None) -> "ExecutionContext":
        """Create new context with user information."""
        return self.copy(update={
            "user_id": user_id,
            "session_id": session_id,
        })
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return self.dict(exclude_none=True)


class AuditContext(BaseModel):
    """Audit context for compliance tracking."""
    
    execution_context: ExecutionContext
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    action: Optional[str] = None
    business_justification: Optional[str] = None
    regulatory_context: Optional[str] = None
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() + "Z",
        }
    
    @classmethod
    def create_for_business_operation(
        cls,
        execution_context: ExecutionContext,
        resource_type: str,
        resource_id: UUID,
        action: str,
        business_justification: Optional[str] = None,
    ) -> "AuditContext":
        """Create audit context for business operations."""
        return cls(
            execution_context=execution_context,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            business_justification=business_justification,
        )
    
    @classmethod
    def create_for_compliance_operation(
        cls,
        execution_context: ExecutionContext,
        action: str,
        regulatory_context: str,
        business_justification: Optional[str] = None,
    ) -> "AuditContext":
        """Create audit context for compliance operations."""
        return cls(
            execution_context=execution_context,
            resource_type="compliance",
            action=action,
            regulatory_context=regulatory_context,
            business_justification=business_justification,
        )
    
    def to_audit_record(self) -> dict:
        """Convert to audit record format."""
        record = self.execution_context.to_dict()
        
        if self.resource_type:
            record["resource_type"] = self.resource_type
        if self.resource_id:
            record["resource_id"] = str(self.resource_id)
        if self.action:
            record["action"] = self.action
        if self.business_justification:
            record["business_justification"] = self.business_justification
        if self.regulatory_context:
            record["regulatory_context"] = self.regulatory_context
        
        return record


# Context variables for thread-local storage
_execution_context: contextvars.ContextVar[Optional[ExecutionContext]] = contextvars.ContextVar(
    "execution_context", default=None
)

_audit_context: contextvars.ContextVar[Optional[AuditContext]] = contextvars.ContextVar(
    "audit_context", default=None
)


def set_execution_context(context: ExecutionContext) -> None:
    """Set execution context for current operation."""
    _execution_context.set(context)


def get_current_execution_context() -> Optional[ExecutionContext]:
    """Get current execution context."""
    return _execution_context.get()


def clear_execution_context() -> None:
    """Clear current execution context."""
    _execution_context.set(None)


def set_audit_context(context: AuditContext) -> None:
    """Set audit context for current operation."""
    _audit_context.set(context)


def get_current_audit_context() -> Optional[AuditContext]:
    """Get current audit context."""
    return _audit_context.get()


def clear_audit_context() -> None:
    """Clear current audit context."""
    _audit_context.set(None)


def with_execution_context(context: ExecutionContext):
    """Context manager for execution context."""
    class ExecutionContextManager:
        def __enter__(self):
            set_execution_context(context)
            return context
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            clear_execution_context()
    
    return ExecutionContextManager()


def with_audit_context(context: AuditContext):
    """Context manager for audit context."""
    class AuditContextManager:
        def __enter__(self):
            set_audit_context(context)
            return context
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            clear_audit_context()
    
    return AuditContextManager()


async def with_async_execution_context(context: ExecutionContext):
    """Async context manager for execution context."""
    class AsyncExecutionContextManager:
        async def __aenter__(self):
            set_execution_context(context)
            return context
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            clear_execution_context()
    
    return AsyncExecutionContextManager()


async def with_async_audit_context(context: AuditContext):
    """Async context manager for audit context."""
    class AsyncAuditContextManager:
        async def __aenter__(self):
            set_audit_context(context)
            return context
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            clear_audit_context()
    
    return AsyncAuditContextManager()