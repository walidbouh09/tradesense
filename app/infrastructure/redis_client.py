"""
Redis Client - Shared Infrastructure Component

Provides Redis connectivity for caching, message passing, and future scaling.
Redis is infrastructure - failures must not break core business logic.

Use Cases:
- Message broker for async workers
- Cache for frequently accessed data
- Future WebSocket scaling (Redis adapter)
- Rate limiting and session storage

Design Principles:
- Graceful degradation on Redis failure
- No business logic in Redis operations
- Connection pooling for performance
- Environment-driven configuration
"""

import os
import json
import logging
from typing import Any, Optional, Dict, List
from contextlib import contextmanager

try:
    import redis
    from redis import Redis, ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    Redis = None
    ConnectionPool = None

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client with graceful degradation.

    Provides caching and message passing capabilities.
    All operations are best-effort - failures don't break business logic.
    """

    def __init__(self):
        """Initialize Redis client with environment configuration."""
        self.enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'
        self.host = os.getenv('REDIS_HOST', 'redis')
        self.port = int(os.getenv('REDIS_PORT', '6379'))
        self.db = int(os.getenv('REDIS_DB', '0'))
        self.password = os.getenv('REDIS_PASSWORD', None)
        self.socket_timeout = float(os.getenv('REDIS_SOCKET_TIMEOUT', '5.0'))
        self.socket_connect_timeout = float(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5.0'))

        self._pool = None
        self._client = None

        if self.enabled and REDIS_AVAILABLE:
            try:
                self._pool = ConnectionPool(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    decode_responses=True,  # Return strings, not bytes
                    max_connections=20,      # Connection pooling
                    retry_on_timeout=True,
                )
                self._client = Redis(connection_pool=self._pool)
                logger.info("Redis client initialized", extra={
                    'host': self.host,
                    'port': self.port,
                    'db': self.db,
                })
            except Exception as e:
                logger.warning("Redis initialization failed", extra={
                    'error': str(e),
                    'host': self.host,
                    'port': self.port,
                })
                self.enabled = False
        else:
            logger.info("Redis disabled or unavailable")
            self.enabled = False

    @contextmanager
    def connection(self):
        """
        Context manager for Redis connections.

        Ensures proper connection handling and error recovery.
        """
        if not self.enabled:
            # Return a mock connection that does nothing
            yield MockRedisConnection()
            return

        client = None
        try:
            client = Redis(connection_pool=self._pool)
            yield client
        except Exception as e:
            logger.error("Redis connection error", exc_info=True)
            # Return mock to prevent failures
            yield MockRedisConnection()
        finally:
            # Connection pooling handles cleanup
            pass

    def is_available(self) -> bool:
        """Check if Redis is available and responding."""
        if not self.enabled:
            return False

        try:
            with self.connection() as conn:
                return conn.ping()
        except Exception:
            return False

    # Cache Operations
    def get_cache(self, key: str) -> Optional[str]:
        """
        Get value from cache.

        Returns None if Redis unavailable or key not found.
        """
        try:
            with self.connection() as conn:
                return conn.get(key)
        except Exception as e:
            logger.debug("Cache get failed", extra={'key': key, 'error': str(e)})
            return None

    def set_cache(self, key: str, value: str, ttl_seconds: int = 300) -> bool:
        """
        Set cache value with TTL.

        Returns True if successful, False otherwise.
        """
        try:
            with self.connection() as conn:
                return conn.setex(key, ttl_seconds, value)
        except Exception as e:
            logger.debug("Cache set failed", extra={'key': key, 'error': str(e)})
            return False

    def delete_cache(self, key: str) -> bool:
        """
        Delete cache key.

        Returns True if successful, False otherwise.
        """
        try:
            with self.connection() as conn:
                return conn.delete(key) > 0
        except Exception as e:
            logger.debug("Cache delete failed", extra={'key': key, 'error': str(e)})
            return False

    # Message Queue Operations
    def publish_message(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish message to channel.

        Used for inter-service communication and worker coordination.
        """
        try:
            with self.connection() as conn:
                return conn.publish(channel, json.dumps(message)) > 0
        except Exception as e:
            logger.debug("Message publish failed", extra={
                'channel': channel,
                'error': str(e)
            })
            return False

    def subscribe_to_channel(self, channel: str, callback):
        """
        Subscribe to channel with callback.

        Used by workers to listen for tasks or events.
        Note: This is blocking - use in dedicated threads.
        """
        if not self.enabled:
            logger.warning("Cannot subscribe - Redis disabled")
            return

        try:
            pubsub = self._client.pubsub()
            pubsub.subscribe(**{channel: callback})

            logger.info("Subscribed to Redis channel", extra={'channel': channel})

            # Start listening (blocking)
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        callback(data)
                    except Exception as e:
                        logger.error("Error processing message", extra={
                            'channel': channel,
                            'error': str(e)
                        })

        except Exception as e:
            logger.error("Channel subscription failed", extra={
                'channel': channel,
                'error': str(e)
            })

    # Future WebSocket Scaling Support
    def store_websocket_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Store WebSocket session data.

        Used for WebSocket server clustering and session recovery.
        """
        try:
            with self.connection() as conn:
                return conn.setex(f"ws:session:{session_id}", ttl, json.dumps(data))
        except Exception as e:
            logger.debug("Session storage failed", extra={'session_id': session_id, 'error': str(e)})
            return False

    def get_websocket_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve WebSocket session data.
        """
        try:
            with self.connection() as conn:
                data = conn.get(f"ws:session:{session_id}")
                return json.loads(data) if data else None
        except Exception as e:
            logger.debug("Session retrieval failed", extra={'session_id': session_id, 'error': str(e)})
            return None

    # Health and Monitoring
    def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis connection and performance statistics.
        """
        if not self.enabled:
            return {'enabled': False}

        try:
            with self.connection() as conn:
                info = conn.info()
                return {
                    'enabled': True,
                    'available': True,
                    'connections': info.get('connected_clients', 0),
                    'memory_used': info.get('used_memory_human', 'unknown'),
                    'uptime_seconds': info.get('uptime_in_seconds', 0),
                }
        except Exception as e:
            return {
                'enabled': True,
                'available': False,
                'error': str(e),
            }


class MockRedisConnection:
    """
    Mock Redis connection for when Redis is unavailable.

    Provides same interface but does nothing.
    Ensures application continues working without Redis.
    """

    def ping(self) -> bool:
        return False

    def get(self, key: str) -> None:
        return None

    def setex(self, key: str, ttl: int, value: str) -> bool:
        return False

    def delete(self, key: str) -> int:
        return 0

    def publish(self, channel: str, message: str) -> int:
        return 0


# Global Redis client instance
redis_client = RedisClient()


# Example usage functions
def cache_challenge_data(challenge_id: str, data: Dict[str, Any]) -> bool:
    """
    Cache frequently accessed challenge data.

    Example: Cache challenge summary for dashboard performance.
    """
    key = f"challenge:{challenge_id}:summary"
    return redis_client.set_cache(key, json.dumps(data), ttl_seconds=300)  # 5 minutes


def get_cached_challenge_data(challenge_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached challenge data.
    """
    key = f"challenge:{challenge_id}:summary"
    cached = redis_client.get_cache(key)
    return json.loads(cached) if cached else None


def queue_worker_task(task_type: str, payload: Dict[str, Any]) -> bool:
    """
    Queue background task for workers.

    Example: Queue risk analysis for a challenge.
    """
    return redis_client.publish_message(f"worker:{task_type}", payload)


# Export for easy importing
__all__ = ['redis_client', 'cache_challenge_data', 'get_cached_challenge_data', 'queue_worker_task']