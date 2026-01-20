"""
TradeSense Pro - Database Configuration

Async PostgreSQL database configuration with:
- SQLAlchemy async engine
- Connection pooling
- Health checks
- Migration support
- Session management
"""

import logging
from typing import AsyncGenerator, Optional

import structlog
from app.core.config import get_settings
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

# Configure logger
logger = structlog.get_logger(__name__)

# Get settings
settings = get_settings()

# SQLAlchemy async engine
engine: Optional[create_async_engine] = None
async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


class Base(DeclarativeBase):
    """
    Base class for all database models.

    Includes common fields and methods for all models.
    """

    # Naming convention for constraints
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


async def init_db() -> None:
    """
    Initialize database connection and create tables.

    This function should be called at application startup.
    """
    global engine, async_session_maker

    try:
        # Create async engine with connection pooling
        engine = create_async_engine(
            str(settings.DATABASE_URL),
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
            pool_size=10,  # Connection pool size
            max_overflow=20,  # Maximum overflow connections
            pool_timeout=30,  # Timeout for getting connection from pool
        )

        # Create session maker
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )

        # Test database connection
        await test_connection()

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_db() -> None:
    """
    Close database connection.

    This function should be called at application shutdown.
    """
    global engine

    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def test_connection() -> bool:
    """
    Test database connection health.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
            return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session.

    This is a dependency that can be used with FastAPI's Depends().

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_session)):
            return await db.execute(select(User))
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class DatabaseHealthCheck:
    """
    Database health check utilities.
    """

    @staticmethod
    async def check_connection() -> dict:
        """
        Comprehensive database health check.

        Returns:
            dict: Health check results
        """
        health_status = {
            "database": "unhealthy",
            "connection": False,
            "pool_size": 0,
            "pool_checked_in": 0,
            "pool_checked_out": 0,
            "details": {},
        }

        try:
            if engine is None:
                health_status["details"]["error"] = "Database engine not initialized"
                return health_status

            # Check basic connection
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
                health_status["connection"] = True

            # Check connection pool status
            pool = engine.pool
            health_status["pool_size"] = pool.size()
            health_status["pool_checked_in"] = pool.checkedin()
            health_status["pool_checked_out"] = pool.checkedout()

            # Check if we can perform basic operations
            async with get_session() as session:
                # Test a simple query with timestamp
                result = await session.execute(text("SELECT NOW() as current_time"))
                row = result.fetchone()
                health_status["details"]["server_time"] = str(row.current_time)

            health_status["database"] = "healthy"

        except Exception as e:
            health_status["details"]["error"] = str(e)
            logger.error("Database health check failed", error=str(e))

        return health_status


class DatabaseTransaction:
    """
    Context manager for database transactions.

    Example:
        async with DatabaseTransaction() as session:
            user = User(email="test@example.com")
            session.add(user)
            # Transaction is automatically committed
    """

    def __init__(self):
        self.session: Optional[AsyncSession] = None

    async def __aenter__(self) -> AsyncSession:
        if async_session_maker is None:
            raise RuntimeError("Database not initialized")

        self.session = async_session_maker()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                await self.session.rollback()
                logger.warning(
                    "Transaction rolled back due to exception",
                    exc_type=exc_type.__name__ if exc_type else None,
                    exc_val=str(exc_val) if exc_val else None,
                )
            else:
                await self.session.commit()

            await self.session.close()


async def create_tables() -> None:
    """
    Create all database tables.

    This should only be used for initial setup or testing.
    In production, use Alembic migrations.
    """
    if engine is None:
        raise RuntimeError("Database engine not initialized")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created")


async def drop_tables() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data!
    Should only be used in testing.
    """
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("Cannot drop tables in production environment")

    if engine is None:
        raise RuntimeError("Database engine not initialized")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.warning("Database tables dropped")


# Utility functions for common database operations
async def execute_raw_sql(query: str, parameters: dict = None) -> any:
    """
    Execute raw SQL query.

    Args:
        query: SQL query string
        parameters: Query parameters

    Returns:
        Query result
    """
    async with get_session() as session:
        if parameters:
            result = await session.execute(text(query), parameters)
        else:
            result = await session.execute(text(query))

        return result


async def get_database_version() -> str:
    """
    Get PostgreSQL version.

    Returns:
        str: Database version
    """
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            return version
    except Exception as e:
        logger.error("Failed to get database version", error=str(e))
        return "unknown"


# Export commonly used items
__all__ = [
    "Base",
    "init_db",
    "close_db",
    "get_session",
    "test_connection",
    "DatabaseHealthCheck",
    "DatabaseTransaction",
    "create_tables",
    "drop_tables",
    "execute_raw_sql",
    "get_database_version",
]
