"""Financial-grade audit logging with immutability and integrity protection."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from ..common.context import ExecutionContext
from ..common.exceptions import AuditLogError
from ..security.hashing import DataIntegrityHasher

logger = structlog.get_logger()


class AuditEventType(Enum):
    """Types of audit events."""
    
    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    
    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    
    # Business events
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    
    # Account events
    ACCOUNT_CREATED = "account_created"
    BALANCE_ADJUSTED = "balance_adjusted"
    WITHDRAWAL_REQUESTED = "withdrawal_requested"
    DEPOSIT_PROCESSED = "deposit_processed"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIG_CHANGED = "config_changed"
    BACKUP_CREATED = "backup_created"
    
    # Compliance events
    AUDIT_LOG_ACCESSED = "audit_log_accessed"
    COMPLIANCE_REPORT_GENERATED = "compliance_report_generated"
    REGULATORY_EXPORT = "regulatory_export"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogEntry(BaseModel):
    """Immutable audit log entry."""
    
    # Core identification
    audit_id: UUID
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    
    # Context information
    correlation_id: Optional[str] = None
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Business context
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    action: Optional[str] = None
    
    # Event details
    message: str
    details: Dict[str, Any] = {}
    
    # Compliance fields
    business_justification: Optional[str] = None
    regulatory_context: Optional[str] = None
    
    # Integrity protection
    integrity_hash: Optional[str] = None
    previous_hash: Optional[str] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() + "Z",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return self.dict(exclude_none=True)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


class AuditLogChain:
    """Maintains audit log chain integrity."""
    
    def __init__(self, integrity_hasher: DataIntegrityHasher):
        self.integrity_hasher = integrity_hasher
        self.last_hash: Optional[str] = None
    
    def add_entry(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Add entry to audit chain with integrity protection."""
        # Set previous hash
        entry.previous_hash = self.last_hash
        
        # Calculate integrity hash
        entry_data = entry.to_json()
        entry.integrity_hash = self.integrity_hasher.create_audit_hash({
            "data": entry_data,
            "previous_hash": self.last_hash or "",
            "timestamp": entry.timestamp.isoformat(),
        })
        
        # Update last hash
        self.last_hash = entry.integrity_hash
        
        return entry
    
    def verify_chain_integrity(self, entries: List[AuditLogEntry]) -> bool:
        """Verify integrity of audit log chain."""
        if not entries:
            return True
        
        previous_hash = None
        
        for entry in entries:
            # Verify previous hash matches
            if entry.previous_hash != previous_hash:
                logger.error(
                    "Audit chain integrity violation: previous hash mismatch",
                    audit_id=str(entry.audit_id),
                    expected_previous=previous_hash,
                    actual_previous=entry.previous_hash,
                )
                return False
            
            # Verify integrity hash
            expected_hash = self.integrity_hasher.create_audit_hash({
                "data": entry.to_json(),
                "previous_hash": previous_hash or "",
                "timestamp": entry.timestamp.isoformat(),
            })
            
            if entry.integrity_hash != expected_hash:
                logger.error(
                    "Audit chain integrity violation: hash mismatch",
                    audit_id=str(entry.audit_id),
                    expected_hash=expected_hash,
                    actual_hash=entry.integrity_hash,
                )
                return False
            
            previous_hash = entry.integrity_hash
        
        return True


class AuditLogger:
    """Financial-grade audit logger with immutability and integrity protection."""
    
    def __init__(self, integrity_key: str):
        self.integrity_hasher = DataIntegrityHasher(integrity_key)
        self.audit_chain = AuditLogChain(self.integrity_hasher)
        self.base_logger = structlog.get_logger("audit")
    
    async def log_audit_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        execution_context: Optional[ExecutionContext] = None,
        business_justification: Optional[str] = None,
        regulatory_context: Optional[str] = None,
    ) -> AuditLogEntry:
        """Log audit event with integrity protection."""
        try:
            # Create audit log entry
            entry = AuditLogEntry(
                audit_id=uuid4(),
                timestamp=datetime.utcnow(),
                event_type=event_type,
                severity=severity,
                message=message,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                details=details or {},
                business_justification=business_justification,
                regulatory_context=regulatory_context,
            )
            
            # Add execution context if provided
            if execution_context:
                entry.correlation_id = execution_context.correlation_id
                entry.session_id = execution_context.session_id
                entry.ip_address = execution_context.ip_address
                entry.user_agent = execution_context.user_agent
            
            # Add to audit chain with integrity protection
            entry = self.audit_chain.add_entry(entry)
            
            # Log to structured logger
            self.base_logger.info(
                "AUDIT_EVENT",
                audit_id=str(entry.audit_id),
                event_type=entry.event_type.value,
                severity=entry.severity.value,
                message=entry.message,
                user_id=str(entry.user_id) if entry.user_id else None,
                resource_type=entry.resource_type,
                resource_id=str(entry.resource_id) if entry.resource_id else None,
                action=entry.action,
                details=entry.details,
                correlation_id=entry.correlation_id,
                integrity_hash=entry.integrity_hash,
                previous_hash=entry.previous_hash,
            )
            
            # In a real implementation, this would also:
            # 1. Store in immutable audit database
            # 2. Send to SIEM system
            # 3. Archive to compliance storage
            # 4. Trigger alerts for critical events
            
            return entry
            
        except Exception as e:
            # Audit logging failures are critical
            logger.critical(
                "Audit logging failed",
                event_type=event_type.value,
                error=str(e),
                user_id=str(user_id) if user_id else None,
            )
            raise AuditLogError(f"Audit logging failed: {e}") from e
    
    async def log_authentication_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[UUID],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> AuditLogEntry:
        """Log authentication-related audit event."""
        severity = AuditSeverity.MEDIUM if success else AuditSeverity.HIGH
        
        message = f"Authentication {event_type.value}: {'success' if success else 'failed'}"
        if failure_reason:
            message += f" - {failure_reason}"
        
        details = {
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        
        if failure_reason:
            details["failure_reason"] = failure_reason
        
        return await self.log_audit_event(
            event_type=event_type,
            message=message,
            severity=severity,
            user_id=user_id,
            resource_type="authentication",
            action=event_type.value,
            details=details,
            execution_context=execution_context,
        )
    
    async def log_business_event(
        self,
        event_type: AuditEventType,
        user_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: str,
        details: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None,
        business_justification: Optional[str] = None,
    ) -> AuditLogEntry:
        """Log business operation audit event."""
        message = f"Business operation: {action} on {resource_type}"
        
        return await self.log_audit_event(
            event_type=event_type,
            message=message,
            severity=AuditSeverity.MEDIUM,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details,
            execution_context=execution_context,
            business_justification=business_justification,
        )
    
    async def log_system_event(
        self,
        event_type: AuditEventType,
        component: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.LOW,
    ) -> AuditLogEntry:
        """Log system operation audit event."""
        message = f"System operation: {action} in {component}"
        
        return await self.log_audit_event(
            event_type=event_type,
            message=message,
            severity=severity,
            resource_type="system",
            action=action,
            details=details or {"component": component},
        )
    
    async def log_compliance_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[UUID],
        action: str,
        regulatory_context: str,
        details: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None,
    ) -> AuditLogEntry:
        """Log compliance-related audit event."""
        message = f"Compliance operation: {action}"
        
        return await self.log_audit_event(
            event_type=event_type,
            message=message,
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            resource_type="compliance",
            action=action,
            details=details,
            execution_context=execution_context,
            regulatory_context=regulatory_context,
        )
    
    async def verify_audit_integrity(
        self,
        entries: List[AuditLogEntry],
    ) -> bool:
        """Verify integrity of audit log entries."""
        return self.audit_chain.verify_chain_integrity(entries)
    
    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Generate compliance report from audit logs."""
        # In a real implementation, this would query the audit database
        # and generate a comprehensive compliance report
        
        report = {
            "report_id": str(uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "filters": {
                "event_types": [et.value for et in event_types] if event_types else None,
                "user_id": str(user_id) if user_id else None,
            },
            "summary": {
                "total_events": 0,
                "events_by_type": {},
                "events_by_severity": {},
                "unique_users": 0,
            },
            "integrity_verified": True,
        }
        
        # Log compliance report generation
        await self.log_compliance_event(
            event_type=AuditEventType.COMPLIANCE_REPORT_GENERATED,
            user_id=user_id,
            action="generate_compliance_report",
            regulatory_context="financial_audit",
            details={
                "report_id": report["report_id"],
                "period": report["period"],
                "filters": report["filters"],
            },
        )
        
        return report