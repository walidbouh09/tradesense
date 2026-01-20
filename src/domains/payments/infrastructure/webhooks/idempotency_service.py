"""Webhook idempotency service."""

import json
import time
from typing import Dict, Any, Optional

import redis.asyncio as redis

from shared.infrastructure.logging.audit_logger import AuditLogger


class WebhookIdempotencyService:
    """Ensures webhook processing is idempotent."""

    def __init__(
        self,
        redis_client: redis.Redis,
        audit_logger: AuditLogger,
        ttl_seconds: int = 86400 * 7  # 7 days
    ):
        self.redis = redis_client
        self.audit_logger = audit_logger
        self.ttl_seconds = ttl_seconds

    async def check_and_store(
        self,
        provider: str,
        event_id: str,
        processing_result: Dict[str, Any]
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if webhook has been processed and store result if not.

        Returns:
            Tuple of (is_duplicate, previous_result)
        """
        key = f"webhook_idempotency:{provider}:{event_id}"

        try:
            # Check if already processed
            existing_result = await self.redis.get(key)
            if existing_result:
                try:
                    previous_result = json.loads(existing_result)
                    self.audit_logger.log_security_event(
                        event_type="webhook_idempotency_duplicate",
                        success=True,
                        details={
                            "provider": provider,
                            "event_id": event_id,
                            "duplicate_detected": True,
                        }
                    )
                    return True, previous_result
                except json.JSONDecodeError:
                    # Corrupted data, treat as not processed
                    pass

            # Store processing result
            result_json = json.dumps(processing_result)
            await self.redis.setex(key, self.ttl_seconds, result_json)

            self.audit_logger.log_security_event(
                event_type="webhook_idempotency_stored",
                success=True,
                details={
                    "provider": provider,
                    "event_id": event_id,
                    "ttl_seconds": self.ttl_seconds,
                }
            )

            return False, None

        except Exception as e:
            # On Redis error, log and allow processing (fail open)
            self.audit_logger.log_security_event(
                event_type="webhook_idempotency_error",
                success=False,
                details={
                    "provider": provider,
                    "event_id": event_id,
                    "error": str(e),
                },
                severity="ERROR"
            )
            return False, None  # Allow processing on error

    async def get_processing_result(
        self,
        provider: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get stored processing result for webhook."""
        key = f"webhook_idempotency:{provider}:{event_id}"

        try:
            result = await self.redis.get(key)
            if result:
                return json.loads(result)
        except Exception as e:
            self.audit_logger.log_security_event(
                event_type="webhook_idempotency_retrieval_error",
                success=False,
                details={
                    "provider": provider,
                    "event_id": event_id,
                    "error": str(e),
                },
                severity="ERROR"
            )

        return None

    async def cleanup_expired(self) -> int:
        """Clean up expired idempotency records."""
        # Redis automatically expires keys, but we can implement
        # manual cleanup if needed for monitoring
        return 0

    async def get_statistics(self) -> Dict[str, Any]:
        """Get idempotency statistics."""
        try:
            # Get all webhook idempotency keys
            pattern = "webhook_idempotency:*"
            keys = await self.redis.keys(pattern)
            total_records = len(keys)

            # Get sample of TTL values
            ttl_samples = []
            for key in keys[:10]:  # Sample first 10
                try:
                    ttl = await self.redis.ttl(key)
                    if ttl > 0:
                        ttl_samples.append(ttl)
                except:
                    pass

            return {
                "total_idempotency_records": total_records,
                "ttl_samples": ttl_samples,
                "average_ttl": sum(ttl_samples) / len(ttl_samples) if ttl_samples else 0,
            }

        except Exception as e:
            self.audit_logger.log_security_event(
                event_type="webhook_idempotency_stats_error",
                success=False,
                details={"error": str(e)},
                severity="ERROR"
            )
            return {"error": str(e)}