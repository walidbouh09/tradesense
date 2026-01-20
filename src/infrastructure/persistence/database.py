"""Database configuration and session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ...domains.trading.infrastructure.models import Base


class DatabaseManager:
    """Database manager for async SQLAlchemy operations."""
    
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(
            database_url,
            poolclass=NullPool,  # Use NullPool for async
            echo=False,  # Set to True for SQL logging in development
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self) -> None:
        """Drop all database tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        """Close database engine."""
        await self._engine.dispose()