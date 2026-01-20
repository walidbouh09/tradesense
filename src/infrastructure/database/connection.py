"""Database connection management with pooling, health monitoring, and failover."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from ..config.settings import DatabaseConfig
from ..common.exceptions import DatabaseConnectionError, DatabaseHealthCheckError

logger = structlog.get_logger()


class ConnectionHealth:
    """Database connection health status."""
    
    def __init__(self):
        self.is_healthy: bool = True
        self.last_check: datetime = datetime.utcnow()
        self.response_time_ms: Optional[float] = None
        self.error_message: Optional[str] = None
        self.consecutive_failures: int = 0
        
    def mark_healthy(self, response_time_ms: float) -> None:
        """Mark connection as healthy."""
        self.is_healthy = True
        self.last_check = datetime.utcnow()
        self.response_time_ms = response_time_ms
        self.error_message = None
        self.consecutive_failures = 0
        
    def mark_unhealthy(self, error_message: str) -> None:
        """Mark connection as unhealthy."""
        self.is_healthy = False
        self.last_check = datetime.utcnow()
        self.error_message = error_message
        self.consecutive_failures += 1
        
    @property
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker should be open."""
        return self.consecutive_failures >= 3
        
    @property
    def should_retry(self) -> bool:
        """Check if connection should be retried."""
        if not self.is_circuit_open:
            return True
        
        # Exponential backoff: wait longer after more failures
        backoff_seconds = min(300, 2 ** (self.consecutive_failures - 3))  # Max 5 minutes
        return datetime.utcnow() - self.last_check > timedelta(seconds=backoff_seconds)


class DatabaseConnectionManager:
    """Manages database connections with pooling, health monitoring, and circuit breaker."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.health: ConnectionHealth = ConnectionHealth()
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize database connection pool with health monitoring."""
        try:
            logger.info("Initializing database connection pool")
            
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                self.config.connection_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True,  # Validate connections before use
                echo=False,  # Set to True for SQL debugging
                future=True,
            )
            
            # Perform initial health check
            await self._perform_health_check()
            
            if not self.health.is_healthy:
                raise DatabaseConnectionError("Initial database health check failed")
            
            # Start background health monitoring
            self._health_check_task = asyncio.create_task(self._health_monitor_loop())
            
            logger.info(
                "Database connection pool initialized",
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                response_time_ms=self.health.response_time_ms,
            )
            
        except Exception as e:
            logger.error("Failed to initialize database connection", error=str(e))
            raise DatabaseConnectionError(f"Database initialization failed: {e}") from e
    
    async def _health_monitor_loop(self) -> None:
        """Background task for continuous health monitoring."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self.health.should_retry:
                    await self._perform_health_check()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in database health monitor", error=str(e))
    
    async def _perform_health_check(self) -> None:
        """Perform database health check."""
        if not self.engine:
            self.health.mark_unhealthy("Database engine not initialized")
            return
        
        start_time = datetime.utcnow()
        
        try:
            async with self.engine.begin() as conn:
                # Simple query to test connectivity and performance
                result = await conn.execute(text("SELECT 1 as health_check"))
                row = result.fetchone()
                
                if row and row[0] == 1:
                    response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    self.health.mark_healthy(response_time)
                    
                    logger.debug(
                        "Database health check passed",
                        response_time_ms=response_time,
                    )
                else:
                    self.health.mark_unhealthy("Health check query returned unexpected result")
                    
        except Exception as e:
            error_msg = f"Database health check failed: {e}"
            self.health.mark_unhealthy(error_msg)
            
            logger.warning(
                "Database health check failed",
                error=str(e),
                consecutive_failures=self.health.consecutive_failures,
                circuit_open=self.health.is_circuit_open,
            )
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator:
        """Get database connection with circuit breaker protection."""
        if not self.engine:
            raise DatabaseConnectionError("Database engine not initialized")
        
        if self.health.is_circuit_open and not self.health.should_retry:
            raise DatabaseConnectionError(
                f"Database circuit breaker is open. Last error: {self.health.error_message}"
            )
        
        try:
            async with self.engine.begin() as conn:
                yield conn
                
        except Exception as e:
            # Update health status on connection failure
            self.health.mark_unhealthy(f"Connection error: {e}")
            logger.error(
                "Database connection error",
                error=str(e),
                consecutive_failures=self.health.consecutive_failures,
            )
            raise DatabaseConnectionError(f"Database connection failed: {e}") from e
    
    async def get_health_status(self) -> Dict[str, any]:
        """Get detailed health status for monitoring."""
        # Perform fresh health check if needed
        if datetime.utcnow() - self.health.last_check > timedelta(minutes=1):
            await self._perform_health_check()
        
        pool_status = {}
        if self.engine and hasattr(self.engine.pool, 'size'):
            pool_status = {
                "pool_size": self.engine.pool.size(),
                "checked_in": self.engine.pool.checkedin(),
                "checked_out": self.engine.pool.checkedout(),
                "overflow": self.engine.pool.overflow(),
            }
        
        return {
            "healthy": self.health.is_healthy,
            "last_check": self.health.last_check.isoformat(),
            "response_time_ms": self.health.response_time_ms,
            "consecutive_failures": self.health.consecutive_failures,
            "circuit_open": self.health.is_circuit_open,
            "error_message": self.health.error_message,
            "pool_status": pool_status,
        }
    
    async def execute_health_check(self) -> None:
        """Execute immediate health check (for external monitoring)."""
        await self._perform_health_check()
        
        if not self.health.is_healthy:
            raise DatabaseHealthCheckError(
                f"Database health check failed: {self.health.error_message}"
            )
    
    async def close(self) -> None:
        """Gracefully close database connections."""
        logger.info("Closing database connections")
        
        # Signal health monitor to stop
        self._shutdown_event.set()
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close engine and all connections
        if self.engine:
            await self.engine.dispose()
            self.engine = None
        
        logger.info("Database connections closed")
    
    def __repr__(self) -> str:
        return f"DatabaseConnectionManager(healthy={self.health.is_healthy}, pool_size={self.config.pool_size})"