"""Database session management with lifecycle control and context tracking."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .connection import DatabaseConnectionManager
from ..common.context import ExecutionContext
from ..common.exceptions import DatabaseSessionError

logger = structlog.get_logger()


class DatabaseSessionManager:
    """Manages database sessions with proper lifecycle and context tracking."""
    
    def __init__(self, connection_manager: DatabaseConnectionManager):
        self.connection_manager = connection_manager
        self.session_factory: Optional[async_sessionmaker] = None
        
    async def initialize(self) -> None:
        """Initialize session factory."""
        if not self.connection_manager.engine:
            raise DatabaseSessionError("Connection manager not initialized")
        
        self.session_factory = async_sessionmaker(
            bind=self.connection_manager.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Keep objects accessible after commit
            autoflush=True,  # Auto-flush before queries
            autocommit=False,  # Explicit transaction control
        )
        
        logger.info("Database session factory initialized")
    
    @asynccontextmanager
    async def get_session(
        self, 
        execution_context: Optional[ExecutionContext] = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup and context tracking."""
        if not self.session_factory:
            raise DatabaseSessionError("Session factory not initialized")
        
        session_id = None
        if execution_context:
            session_id = execution_context.correlation_id
        
        logger.debug("Creating database session", session_id=session_id)
        
        async with self.session_factory() as session:
            try:
                # Set session context for audit trail
                if execution_context:
                    await self._set_session_context(session, execution_context)
                
                yield session
                
                logger.debug("Database session completed successfully", session_id=session_id)
                
            except Exception as e:
                logger.error(
                    "Database session error, rolling back",
                    session_id=session_id,
                    error=str(e),
                )
                await session.rollback()
                raise DatabaseSessionError(f"Database session failed: {e}") from e
            
            finally:
                await session.close()
                logger.debug("Database session closed", session_id=session_id)
    
    async def _set_session_context(
        self, 
        session: AsyncSession, 
        execution_context: ExecutionContext
    ) -> None:
        """Set session-level context variables for audit and tracking."""
        try:
            # Set application context in database session
            context_vars = {
                'application.correlation_id': execution_context.correlation_id,
                'application.user_id': str(execution_context.user_id) if execution_context.user_id else None,
                'application.session_id': execution_context.session_id,
                'application.timestamp': execution_context.timestamp.isoformat(),
            }
            
            # Set context variables (PostgreSQL specific)
            for key, value in context_vars.items():
                if value is not None:
                    await session.execute(
                        f"SELECT set_config('{key}', '{value}', false)"
                    )
            
        except Exception as e:
            logger.warning(
                "Failed to set session context variables",
                error=str(e),
                correlation_id=execution_context.correlation_id,
            )
            # Don't fail the session creation for context setting errors


class TransactionManager:
    """Manages database transactions with audit context and rollback safety."""
    
    def __init__(self, session_manager: DatabaseSessionManager):
        self.session_manager = session_manager
    
    @asynccontextmanager
    async def transaction(
        self,
        execution_context: Optional[ExecutionContext] = None,
        isolation_level: Optional[str] = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Execute operations within a database transaction."""
        async with self.session_manager.get_session(execution_context) as session:
            transaction = await session.begin()
            
            try:
                # Set isolation level if specified
                if isolation_level:
                    await session.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
                
                logger.debug(
                    "Transaction started",
                    correlation_id=execution_context.correlation_id if execution_context else None,
                    isolation_level=isolation_level,
                )
                
                yield session
                
                await transaction.commit()
                
                logger.debug(
                    "Transaction committed",
                    correlation_id=execution_context.correlation_id if execution_context else None,
                )
                
            except Exception as e:
                logger.error(
                    "Transaction failed, rolling back",
                    correlation_id=execution_context.correlation_id if execution_context else None,
                    error=str(e),
                )
                await transaction.rollback()
                raise
    
    @asynccontextmanager
    async def read_only_transaction(
        self,
        execution_context: Optional[ExecutionContext] = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Execute read-only operations within a transaction."""
        async with self.transaction(
            execution_context=execution_context,
            isolation_level="READ COMMITTED",
        ) as session:
            # Set transaction as read-only
            await session.execute("SET TRANSACTION READ ONLY")
            yield session
    
    async def execute_with_retry(
        self,
        operation,
        execution_context: Optional[ExecutionContext] = None,
        max_retries: int = 3,
        isolation_level: Optional[str] = None,
    ):
        """Execute operation with automatic retry on transient failures."""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                async with self.transaction(execution_context, isolation_level) as session:
                    return await operation(session)
                    
            except Exception as e:
                last_exception = e
                
                # Check if error is retryable (connection issues, deadlocks, etc.)
                if self._is_retryable_error(e) and attempt < max_retries:
                    logger.warning(
                        "Retryable database error, attempting retry",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                        correlation_id=execution_context.correlation_id if execution_context else None,
                    )
                    
                    # Exponential backoff
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                # Non-retryable error or max retries exceeded
                logger.error(
                    "Database operation failed after retries",
                    attempts=attempt + 1,
                    error=str(e),
                    correlation_id=execution_context.correlation_id if execution_context else None,
                )
                raise
        
        # This should never be reached, but just in case
        raise last_exception
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if database error is retryable."""
        error_str = str(error).lower()
        
        # Common retryable error patterns
        retryable_patterns = [
            "connection",
            "timeout",
            "deadlock",
            "serialization failure",
            "could not serialize access",
            "connection reset",
            "connection refused",
        ]
        
        return any(pattern in error_str for pattern in retryable_patterns)