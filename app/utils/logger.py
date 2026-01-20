"""
TradeSense AI - Logging Utilities

Professional logging configuration with structured logging,
multiple handlers, and proper formatting for the trading platform.
"""

import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from flask import Flask, g, has_request_context, request
from pythonjsonlogger import jsonlogger


class RequestContextFilter(logging.Filter):
    """Add Flask request context to log records."""

    def filter(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
            record.request_id = getattr(g, "request_id", None)
            record.user_id = getattr(g, "current_user_id", None)
            record.method = request.method
        else:
            record.url = None
            record.remote_addr = None
            record.request_id = None
            record.user_id = None
            record.method = None
        return True


class TradeSenseFormatter(logging.Formatter):
    """Custom formatter with enhanced information."""

    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.utcnow().isoformat()

        # Add service info
        record.service = "tradesense-api"
        record.version = os.getenv("APP_VERSION", "1.0.0")
        record.environment = os.getenv("FLASK_ENV", "development")

        return super().format(record)


def setup_logging(app: Flask) -> None:
    """
    Setup comprehensive logging for the application.

    Args:
        app: Flask application instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get log level from config
    log_level = app.config.get("LOG_LEVEL", "INFO").upper()
    log_file = app.config.get("LOG_FILE", "logs/tradesense.log")

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": TradeSenseFormatter,
                "format": "[%(timestamp)s] %(levelname)s in %(name)s [%(service)s:%(version)s:%(environment)s]: %(message)s"
                " [req_id:%(request_id)s user:%(user_id)s %(remote_addr)s %(method)s %(url)s]",
            },
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(timestamp)s %(name)s %(levelname)s %(message)s %(service)s %(version)s "
                "%(environment)s %(request_id)s %(user_id)s %(remote_addr)s %(method)s %(url)s",
            },
            "detailed": {
                "()": TradeSenseFormatter,
                "format": "[%(timestamp)s] %(levelname)s in %(name)s [%(filename)s:%(lineno)d] "
                "[%(service)s:%(version)s:%(environment)s]: %(message)s"
                " [req_id:%(request_id)s user:%(user_id)s %(remote_addr)s %(method)s %(url)s]",
            },
        },
        "filters": {
            "request_context": {
                "()": RequestContextFilter,
            }
        },
        "handlers": {
            "console": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["request_context"],
                "stream": sys.stdout,
            },
            "file": {
                "level": "INFO",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filters": ["request_context"],
                "filename": log_file,
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf8",
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filters": ["request_context"],
                "filename": "logs/tradesense_errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "tradesense": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if not app.debug else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "werkzeug": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "socketio": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }

    # Apply logging configuration
    logging.config.dictConfig(logging_config)

    # Set application logger
    app.logger.setLevel(getattr(logging, log_level))

    # Add custom log methods to app
    app.log_info = lambda msg, **kwargs: app.logger.info(msg, extra=kwargs)
    app.log_error = lambda msg, **kwargs: app.logger.error(msg, extra=kwargs)
    app.log_warning = lambda msg, **kwargs: app.logger.warning(msg, extra=kwargs)
    app.log_debug = lambda msg, **kwargs: app.logger.debug(msg, extra=kwargs)

    # Log startup
    app.logger.info(
        "Logging system initialized",
        extra={
            "log_level": log_level,
            "log_file": log_file,
            "environment": app.config.get("ENV", "unknown"),
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_trade_event(
    event_type: str, trade_id: str, user_id: str, symbol: str, **kwargs
) -> None:
    """
    Log trading-related events with structured data.

    Args:
        event_type: Type of trade event (created, executed, cancelled, etc.)
        trade_id: Trade identifier
        user_id: User identifier
        symbol: Trading symbol
        **kwargs: Additional event data
    """
    logger = get_logger("tradesense.trading")

    event_data = {
        "event_type": event_type,
        "trade_id": trade_id,
        "user_id": user_id,
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }

    logger.info(f"Trade event: {event_type}", extra=event_data)


def log_market_data_event(
    event_type: str,
    symbol: str,
    price: Optional[float] = None,
    volume: Optional[float] = None,
    **kwargs,
) -> None:
    """
    Log market data events.

    Args:
        event_type: Type of market event (price_update, data_fetch, etc.)
        symbol: Trading symbol
        price: Current price
        volume: Volume data
        **kwargs: Additional event data
    """
    logger = get_logger("tradesense.market_data")

    event_data = {
        "event_type": event_type,
        "symbol": symbol,
        "price": price,
        "volume": volume,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }

    logger.info(f"Market data event: {event_type}", extra=event_data)


def log_payment_event(
    event_type: str,
    payment_id: str,
    user_id: str,
    amount: float,
    currency: str = "USD",
    **kwargs,
) -> None:
    """
    Log payment-related events.

    Args:
        event_type: Type of payment event (created, processed, failed, etc.)
        payment_id: Payment identifier
        user_id: User identifier
        amount: Payment amount
        currency: Payment currency
        **kwargs: Additional event data
    """
    logger = get_logger("tradesense.payments")

    event_data = {
        "event_type": event_type,
        "payment_id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "currency": currency,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }

    logger.info(f"Payment event: {event_type}", extra=event_data)


def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Log security-related events.

    Args:
        event_type: Type of security event (login, logout, failed_auth, etc.)
        user_id: User identifier
        ip_address: Client IP address
        user_agent: Client user agent
        **kwargs: Additional event data
    """
    logger = get_logger("tradesense.security")

    event_data = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }

    logger.warning(f"Security event: {event_type}", extra=event_data)


def log_performance_metric(
    metric_name: str, metric_value: float, metric_unit: str = "ms", **kwargs
) -> None:
    """
    Log performance metrics.

    Args:
        metric_name: Name of the metric
        metric_value: Metric value
        metric_unit: Unit of measurement
        **kwargs: Additional metric data
    """
    logger = get_logger("tradesense.performance")

    metric_data = {
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": metric_unit,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs,
    }

    logger.info(f"Performance metric: {metric_name}", extra=metric_data)


class LoggingMiddleware:
    """Middleware for request/response logging."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.requests")

    def __call__(self, environ, start_response):
        """Process request and log details."""

        def new_start_response(status, response_headers, exc_info=None):
            # Log response
            self.logger.info(f"Response: {status}")
            return start_response(status, response_headers, exc_info)

        return self.app(environ, new_start_response)


# Context manager for performance logging
class PerformanceLogger:
    """Context manager for logging execution time."""

    def __init__(
        self, operation_name: str, logger_name: str = "tradesense.performance"
    ):
        self.operation_name = operation_name
        self.logger = get_logger(logger_name)
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.debug(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000

            if exc_type:
                self.logger.error(
                    f"Operation failed: {self.operation_name}",
                    extra={
                        "operation": self.operation_name,
                        "duration_ms": duration,
                        "error": str(exc_val),
                    },
                )
            else:
                self.logger.info(
                    f"Operation completed: {self.operation_name}",
                    extra={"operation": self.operation_name, "duration_ms": duration},
                )


# Decorator for automatic function logging
def log_function_call(logger_name: str = "tradesense.functions"):
    """
    Decorator to automatically log function calls and execution time.

    Args:
        logger_name: Name of the logger to use
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = f"{func.__module__}.{func.__name__}"

            with PerformanceLogger(func_name, logger_name):
                try:
                    result = func(*args, **kwargs)
                    logger.debug(f"Function executed successfully: {func_name}")
                    return result
                except Exception as e:
                    logger.error(f"Function failed: {func_name} - {str(e)}")
                    raise

        return wrapper

    return decorator
