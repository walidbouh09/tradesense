"""Payment domain SQLAlchemy models."""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped

from shared.kernel.entity import Base


class PaymentModel(Base):
    """SQLAlchemy model for Payment aggregate."""

    __tablename__ = "payments"

    # Primary key
    id: Mapped[UUID] = Column(PGUUID(as_uuid=True), primary_key=True)

    # Idempotency
    idempotency_key: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)

    # Financial details
    amount: Mapped[float] = Column(DECIMAL(20, 8), nullable=False)
    currency: Mapped[str] = Column(String(3), nullable=False)
    fees: Mapped[float] = Column(DECIMAL(20, 8), default=0.0)
    net_amount: Mapped[float] = Column(DECIMAL(20, 8), nullable=False)

    # Customer and payment method
    customer_id: Mapped[UUID] = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    payment_method_id: Mapped[str] = Column(String(255), nullable=False)

    # Status and provider
    status: Mapped[str] = Column(String(50), nullable=False, index=True)
    provider: Mapped[str] = Column(String(50), nullable=False)
    provider_payment_id: Mapped[Optional[str]] = Column(String(255), unique=True)

    # Description and metadata
    description: Mapped[str] = Column(Text, nullable=False)
    metadata_: Mapped[Optional[Dict[str, Any]]] = Column("metadata", JSON)

    # Failure handling
    failure_reason: Mapped[Optional[str]] = Column(Text)

    # Timestamps
    processed_at: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    transactions: Mapped[list["TransactionModel"]] = relationship(
        "TransactionModel",
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentMethodModel(Base):
    """SQLAlchemy model for PaymentMethod."""

    __tablename__ = "payment_methods"

    # Primary key
    payment_method_id: Mapped[str] = Column(String(255), primary_key=True)

    # Customer and provider
    customer_id: Mapped[UUID] = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = Column(String(50), nullable=False)
    provider: Mapped[str] = Column(String(50), nullable=False)

    # Status
    is_default: Mapped[bool] = Column(Boolean, default=False)
    is_active: Mapped[bool] = Column(Boolean, default=True)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = Column(DateTime)

    # Metadata
    metadata_: Mapped[Optional[Dict[str, Any]]] = Column("metadata", JSON)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TransactionModel(Base):
    """SQLAlchemy model for Transaction."""

    __tablename__ = "transactions"

    # Primary key
    id: Mapped[UUID] = Column(PGUUID(as_uuid=True), primary_key=True)

    # Relationships
    payment_id: Mapped[UUID] = Column(PGUUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)

    # Transaction details
    type: Mapped[str] = Column(String(50), nullable=False)
    amount: Mapped[float] = Column(DECIMAL(20, 8), nullable=False)
    currency: Mapped[str] = Column(String(3), nullable=False)
    status: Mapped[str] = Column(String(50), nullable=False, index=True)

    # Provider details
    provider_transaction_id: Mapped[Optional[str]] = Column(String(255))

    # Metadata
    metadata_: Mapped[Optional[Dict[str, Any]]] = Column("metadata", JSON)

    # Timestamps
    processed_at: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    payment: Mapped["PaymentModel"] = relationship("PaymentModel", back_populates="transactions")


class IdempotencyRecordModel(Base):
    """SQLAlchemy model for idempotency records."""

    __tablename__ = "idempotency_records"

    # Primary key
    key: Mapped[str] = Column(String(255), primary_key=True)

    # Result data
    result: Mapped[Dict[str, Any]] = Column(JSON, nullable=False)

    # Expiration
    expires_at: Mapped[float] = Column(Float, nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)


class WebhookEventModel(Base):
    """SQLAlchemy model for webhook events."""

    __tablename__ = "webhook_events"

    # Primary key
    id: Mapped[UUID] = Column(PGUUID(as_uuid=True), primary_key=True)

    # Event details
    provider: Mapped[str] = Column(String(50), nullable=False)
    event_type: Mapped[str] = Column(String(100), nullable=False)
    event_id: Mapped[str] = Column(String(255), nullable=False, index=True)
    payment_id: Mapped[Optional[str]] = Column(String(255), index=True)

    # Event data
    raw_payload: Mapped[str] = Column(Text, nullable=False)
    parsed_data: Mapped[Optional[Dict[str, Any]]] = Column(JSON)

    # Processing status
    processed: Mapped[bool] = Column(Boolean, default=False)
    processing_error: Mapped[Optional[str]] = Column(Text)

    # Timestamps
    received_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at: Mapped[Optional[datetime]] = Column(DateTime)

    # Indexes for performance
    __table_args__ = (
        {"schema": None},  # Use default schema
    )