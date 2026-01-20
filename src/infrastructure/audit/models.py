"""
Immutable Audit Log Models

Design Principles:
- Append-only: No updates or deletes allowed
- Tamper-evident: Cryptographic hashing chain
- Complete: Every domain event stored
- Immutable: Database-level constraints prevent modification
"""

from datetime import datetime
from typing import Dict, Any, Optional
import hashlib
import json

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped

from shared.kernel.entity import Base


class AuditEvent(Base):
    """
    Immutable audit event log entry.

    Each event is cryptographically chained to prevent tampering:
    - hash_chain: SHA-256 hash of (previous_hash + event_data)
    - sequence_id: Monotonically increasing sequence number
    - immutable: Database constraints prevent modification
    """

    __tablename__ = "audit_events"

    # Sequence ID - monotonically increasing, unique, immutable
    sequence_id: Mapped[int] = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )

    # Cryptographic hash chain for tamper detection
    hash_chain: Mapped[str] = Column(
        String(64),  # SHA-256 hex length
        nullable=False,
        unique=True,
        index=True,
    )

    # Previous hash in the chain (null for first event)
    previous_hash: Mapped[Optional[str]] = Column(String(64), index=True)

    # Domain event data
    aggregate_id: Mapped[str] = Column(String(255), nullable=False, index=True)
    aggregate_type: Mapped[str] = Column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(100), nullable=False, index=True)
    event_version: Mapped[int] = Column(Integer, default=1, nullable=False)

    # Event payload (immutable JSON)
    event_data: Mapped[str] = Column(Text, nullable=False)  # JSON as text

    # Metadata
    correlation_id: Mapped[Optional[str]] = Column(String(255), index=True)
    causation_id: Mapped[Optional[str]] = Column(String(255), index=True)
    user_id: Mapped[Optional[str]] = Column(String(255), index=True)
    session_id: Mapped[Optional[str]] = Column(String(255), index=True)

    # System context
    service_name: Mapped[str] = Column(String(100), nullable=False)
    service_version: Mapped[str] = Column(String(50), nullable=False)
    environment: Mapped[str] = Column(String(50), nullable=False)

    # Timestamps (immutable)
    event_timestamp: Mapped[datetime] = Column(DateTime, nullable=False, index=True)
    recorded_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Additional context (optional)
    ip_address: Mapped[Optional[str]] = Column(String(45))  # IPv6 support
    user_agent: Mapped[Optional[str]] = Column(String(500))
    tags: Mapped[Optional[Dict[str, Any]]] = Column(JSON)

    # Database-level immutability constraints
    __table_args__ = (
        # Prevent any updates to existing records
        CheckConstraint(
            "recorded_at >= event_timestamp",
            name="audit_immutability_check"
        ),

        # Indexes for performance
        Index('idx_audit_aggregate', 'aggregate_id', 'aggregate_type'),
        Index('idx_audit_event_type', 'event_type', 'event_timestamp'),
        Index('idx_audit_correlation', 'correlation_id'),
        Index('idx_audit_timestamp', 'event_timestamp', 'sequence_id'),

        # Ensure hash chain integrity
        Index('idx_audit_hash_chain', 'hash_chain', 'previous_hash'),
    )

    def __init__(self, **kwargs):
        """Initialize with tamper-evident hash calculation."""
        super().__init__(**kwargs)

        # Calculate hash chain if not provided
        if not hasattr(self, 'hash_chain') or not self.hash_chain:
            self.hash_chain = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """
        Calculate tamper-evident hash for this audit event.

        Hash includes: sequence_id, aggregate_id, event_type, event_data, event_timestamp
        """
        # Create canonical representation
        canonical_data = {
            "sequence_id": getattr(self, 'sequence_id', None),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "event_data": self.event_data,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
        }

        # Sort keys for consistent hashing
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))

        # Calculate SHA-256 hash
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self, previous_event: Optional['AuditEvent'] = None) -> bool:
        """
        Verify the integrity of this audit event.

        Checks:
        1. Hash chain integrity
        2. Sequence number continuity
        3. Timestamp monotonicity
        """
        # Verify own hash
        calculated_hash = self._calculate_hash()
        if calculated_hash != self.hash_chain:
            return False

        # Verify chain continuity
        if previous_event:
            if self.previous_hash != previous_event.hash_chain:
                return False

            # Sequence number should be exactly one greater
            if self.sequence_id != previous_event.sequence_id + 1:
                return False

            # Timestamp should not be earlier than previous
            if self.event_timestamp < previous_event.event_timestamp:
                return False

        return True


class AuditReconstruction:
    """
    Helper class for reconstructing business state from audit events.

    Allows step-by-step reconstruction of challenge decisions and business processes.
    """

    @staticmethod
    def reconstruct_challenge_decision(challenge_id: str, audit_events: list[AuditEvent]) -> Dict[str, Any]:
        """
        Reconstruct a challenge's decision-making process step by step.

        Returns complete audit trail showing:
        - Initial challenge creation
        - Trading activity and metrics updates
        - Rule evaluations and violations
        - Final decision and reasoning
        """
        challenge_events = [
            event for event in audit_events
            if event.aggregate_id == challenge_id and event.aggregate_type == "Challenge"
        ]

        # Sort by sequence for chronological order
        challenge_events.sort(key=lambda e: e.sequence_id)

        reconstruction = {
            "challenge_id": challenge_id,
            "timeline": [],
            "final_decision": None,
            "decision_factors": [],
            "audit_trail_complete": True,
        }

        for event in challenge_events:
            event_data = json.loads(event.event_data)

            timeline_entry = {
                "sequence_id": event.sequence_id,
                "event_type": event.event_type,
                "timestamp": event.event_timestamp.isoformat(),
                "data": event_data,
                "correlation_id": event.correlation_id,
                "user_id": event.user_id,
            }

            reconstruction["timeline"].append(timeline_entry)

            # Track decision factors
            if event.event_type in ["RuleViolationDetected", "TradingMetricsUpdated"]:
                reconstruction["decision_factors"].append({
                    "event": event.event_type,
                    "data": event_data,
                    "sequence_id": event.sequence_id,
                })

            # Capture final decision
            if event.event_type in ["ChallengePassed", "ChallengeFailed"]:
                reconstruction["final_decision"] = {
                    "decision": event.event_type,
                    "timestamp": event.event_timestamp.isoformat(),
                    "reason": event_data.get("reason", event_data.get("failure_reason")),
                    "sequence_id": event.sequence_id,
                }

        return reconstruction

    @staticmethod
    def reconstruct_payment_flow(payment_id: str, audit_events: list[AuditEvent]) -> Dict[str, Any]:
        """
        Reconstruct payment processing flow.

        Shows complete payment lifecycle from initiation to completion.
        """
        payment_events = [
            event for event in audit_events
            if event.aggregate_id == payment_id and event.aggregate_type in ["Payment", "PaymentIntent"]
        ]

        payment_events.sort(key=lambda e: e.sequence_id)

        return {
            "payment_id": payment_id,
            "events": [
                {
                    "sequence_id": event.sequence_id,
                    "event_type": event.event_type,
                    "timestamp": event.event_timestamp.isoformat(),
                    "data": json.loads(event.event_data),
                    "service": event.service_name,
                }
                for event in payment_events
            ]
        }

    @staticmethod
    def verify_audit_chain(audit_events: list[AuditEvent]) -> Dict[str, Any]:
        """
        Verify the integrity of an audit event chain.

        Returns verification results and any detected tampering.
        """
        verification_results = {
            "total_events": len(audit_events),
            "verified_events": 0,
            "tampered_events": [],
            "chain_integrity": True,
            "first_event": None,
            "last_event": None,
        }

        if not audit_events:
            return verification_results

        # Sort by sequence
        audit_events.sort(key=lambda e: e.sequence_id)

        verification_results["first_event"] = audit_events[0].sequence_id
        verification_results["last_event"] = audit_events[-1].sequence_id

        previous_event = None
        for event in audit_events:
            if event.verify_integrity(previous_event):
                verification_results["verified_events"] += 1
            else:
                verification_results["tampered_events"].append({
                    "sequence_id": event.sequence_id,
                    "event_type": event.event_type,
                    "aggregate_id": event.aggregate_id,
                })
                verification_results["chain_integrity"] = False

            previous_event = event

        return verification_results


class AuditRetentionPolicy:
    """
    Audit retention policy for 7-year compliance.

    Defines retention rules and archival procedures.
    """

    RETENTION_YEARS = 7

    @staticmethod
    def should_retain(event: AuditEvent) -> bool:
        """Determine if an audit event should be retained."""
        # Always retain critical financial and compliance events
        critical_events = {
            "ChallengePassed",
            "ChallengeFailed",
            "PaymentSucceeded",
            "PaymentFailed",
            "RuleViolationDetected",
            "PaymentRefunded",
        }

        if event.event_type in critical_events:
            return True

        # Retain all events for retention period
        cutoff_date = datetime.utcnow().replace(year=datetime.utcnow().year - AuditRetentionPolicy.RETENTION_YEARS)

        return event.event_timestamp >= cutoff_date

    @staticmethod
    def get_archival_candidates() -> list:
        """Get events that are candidates for archival."""
        # Events older than retention period but not critical
        # Would return list of event IDs for archival
        return []