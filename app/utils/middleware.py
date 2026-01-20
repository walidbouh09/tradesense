"""
TradeSense AI - Middleware Utilities

Professional middleware components for Flask application including
request tracking, security headers, performance monitoring, and more.
"""

import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from flask import Flask, Response, g, request
from werkzeug.local import LocalProxy

from app.utils.logger import get_logger, log_performance_metric, log_security_event


class RequestTrackingMiddleware:
    """Middleware to track requests with unique IDs and timing."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.tracking")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self) -> None:
        """Process request before handling."""
        # Generate unique request ID
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        g.start_datetime = datetime.utcnow()

        # Log request start
        self.logger.info(
            f"Request started: {request.method} {request.path}",
            extra={
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
                "content_type": request.content_type,
                "content_length": request.content_length,
            },
        )

    def after_request(self, response: Response) -> Response:
        """Process response after handling."""
        if hasattr(g, "start_time"):
            duration = (time.time() - g.start_time) * 1000  # Convert to milliseconds

            # Log request completion
            self.logger.info(
                f"Request completed: {request.method} {request.path} - {response.status_code}",
                extra={
                    "request_id": getattr(g, "request_id", None),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": duration,
                    "content_length": response.content_length,
                },
            )

            # Log performance metric
            log_performance_metric(
                metric_name="request_duration",
                metric_value=duration,
                metric_unit="ms",
                method=request.method,
                path=request.path,
                status_code=response.status_code,
            )

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration:.2f}ms"

        # Add request ID to response headers
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id

        return response


class SecurityHeadersMiddleware:
    """Middleware to add security headers to responses."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.security")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.after_request(self.add_security_headers)

    def add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        # Content Security Policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS (only in production with HTTPS)
        if self.app.config.get("ENV") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Remove server information
        response.headers.pop("Server", None)

        return response


class CORSMiddleware:
    """Custom CORS middleware with enhanced configuration."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.cors")
        self.allowed_origins = app.config.get("CORS_ORIGINS", "").split(",")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.after_request(self.handle_cors)

    def handle_cors(self, response: Response) -> Response:
        """Handle CORS headers."""
        origin = request.headers.get("Origin")

        if origin and (origin in self.allowed_origins or "*" in self.allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, X-Requested-With, X-Request-ID"
            )
            response.headers["Access-Control-Expose-Headers"] = (
                "X-Request-ID, X-Response-Time, X-RateLimit-Remaining"
            )
            response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours

        return response


class CompressionMiddleware:
    """Middleware for response compression."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.compression")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.after_request(self.compress_response)

    def compress_response(self, response: Response) -> Response:
        """Add compression headers if appropriate."""
        # Only compress for certain content types and sizes
        content_type = response.headers.get("Content-Type", "")
        content_length = response.content_length or 0

        compressible_types = [
            "application/json",
            "text/html",
            "text/css",
            "text/javascript",
            "application/javascript",
        ]

        if (
            any(ct in content_type for ct in compressible_types)
            and content_length > 1024
        ):  # Only compress if > 1KB
            response.headers["Vary"] = "Accept-Encoding"

        return response


class RateLimitLoggingMiddleware:
    """Middleware to log rate limit events."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.ratelimit")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.after_request(self.log_rate_limit)

    def log_rate_limit(self, response: Response) -> Response:
        """Log rate limit information."""
        if response.status_code == 429:
            # Rate limit exceeded
            log_security_event(
                event_type="rate_limit_exceeded",
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                endpoint=request.endpoint,
                method=request.method,
                path=request.path,
            )

        # Add rate limit headers if present
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        if rate_limit_remaining:
            response.headers["X-RateLimit-Remaining"] = rate_limit_remaining

        return response


class APIVersionMiddleware:
    """Middleware to handle API versioning."""

    def __init__(self, app: Flask, default_version: str = "v1"):
        self.app = app
        self.default_version = default_version
        self.logger = get_logger("tradesense.middleware.versioning")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.before_request(self.handle_api_version)
        app.after_request(self.add_version_headers)

    def handle_api_version(self) -> None:
        """Handle API version from headers or URL."""
        # Check for version in Accept header
        accept_header = request.headers.get("Accept", "")
        if "application/vnd.tradesense" in accept_header:
            # Extract version from header like: application/vnd.tradesense.v1+json
            version = self.extract_version_from_header(accept_header)
            g.api_version = version or self.default_version
        else:
            # Check URL path for version
            if request.path.startswith("/api/"):
                path_parts = request.path.split("/")
                if len(path_parts) >= 3 and path_parts[2].startswith("v"):
                    g.api_version = path_parts[2]
                else:
                    g.api_version = self.default_version
            else:
                g.api_version = self.default_version

    def add_version_headers(self, response: Response) -> Response:
        """Add version information to response headers."""
        if hasattr(g, "api_version"):
            response.headers["X-API-Version"] = g.api_version
            response.headers["X-API-Supported-Versions"] = "v1"

        return response

    def extract_version_from_header(self, accept_header: str) -> Optional[str]:
        """Extract version from Accept header."""
        import re

        match = re.search(r"application/vnd\.tradesense\.(.+?)\+json", accept_header)
        return match.group(1) if match else None


class HealthCheckMiddleware:
    """Middleware for health check endpoints."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.health")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.before_request(self.handle_health_check)

    def handle_health_check(self) -> Optional[Response]:
        """Handle health check requests."""
        if request.path in ["/health", "/healthz", "/ping"]:
            # Skip authentication and other middleware for health checks
            g.skip_auth = True

            # Return simple health response
            from flask import jsonify

            return jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": self.app.config.get("VERSION", "1.0.0"),
                }
            )

        return None


class MaintenanceModeMiddleware:
    """Middleware to handle maintenance mode."""

    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger("tradesense.middleware.maintenance")

    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.before_request(self.check_maintenance_mode)

    def check_maintenance_mode(self) -> Optional[Response]:
        """Check if application is in maintenance mode."""
        if self.app.config.get("MAINTENANCE_MODE", False):
            # Allow health checks during maintenance
            if request.path in ["/health", "/healthz", "/ping"]:
                return None

            # Allow admin access during maintenance
            admin_token = request.headers.get("X-Admin-Token")
            if admin_token == self.app.config.get("ADMIN_MAINTENANCE_TOKEN"):
                return None

            # Return maintenance response
            from flask import jsonify

            return jsonify(
                {
                    "error": {
                        "code": "MAINTENANCE_MODE",
                        "message": "Service is currently under maintenance. Please try again later.",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                }
            ), 503

        return None


def setup_middleware(app: Flask) -> None:
    """Setup all middleware for the application."""

    # Initialize middleware components
    RequestTrackingMiddleware(app).init_app(app)
    SecurityHeadersMiddleware(app).init_app(app)
    CORSMiddleware(app).init_app(app)
    CompressionMiddleware(app).init_app(app)
    RateLimitLoggingMiddleware(app).init_app(app)
    APIVersionMiddleware(app).init_app(app)
    HealthCheckMiddleware(app).init_app(app)
    MaintenanceModeMiddleware(app).init_app(app)

    logger = get_logger("tradesense.middleware")
    logger.info("All middleware components initialized successfully")


# Utility functions for middleware
def get_client_ip() -> str:
    """Get client IP address considering proxy headers."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    else:
        return request.remote_addr or "unknown"


def get_user_agent() -> str:
    """Get user agent string."""
    return request.headers.get("User-Agent", "unknown")


def is_api_request() -> bool:
    """Check if current request is an API request."""
    return request.path.startswith("/api/")


def is_websocket_request() -> bool:
    """Check if current request is a WebSocket request."""
    return request.headers.get("Upgrade", "").lower() == "websocket"


# Context processors for templates
def inject_request_context():
    """Inject request context into templates."""
    return {
        "request_id": getattr(g, "request_id", None),
        "api_version": getattr(g, "api_version", "v1"),
        "client_ip": get_client_ip(),
    }
