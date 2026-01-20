"""
Audit Service - Immutable Audit Log System

Core Responsibilities:
- Write domain events to immutable audit log
- Provide reconstruction capabilities
- Ensure tamper-evident storage
- Handle retention and archival
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from shared.infrastructure.messaging.event_bus import EventBus
from shared.kernel.events import DomainEvent

from .models import AuditEvent, AuditReconstruction, AuditRetentionPolicy


class AuditService:
    """Immutable audit log service."""

    def __init__(
        self,
        session: AsyncSession,
        event_bus: EventBus,
        service_name: str = "tradesense",
        service_version: str = "1.0.0",
        environment: str = "production",
    ):
        self.session = session
        self.event_bus = event_bus
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment

        # Register event handlers
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """Register handlers for all domain events."""
        # Subscribe to all domain events for audit logging
        # This is a simplified registration - in practice, you'd register
        # handlers for all known event types
        pass

    async def audit_domain_event(
        self,
        domain_event: DomainEvent,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Write a domain event to the immutable audit log.

        Returns the sequence ID of the audit entry.
        """
        # Serialize event data
        event_data = self._serialize_domain_event(domain_event)

        # Get previous hash for chain
        previous_hash = await self._get_latest_hash()

        # Create audit event
        audit_event = AuditEvent(
            previous_hash=previous_hash,
            aggregate_id=str(domain_event.aggregate_id),
            aggregate_type=domain_event.__class__.__name__.replace("Event", "").replace("Created", "").replace("Updated", "").replace("Deleted", ""),
            event_type=domain_event.__class__.__name__,
            event_version=1,  # Would be determined by event schema versioning
            event_data=json.dumps(event_data, sort_keys=True),
            correlation_id=correlation_id,
            causation_id=causation_id,
            user_id=user_id,
            session_id=session_id,
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            event_timestamp=domain_event.occurred_at,
            ip_address=ip_address,
            user_agent=user_agent,
            tags=tags or {},
        )

        # Calculate and set hash chain
        audit_event.hash_chain = audit_event._calculate_hash()

        # Save to database
        self.session.add(audit_event)
        await self.session.commit()
        await self.session.refresh(audit_event)

        return audit_event.sequence_id

    def _serialize_domain_event(self, event: DomainEvent) -> Dict[str, Any]:
        """Serialize domain event to JSON-compatible format."""
        # Get all non-private attributes
        event_dict = {}
        for attr in dir(event):
            if not attr.startswith('_') and not callable(getattr(event, attr)):
                value = getattr(event, attr)
                # Convert complex objects to serializable format
                if isinstance(value, datetime):
                    event_dict[attr] = value.isoformat()
                elif hasattr(value, '__dict__'):
                    # For value objects, convert to dict
                    event_dict[attr] = str(value)
                else:
                    event_dict[attr] = value

        return event_dict

    async def _get_latest_hash(self) -> Optional[str]:
        """Get the hash of the most recent audit event."""
        result = await self.session.execute(
            select(AuditEvent.hash_chain).order_by(desc(AuditEvent.sequence_id)).limit(1)
        )
        latest_hash = result.scalar_one_or_none()
        return latest_hash

    async def reconstruct_challenge_decision(self, challenge_id: str) -> Dict[str, Any]:
        """
        Reconstruct a challenge's decision-making process.

        Returns complete audit trail showing step-by-step decision process.
        """
        # Get all audit events for this challenge
        result = await self.session.execute(
            select(AuditEvent).where(
                and_(
                    AuditEvent.aggregate_id == challenge_id,
                    AuditEvent.aggregate_type == "Challenge"
                )
            ).order_by(AuditEvent.sequence_id)
        )

        audit_events = result.scalars().all()

        # Use reconstruction helper
        return AuditReconstruction.reconstruct_challenge_decision(challenge_id, audit_events)

    async def reconstruct_payment_flow(self, payment_id: str) -> Dict[str, Any]:
        """
        Reconstruct complete payment processing flow.

        Shows all events from payment initiation to completion/failure.
        """
        result = await self.session.execute(
            select(AuditEvent).where(
                AuditEvent.aggregate_id == payment_id
            ).order_by(AuditEvent.sequence_id)
        )

        audit_events = result.scalars().all()

        return AuditReconstruction.reconstruct_payment_flow(payment_id, audit_events)

    async def verify_audit_integrity(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Verify audit log integrity over a range of events.

        Returns verification results and any tampering detected.
        """
        # Build query
        query = select(AuditEvent).order_by(AuditEvent.sequence_id)

        if start_sequence:
            query = query.where(AuditEvent.sequence_id >= start_sequence)
        if end_sequence:
            query = query.where(AuditEvent.sequence_id <= end_sequence)

        query = query.limit(limit)

        result = await self.session.execute(query)
        audit_events = result.scalars().all()

        return AuditReconstruction.verify_audit_chain(audit_events)

    async def get_audit_events(
        self,
        aggregate_id: Optional[str] = None,
        aggregate_type: Optional[str] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with flexible filtering."""
        conditions = []

        if aggregate_id:
            conditions.append(AuditEvent.aggregate_id == aggregate_id)
        if aggregate_type:
            conditions.append(AuditEvent.aggregate_type == aggregate_type)
        if event_type:
            conditions.append(AuditEvent.event_type == event_type)
        if correlation_id:
            conditions.append(AuditEvent.correlation_id == correlation_id)
        if user_id:
            conditions.append(AuditEvent.user_id == user_id)
        if start_date:
            conditions.append(AuditEvent.event_timestamp >= start_date)
        if end_date:
            conditions.append(AuditEvent.event_timestamp <= end_date)

        query = select(AuditEvent)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(AuditEvent.event_timestamp)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_audit_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get audit statistics."""
        query = select(
            func.count(AuditEvent.sequence_id).label('total_events'),
            func.min(AuditEvent.event_timestamp).label('earliest_event'),
            func.max(AuditEvent.event_timestamp).label('latest_event'),
            func.count(func.distinct(AuditEvent.aggregate_id)).label('unique_aggregates'),
        )

        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append(AuditEvent.event_timestamp >= start_date)
            if end_date:
                conditions.append(AuditEvent.event_timestamp <= end_date)

            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        row = result.first()

        return {
            "total_events": row.total_events or 0,
            "earliest_event": row.earliest_event.isoformat() if row.earliest_event else None,
            "latest_event": row.latest_event.isoformat() if row.latest_event else None,
            "unique_aggregates": row.unique_aggregates or 0,
            "audit_period_days": (
                (row.latest_event - row.earliest_event).days
                if row.latest_event and row.earliest_event else 0
            ),
        }

    async def cleanup_expired_events(self) -> int:
        """Clean up events beyond retention period (for non-critical events only)."""
        # This would implement retention policy cleanup
        # In production, would archive to cold storage first

        cutoff_date = datetime.utcnow().replace(
            year=datetime.utcnow().year - AuditRetentionPolicy.RETENTION_YEARS
        )

        # Count candidates for cleanup (non-critical events)
        result = await self.session.execute(
            select(func.count(AuditEvent.sequence_id)).where(
                and_(
                    AuditEvent.event_timestamp < cutoff_date,
                    AuditEvent.event_type.notin_({
                        "ChallengePassed",
                        "ChallengeFailed",
                        "PaymentSucceeded",
                        "PaymentFailed",
                        "RuleViolationDetected",
                        "PaymentRefunded",
                    })
                )
            )
        )

        count = result.scalar() or 0

        # In production: archive then delete
        # For now, just return count
        return count

    async def export_audit_trail(
        self,
        aggregate_id: str,
        format: str = "json"
    ) -> str:
        """
        Export complete audit trail for an aggregate.

        Returns JSON representation of the complete audit trail.
        """
        events = await self.get_audit_events(aggregate_id=aggregate_id)

        if format == "json":
            export_data = {
                "aggregate_id": aggregate_id,
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_events": len(events),
                "events": [
                    {
                        "sequence_id": event.sequence_id,
                        "hash_chain": event.hash_chain,
                        "event_type": event.event_type,
                        "event_timestamp": event.event_timestamp.isoformat(),
                        "event_data": json.loads(event.event_data),
                        "correlation_id": event.correlation_id,
                        "user_id": event.user_id,
                        "service_name": event.service_name,
                    }
                    for event in events
                ]
            }

            return json.dumps(export_data, indent=2, sort_keys=True)

        raise ValueError(f"Unsupported export format: {format}")


# Event Handler Integration
class DomainEventAuditHandler:
    """Handles domain events and writes them to audit log."""

    def __init__(self, audit_service: AuditService):
        self.audit_service = audit_service

    async def handle_domain_event(
        self,
        event: DomainEvent,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handle any domain event by writing to audit log."""
        context = context or {}

        await self.audit_service.audit_domain_event(
            domain_event=event,
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            user_id=context.get("user_id"),
            session_id=context.get("session_id"),
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
            tags=context.get("tags", {}),
        )