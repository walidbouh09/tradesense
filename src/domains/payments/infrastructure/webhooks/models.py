"""Webhook event models for audit trail."""

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped

from shared.kernel.entity import Base


class WebhookEventModel(Base):
    """Immutable webhook event log for audit trail."""

    __tablename__ = "webhook_events"

    # Primary key - using timestamp + provider + event_id for uniqueness
    id: Mapped[str] = Column(String(255), primary_key=True)

    # Webhook metadata
    provider: Mapped[str] = Column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = Column(String(100), nullable=False, index=True)
    event_id: Mapped[str] = Column(String(255), nullable=False, unique=True, index=True)

    # Payment reference (if applicable)
    payment_id: Mapped[Optional[str]] = Column(String(255), index=True)
    idempotency_key: Mapped[Optional[str]] = Column(String(255), index=True)

    # Event data
    raw_payload: Mapped[str] = Column(Text, nullable=False)
    parsed_data: Mapped[Optional[Dict[str, Any]]] = Column(JSON)

    # Signature verification
    signature: Mapped[str] = Column(String(500), nullable=False)
    signature_verified: Mapped[bool] = Column(Boolean, default=False)

    # Processing status
    processed: Mapped[bool] = Column(Boolean, default=False, index=True)
    processing_attempts: Mapped[int] = Column(Integer, default=0)
    processing_error: Mapped[Optional[str]] = Column(Text)
    processing_error_code: Mapped[Optional[str]] = Column(String(50))

    # Idempotency
    idempotency_processed: Mapped[bool] = Column(Boolean, default=False)

    # Timestamps (immutable audit trail)
    received_at: Mapped[datetime] = Column(DateTime, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = Column(DateTime)

    # Additional metadata
    user_agent: Mapped[Optional[str]] = Column(String(500))
    source_ip: Mapped[Optional[str]] = Column(String(45))  # IPv6 support
    headers: Mapped[Optional[Dict[str, Any]]] = Column(JSON)

    # Indexes for performance
    __table_args__ = (
        Index('idx_webhook_provider_event_received',
              'provider', 'event_type', 'received_at'),
        Index('idx_webhook_payment_processed',
              'payment_id', 'processed'),
        Index('idx_webhook_received_processed',
              'received_at', 'processed'),
    )


class WebhookProcessingLog(Base):
    """Detailed processing log for webhook events."""

    __tablename__ = "webhook_processing_logs"

    id: Mapped[str] = Column(String(255), primary_key=True)

    # Reference to webhook event
    webhook_event_id: Mapped[str] = Column(String(255), nullable=False, index=True)

    # Processing details
    processing_step: Mapped[str] = Column(String(100), nullable=False)
    step_status: Mapped[str] = Column(String(50), nullable=False)  # SUCCESS, ERROR, WARNING
    message: Mapped[str] = Column(Text)

    # Context data
    context_data: Mapped[Optional[Dict[str, Any]]] = Column(JSON)

    # Timestamp
    logged_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)


class WebhookIdempotencyRecord(Base):
    """Idempotency records for webhook processing."""

    __tablename__ = "webhook_idempotency_records"

    # Composite key: provider + event_id
    provider: Mapped[str] = Column(String(50), primary_key=True)
    event_id: Mapped[str] = Column(String(255), primary_key=True)

    # Processing result
    processing_result: Mapped[Dict[str, Any]] = Column(JSON, nullable=False)

    # Expiration (TTL)
    expires_at: Mapped[float] = Column(String(50), nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)