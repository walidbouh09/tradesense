"""Structured logging with correlation tracking and sensitive data masking."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import structlog
from structlog.types import FilteringBoundLogger

from ..config.settings import LoggingConfig
from ..common.context import ExecutionContext
from ..common.exceptions import LoggingError

# Global logger instance
_logger: Optional[FilteringBoundLogger] = None


class SensitiveDataMasker:
    """Masks sensitive data in log messages."""
    
    def __init__(self, sensitive_fields: List[str]):
        self.sensitive_fields = set(field.lower() for field in sensitive_fields)
        self.mask_value = "***MASKED***"
    
    def mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask sensitive fields in dictionary."""
        if not isinstance(data, dict):
            return data
        
        masked_data = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            if key_lower in self.sensitive_fields:
                masked_data[key] = self.mask_value
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value)
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked_data[key] = value
        
        return masked_data
    
    def mask_string(self, text: str) -> str:
        """Mask sensitive patterns in string."""
        # Common patterns to mask
        patterns = [
            (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 'XXXX-XXXX-XXXX-XXXX'),  # Credit card
            (r'\b\d{3}-\d{2}-\d{4}\b', 'XXX-XX-XXXX'),  # SSN
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'email@masked.com'),  # Email
        ]
        
        import re
        masked_text = text
        
        for pattern, replacement in patterns:
            masked_text = re.sub(pattern, replacement, masked_text)
        
        return masked_text


class CorrelationProcessor:
    """Adds correlation context to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        # Add correlation ID from context
        from ..common.context import get_current_execution_context
        
        context = get_current_execution_context()
        if context:
            event_dict["correlation_id"] = context.correlation_id
            event_dict["user_id"] = str(context.user_id) if context.user_id else None
            event_dict["session_id"] = context.session_id
        
        return event_dict


class TimestampProcessor:
    """Adds ISO timestamp to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return event_dict


class SensitiveDataProcessor:
    """Masks sensitive data in log records."""
    
    def __init__(self, masker: SensitiveDataMasker):
        self.masker = masker
    
    def __call__(self, logger, method_name, event_dict):
        # Mask sensitive data in event dict
        masked_dict = self.masker.mask_dict(event_dict)
        
        # Mask sensitive data in the main event message
        if "event" in masked_dict and isinstance(masked_dict["event"], str):
            masked_dict["event"] = self.masker.mask_string(masked_dict["event"])
        
        return masked_dict


class StructuredLoggerManager:
    """Manages structured logging configuration and setup."""
    
    def __init__(self, config: LoggingConfig):
        self.config = config
        self.masker = SensitiveDataMasker(config.sensitive_fields)
        self._configured = False
    
    def configure_logging(self) -> FilteringBoundLogger:
        """Configure structured logging with all processors."""
        if self._configured:
            return structlog.get_logger()
        
        # Configure standard library logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, self.config.level),
        )
        
        # Build processor chain
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            TimestampProcessor(),
            CorrelationProcessor(),
            SensitiveDataProcessor(self.masker),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]
        
        # Add appropriate renderer based on format
        if self.config.format.lower() == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        # Configure structlog
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        self._configured = True
        
        logger = structlog.get_logger()
        logger.info(
            "Structured logging configured",
            level=self.config.level,
            format=self.config.format,
            sensitive_fields_count=len(self.config.sensitive_fields),
        )
        
        return logger


class ContextualLogger:
    """Logger with automatic context injection."""
    
    def __init__(self, logger: FilteringBoundLogger, context: Optional[Dict[str, Any]] = None):
        self.logger = logger
        self.context = context or {}
    
    def with_context(self, **additional_context) -> "ContextualLogger":
        """Create new logger with additional context."""
        merged_context = {**self.context, **additional_context}
        return ContextualLogger(self.logger, merged_context)
    
    def _log(self, level: str, message: str, **kwargs) -> None:
        """Internal logging method with context injection."""
        log_data = {**self.context, **kwargs}
        getattr(self.logger, level)(message, **log_data)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """Log error message with optional exception."""
        if exception:
            kwargs["exception"] = str(exception)
            kwargs["exception_type"] = type(exception).__name__
        self._log("error", message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log("critical", message, **kwargs)


class BusinessEventLogger:
    """Specialized logger for business events."""
    
    def __init__(self, logger: FilteringBoundLogger):
        self.logger = logger
    
    def log_business_event(
        self,
        event_type: str,
        user_id: Optional[UUID],
        resource_type: str,
        resource_id: Optional[UUID],
        action: str,
        details: Optional[Dict[str, Any]] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> None:
        """Log business event with structured format."""
        log_data = {
            "event_category": "business",
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "action": action,
            "details": details or {},
        }
        
        if execution_context:
            log_data.update({
                "correlation_id": execution_context.correlation_id,
                "session_id": execution_context.session_id,
                "ip_address": execution_context.ip_address,
            })
        
        self.logger.info("Business event", **log_data)
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[UUID],
        ip_address: Optional[str],
        user_agent: Optional[str],
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log security event."""
        log_data = {
            "event_category": "security",
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "details": details or {},
        }
        
        level = "info" if success else "warning"
        getattr(self.logger, level)("Security event", **log_data)
    
    def log_system_event(
        self,
        event_type: str,
        component: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log system event."""
        log_data = {
            "event_category": "system",
            "event_type": event_type,
            "component": component,
            "status": status,
            "details": details or {},
        }
        
        level = "info" if status == "success" else "error"
        getattr(self.logger, level)("System event", **log_data)


def configure_logging(config: LoggingConfig) -> FilteringBoundLogger:
    """Configure global structured logging."""
    global _logger
    
    if _logger is None:
        manager = StructuredLoggerManager(config)
        _logger = manager.configure_logging()
    
    return _logger


def get_logger(name: Optional[str] = None) -> FilteringBoundLogger:
    """Get configured logger instance."""
    if _logger is None:
        raise LoggingError("Logging not configured. Call configure_logging() first.")
    
    if name:
        return _logger.bind(logger_name=name)
    
    return _logger


def get_contextual_logger(
    name: Optional[str] = None,
    **context
) -> ContextualLogger:
    """Get contextual logger with automatic context injection."""
    base_logger = get_logger(name)
    return ContextualLogger(base_logger, context)


def get_business_logger() -> BusinessEventLogger:
    """Get business event logger."""
    base_logger = get_logger("business")
    return BusinessEventLogger(base_logger)