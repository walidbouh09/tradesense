"""Audit writer worker for processing domain events."""

import asyncio
import json
from typing import Dict, Any

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class AuditWriterWorker:
    """Worker that consumes domain events and writes them to audit log."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        stream_name: str = "domain_events",
        consumer_group: str = "audit_writers",
        consumer_name: str = "audit_writer_1",
    ) -> None:
        self._redis = redis_client
        self._stream_name = stream_name
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._running = False
    
    async def start(self) -> None:
        """Start the audit writer worker."""
        logger.info("Starting audit writer worker")
        
        try:
            # Create consumer group if it doesn't exist
            await self._redis.xgroup_create(
                self._stream_name,
                self._consumer_group,
                id="0",
                mkstream=True,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        
        self._running = True
        
        while self._running:
            try:
                # Read messages from stream
                messages = await self._redis.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    {self._stream_name: ">"},
                    count=10,
                    block=1000,  # Block for 1 second
                )
                
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        await self._process_event(msg_id, fields)
                        
                        # Acknowledge message
                        await self._redis.xack(self._stream_name, self._consumer_group, msg_id)
            
            except Exception as e:
                logger.error("Error in audit writer worker", error=str(e))
                await asyncio.sleep(5)  # Wait before retrying
    
    async def stop(self) -> None:
        """Stop the audit writer worker."""
        logger.info("Stopping audit writer worker")
        self._running = False
    
    async def _process_event(self, msg_id: bytes, fields: Dict[bytes, bytes]) -> None:
        """Process a single domain event."""
        try:
            # Convert bytes to strings
            event_data = {k.decode(): v.decode() for k, v in fields.items()}
            
            # Write to audit log (in real implementation, this would write to a database)
            await self._write_to_audit_log(event_data)
            
            logger.info(
                "Event written to audit log",
                event_type=event_data.get("event_type"),
                event_id=event_data.get("event_id"),
                aggregate_id=event_data.get("aggregate_id"),
            )
        
        except Exception as e:
            logger.error(
                "Failed to process event for audit",
                msg_id=msg_id.decode(),
                error=str(e),
            )
            raise
    
    async def _write_to_audit_log(self, event_data: Dict[str, Any]) -> None:
        """Write event to audit log storage."""
        # In a real implementation, this would:
        # 1. Write to an append-only audit database
        # 2. Ensure immutability and tamper-evidence
        # 3. Handle encryption for sensitive data
        # 4. Implement proper error handling and retries
        
        # For demo purposes, just log the event
        logger.info("AUDIT_LOG", **event_data)