"""
TradeSense AI - Exception Handling Utilities

Comprehensive exception handling system with proper error responses,
logging, and monitoring for the trading platform.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException


class TradeSenseException(Exception):
    """Base exception class for TradeSense AI."""

    def __init__(
        self,
        message: str,
        code: str = "TRADESENSE_ERROR",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(TradeSenseException):
    """Authentication related errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="AUTH_ERROR", status_code=401, details=details
        )


class AuthorizationError(TradeSenseException):
    """Authorization related errors."""

    def __init__(
        self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message, code="AUTHZ_ERROR", status_code=403, details=details
        )


class ValidationError(TradeSenseException):
    """Data validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="VALIDATION_ERROR", status_code=400, details=details
        )
        self.field = field


class NotFoundError(TradeSenseException):
    """Resource not found errors."""

    def __init__(
        self, resource: str = "Resource", details: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource} not found"
        super().__init__(
            message=message, code="NOT_FOUND", status_code=404, details=details
        )


class ConflictError(TradeSenseException):
    """Resource conflict errors."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="CONFLICT", status_code=409, details=details
        )


class BusinessLogicError(TradeSenseException):
    """Business logic violation errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message, code="BUSINESS_ERROR", status_code=422, details=details
        )


class TradingError(TradeSenseException):
    """Trading operation errors."""

    def __init__(
        self,
        message: str,
        trade_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="TRADING_ERROR", status_code=422, details=details
        )
        self.trade_id = trade_id


class MarketDataError(TradeSenseException):
    """Market data related errors."""

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="MARKET_DATA_ERROR", status_code=503, details=details
        )
        self.symbol = symbol


class PaymentError(TradeSenseException):
    """Payment processing errors."""

    def __init__(
        self,
        message: str,
        payment_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="PAYMENT_ERROR", status_code=422, details=details
        )
        self.payment_id = payment_id


class RateLimitError(TradeSenseException):
    """Rate limiting errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="RATE_LIMIT_ERROR", status_code=429, details=details
        )
        self.retry_after = retry_after


class ExternalServiceError(TradeSenseException):
    """External service integration errors."""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details=details,
        )
        self.service = service


class DatabaseError(TradeSenseException):
    """Database operation errors."""

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message, code="DATABASE_ERROR", status_code=500, details=details
        )
        self.operation = operation


def create_error_response(
    error: Exception, request_id: Optional[str] = None, include_traceback: bool = False
) -> Tuple[Dict[str, Any], int]:
    """
    Create standardized error response.

    Args:
        error: Exception instance
        request_id: Optional request ID for tracking
        include_traceback: Include traceback in response (development only)

    Returns:
        Tuple of (response_dict, status_code)
    """
    if isinstance(error, TradeSenseException):
        response = {
            "error": {
                "code": error.code,
                "message": error.message,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        if error.details:
            response["error"]["details"] = error.details

        if request_id:
            response["error"]["request_id"] = request_id

        if include_traceback:
            response["error"]["traceback"] = traceback.format_exc()

        return response, error.status_code

    elif isinstance(error, HTTPException):
        response = {
            "error": {
                "code": "HTTP_ERROR",
                "message": error.description or "HTTP error occurred",
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        if request_id:
            response["error"]["request_id"] = request_id

        return response, error.code

    else:
        # Generic server error
        response = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        if request_id:
            response["error"]["request_id"] = request_id

        if include_traceback:
            response["error"]["traceback"] = traceback.format_exc()
            response["error"]["original_message"] = str(error)

        return response, 500


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for the Flask application."""

    logger = logging.getLogger(__name__)

    @app.errorhandler(TradeSenseException)
    def handle_tradesense_exception(error: TradeSenseException):
        """Handle custom TradeSense exceptions."""
        request_id = getattr(request, "id", None)

        # Log the error
        if error.status_code >= 500:
            logger.error(
                f"TradeSense error: {error.code} - {error.message}",
                extra={
                    "request_id": request_id,
                    "error_code": error.code,
                    "user_agent": request.headers.get("User-Agent"),
                    "ip_address": request.remote_addr,
                    "details": error.details,
                },
            )
        else:
            logger.warning(
                f"TradeSense warning: {error.code} - {error.message}",
                extra={
                    "request_id": request_id,
                    "error_code": error.code,
                    "details": error.details,
                },
            )

        response, status_code = create_error_response(
            error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation_error(error: ValidationError):
        """Handle Marshmallow validation errors."""
        request_id = getattr(request, "id", None)

        logger.warning(
            f"Validation error: {error.messages}",
            extra={"request_id": request_id, "validation_errors": error.messages},
        )

        validation_error = ValidationError(
            message="Input validation failed",
            details={"validation_errors": error.messages},
        )

        response, status_code = create_error_response(
            validation_error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error: IntegrityError):
        """Handle database integrity constraint errors."""
        request_id = getattr(request, "id", None)

        logger.error(
            f"Database integrity error: {str(error)}",
            extra={"request_id": request_id, "original_error": str(error.orig)},
        )

        # Check for common integrity violations
        if "duplicate key" in str(error.orig).lower():
            db_error = ConflictError(
                message="Resource already exists",
                details={"constraint": "unique_constraint"},
            )
        elif "foreign key" in str(error.orig).lower():
            db_error = ValidationError(
                message="Referenced resource does not exist",
                details={"constraint": "foreign_key_constraint"},
            )
        else:
            db_error = DatabaseError(
                message="Database constraint violation",
                details={"constraint": "integrity_constraint"},
            )

        response, status_code = create_error_response(
            db_error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(error: SQLAlchemyError):
        """Handle general SQLAlchemy errors."""
        request_id = getattr(request, "id", None)

        logger.error(f"Database error: {str(error)}", extra={"request_id": request_id})

        db_error = DatabaseError(
            message="Database operation failed",
            details={"error_type": type(error).__name__},
        )

        response, status_code = create_error_response(
            db_error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle HTTP exceptions."""
        request_id = getattr(request, "id", None)

        logger.warning(
            f"HTTP error {error.code}: {error.description}",
            extra={"request_id": request_id, "status_code": error.code},
        )

        response, status_code = create_error_response(
            error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors."""
        request_id = getattr(request, "id", None)

        not_found_error = NotFoundError(
            resource="Endpoint",
            details={"path": request.path, "method": request.method},
        )

        response, status_code = create_error_response(
            not_found_error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle method not allowed errors."""
        request_id = getattr(request, "id", None)

        method_error = TradeSenseException(
            message=f"Method {request.method} not allowed for this endpoint",
            code="METHOD_NOT_ALLOWED",
            status_code=405,
            details={"method": request.method, "path": request.path},
        )

        response, status_code = create_error_response(
            method_error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception):
        """Handle any unhandled exceptions."""
        request_id = getattr(request, "id", None)

        logger.critical(
            f"Unhandled exception: {str(error)}",
            extra={
                "request_id": request_id,
                "error_type": type(error).__name__,
                "traceback": traceback.format_exc(),
            },
        )

        response, status_code = create_error_response(
            error, request_id=request_id, include_traceback=app.debug
        )

        return jsonify(response), status_code

    @app.before_request
    def add_request_id():
        """Add unique request ID for tracking."""
        import uuid

        request.id = str(uuid.uuid4())

    @app.after_request
    def log_request(response):
        """Log request details."""
        request_id = getattr(request, "id", None)

        logger.info(
            f"{request.method} {request.path} - {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "ip_address": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
            },
        )

        # Add request ID to response headers
        if request_id:
            response.headers["X-Request-ID"] = request_id

        return response
