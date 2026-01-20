"""TradeSense AI FastAPI application."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
import structlog
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .domains.trading.api.routers import router as trading_router
from .domains.payments.api.routers import router as payment_router
from .domains.trading.application.handlers import (
    CancelOrderHandler,
    GetActiveOrdersHandler,
    GetOrderHandler,
    GetPositionHandler,
    GetUserOrdersHandler,
    PlaceOrderHandler,
)
from .domains.trading.domain.services import OrderValidationService, PositionCalculator
from .domains.trading.infrastructure.repositories import SqlAlchemyOrderRepository
from .infrastructure.messaging.redis_event_bus import RedisEventBus
from .infrastructure.persistence.database import DatabaseManager
from .workers.audit_writer.worker import AuditWriterWorker
from .workers.payment_processor.worker import PaymentProcessorWorker

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
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global instances
db_manager: DatabaseManager = None
redis_client: redis.Redis = None
event_bus: RedisEventBus = None
audit_worker: AuditWriterWorker = None
payment_worker: PaymentProcessorWorker = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global db_manager, redis_client, event_bus, audit_worker, payment_worker

    logger.info("Starting TradeSense AI application")

    # Initialize database
    db_manager = DatabaseManager("postgresql+asyncpg://user:password@localhost/tradesense")
    await db_manager.create_tables()

    # Initialize Redis
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=False)

    # Initialize event bus
    event_bus = RedisEventBus(redis_client)

    # Initialize and start audit worker
    audit_worker = AuditWriterWorker(redis_client)
    audit_task = asyncio.create_task(audit_worker.start())

    # Initialize and start payment worker
    # Note: In production, these configs should come from environment variables
    stripe_config = {
        "api_key": "sk_test_placeholder",  # Should come from env
        "webhook_secret": "whsec_placeholder",  # Should come from env
    }
    paypal_config = {
        "api_key": "paypal_placeholder",  # Should come from env
        "webhook_secret": "paypal_whsec_placeholder",  # Should come from env
    }

    payment_worker = PaymentProcessorWorker(
        redis_client=redis_client,
        database_url="postgresql+asyncpg://user:password@localhost/tradesense",
        stripe_config=stripe_config,
        paypal_config=paypal_config,
    )
    payment_task = asyncio.create_task(payment_worker.start())

    logger.info("Application startup complete")

    yield

    # Cleanup
    logger.info("Shutting down TradeSense AI application")

    if payment_worker:
        await payment_worker.stop()
        payment_task.cancel()
        try:
            await payment_task
        except asyncio.CancelledError:
            pass

    if audit_worker:
        await audit_worker.stop()
        audit_task.cancel()
        try:
            await audit_task
        except asyncio.CancelledError:
            pass

    if redis_client:
        await redis_client.close()

    if db_manager:
        await db_manager.close()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="TradeSense AI",
    description="FinTech Prop Trading SaaS Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency providers
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async for session in db_manager.get_session():
        yield session


async def get_event_bus() -> RedisEventBus:
    """Get event bus dependency."""
    return event_bus


async def get_order_repository(session: AsyncSession = Depends(get_db_session)) -> SqlAlchemyOrderRepository:
    """Get order repository dependency."""
    return SqlAlchemyOrderRepository(session)


async def get_validation_service() -> OrderValidationService:
    """Get validation service dependency."""
    return OrderValidationService()


async def get_position_calculator() -> PositionCalculator:
    """Get position calculator dependency."""
    return PositionCalculator()


# Handler dependencies
async def get_place_order_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
    event_bus: RedisEventBus = Depends(get_event_bus),
    validation_service: OrderValidationService = Depends(get_validation_service),
) -> PlaceOrderHandler:
    """Get place order handler dependency."""
    return PlaceOrderHandler(repository, event_bus, validation_service)


async def get_cancel_order_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
    event_bus: RedisEventBus = Depends(get_event_bus),
) -> CancelOrderHandler:
    """Get cancel order handler dependency."""
    return CancelOrderHandler(repository, event_bus)


async def get_get_order_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
) -> GetOrderHandler:
    """Get order handler dependency."""
    return GetOrderHandler(repository)


async def get_get_user_orders_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
) -> GetUserOrdersHandler:
    """Get user orders handler dependency."""
    return GetUserOrdersHandler(repository)


async def get_get_active_orders_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
) -> GetActiveOrdersHandler:
    """Get active orders handler dependency."""
    return GetActiveOrdersHandler(repository)


async def get_get_position_handler(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository),
    calculator: PositionCalculator = Depends(get_position_calculator),
) -> GetPositionHandler:
    """Get position handler dependency."""
    return GetPositionHandler(repository, calculator)


# Override dependencies in router
trading_router.dependency_overrides.update({
    PlaceOrderHandler: get_place_order_handler,
    CancelOrderHandler: get_cancel_order_handler,
    GetOrderHandler: get_get_order_handler,
    GetUserOrdersHandler: get_get_user_orders_handler,
    GetActiveOrdersHandler: get_get_active_orders_handler,
    GetPositionHandler: get_get_position_handler,
})

# Include routers
app.include_router(trading_router)
app.include_router(payment_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "tradesense-ai"}


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Welcome to TradeSense AI",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Use structlog instead
    )