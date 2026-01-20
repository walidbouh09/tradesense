"""
TradeSense Pro - Main FastAPI Application

Production-ready FastAPI application with:
- Async database connections
- JWT authentication
- CORS configuration
- Error handling middleware
- Health checks
- API versioning
- WebSocket support
- Request/response logging
"""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BusinessLogicException,
    ValidationException,
)
from app.utils.security import verify_jwt_token
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Configure structured logging
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
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting TradeSense Pro API")

    # Initialize database connection
    await init_db()
    logger.info("Database connection initialized")

    # Add any other startup tasks here
    # - Redis connection
    # - External API health checks
    # - Cache warming

    yield

    # Shutdown
    logger.info("Shutting down TradeSense Pro API")

    # Close database connections
    await close_db()
    logger.info("Database connections closed")


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title="TradeSense Pro API",
        description="Professional Proprietary Trading Platform API",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
        # Custom OpenAPI schema
        openapi_tags=[
            {
                "name": "authentication",
                "description": "User authentication and authorization",
            },
            {
                "name": "challenges",
                "description": "Trading challenge lifecycle management",
            },
            {"name": "trades", "description": "Trade execution and management"},
            {"name": "payments", "description": "Payment processing and billing"},
            {"name": "analytics", "description": "Performance analytics and reporting"},
            {"name": "admin", "description": "Administrative functions"},
            {"name": "health", "description": "System health and monitoring"},
        ],
    )

    # Add middleware
    setup_middleware(app)

    # Add exception handlers
    setup_exception_handlers(app)

    # Include routers
    app.include_router(api_router, prefix="/api")

    return app


def setup_middleware(app: FastAPI) -> None:
    """
    Configure application middleware.

    Args:
        app: FastAPI application instance
    """

    # Trusted hosts (security)
    if settings.TRUSTED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

    # CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )

    # Request ID and logging middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """
        Add unique request ID to each request for tracing.
        """
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Add request ID to logs
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            start_time = time.time()

            # Log incoming request
            logger.info(
                "request_started",
                method=request.method,
                url=str(request.url),
                user_agent=request.headers.get("user-agent"),
                client_ip=request.client.host if request.client else None,
            )

            response = await call_next(request)

            # Calculate request duration
            process_time = time.time() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            # Log completed request
            logger.info(
                "request_completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=process_time,
            )

            return response

    # Authentication middleware for protected routes
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """
        Authentication middleware for protected routes.
        """
        # Skip auth for public routes
        public_routes = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/health",
            "/api/v1/payments/webhook",
        ]

        if any(request.url.path.startswith(route) for route in public_routes):
            return await call_next(request)

        # Extract and verify JWT token
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            try:
                payload = verify_jwt_token(token)
                request.state.user_id = payload.get("user_id")
                request.state.user_email = payload.get("email")
            except Exception as e:
                logger.warning("Invalid JWT token", error=str(e))
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication token"},
                )
        else:
            # Allow unauthenticated requests to proceed
            # Individual endpoints will handle auth requirements
            pass

        return await call_next(request)


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configure custom exception handlers.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(request: Request, exc: ValidationException):
        """Handle custom validation exceptions."""
        logger.warning(
            "validation_error",
            error=exc.message,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request: Request, exc: AuthenticationException):
        """Handle authentication exceptions."""
        logger.warning(
            "authentication_error",
            error=exc.message,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "authentication_error", "message": exc.message},
        )

    @app.exception_handler(AuthorizationException)
    async def authorization_exception_handler(
        request: Request, exc: AuthorizationException
    ):
        """Handle authorization exceptions."""
        logger.warning(
            "authorization_error",
            error=exc.message,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "authorization_error", "message": exc.message},
        )

    @app.exception_handler(BusinessLogicException)
    async def business_logic_exception_handler(
        request: Request, exc: BusinessLogicException
    ):
        """Handle business logic exceptions."""
        logger.error(
            "business_logic_error",
            error=exc.message,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "business_logic_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Handle Pydantic validation errors."""
        logger.warning(
            "request_validation_error",
            errors=exc.errors(),
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(
            "unexpected_error",
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=getattr(request.state, "request_id", None),
            exc_info=True,
        )

        # Don't expose internal errors in production
        if settings.DEBUG:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_server_error",
                    "message": str(exc),
                    "type": type(exc).__name__,
                },
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred",
                },
            )


# Create application instance
app = create_application()


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information."""
    return {
        "message": "TradeSense Pro API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs" if settings.DEBUG else "Contact support for API documentation",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        dict: Health status and system information
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": "connected",  # TODO: Add actual health checks
            "redis": "connected",
            "celery": "running",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
