"""Payment domain entities."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from shared.kernel.entity import AggregateRoot
from shared.kernel.events import DomainEvent
from shared.utils.money import Money


class PaymentStatus:
    """Payment status value object."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

    VALID_STATUSES = {
        PENDING, PROCESSING, SUCCEEDED, FAILED,
        CANCELLED, REFUNDED, PARTIALLY_REFUNDED
    }

    def __init__(self, value: str) -> None:
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid payment status: {value}")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PaymentStatus):
            return NotImplemented
        return self.value == other.value

    def is_terminal(self) -> bool:
        """Check if this status is terminal (no further transitions)."""
        return self.value in {self.SUCCEEDED, self.FAILED, self.CANCELLED}

    def can_transition_to(self, new_status: 'PaymentStatus') -> bool:
        """Check if transition to new status is valid."""
        transitions = {
            self.PENDING: {self.PROCESSING, self.CANCELLED},
            self.PROCESSING: {self.SUCCEEDED, self.FAILED, self.CANCELLED},
            self.SUCCEEDED: {self.REFUNDED, self.PARTIALLY_REFUNDED},
            self.FAILED: set(),  # Terminal
            self.CANCELLED: set(),  # Terminal
            self.REFUNDED: set(),  # Terminal
            self.PARTIALLY_REFUNDED: set(),  # Terminal
        }
        return new_status.value in transitions.get(self.value, set())


class Address:
    """Address value object for billing/shipping."""

    def __init__(
        self,
        street: str,
        city: str,
        state: str,
        postal_code: str,
        country: str,
        street2: Optional[str] = None,
    ) -> None:
        self.street = street
        self.street2 = street2
        self.city = city
        self.state = state
        self.postal_code = postal_code
        self.country = country

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Address):
            return NotImplemented
        return (
            self.street == other.street
            and self.street2 == other.street2
            and self.city == other.city
            and self.state == other.state
            and self.postal_code == other.postal_code
            and self.country == other.country
        )

    def __str__(self) -> str:
        address = f"{self.street}"
        if self.street2:
            address += f", {self.street2}"
        address += f", {self.city}, {self.state} {self.postal_code}, {self.country}"
        return address


class PaymentMethod:
    """Payment method value object."""

    CARD = "card"
    BANK_ACCOUNT = "bank_account"
    DIGITAL_WALLET = "digital_wallet"

    def __init__(
        self,
        payment_method_id: str,
        type: str,
        provider: str,
        is_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        self.payment_method_id = payment_method_id
        self.type = type
        self.provider = provider
        self.is_default = is_default
        self.metadata = metadata or {}
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        """Check if payment method is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PaymentMethod):
            return NotImplemented
        return self.payment_method_id == other.payment_method_id


class Payment(AggregateRoot):
    """Payment aggregate root."""

    def __init__(
        self,
        payment_id: UUID,
        idempotency_key: str,
        amount: Money,
        customer_id: UUID,
        payment_method: PaymentMethod,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        provider: str = "stripe",
    ) -> None:
        super().__init__(payment_id)
        self.idempotency_key = idempotency_key
        self.amount = amount
        self.customer_id = customer_id
        self.payment_method = payment_method
        self.description = description
        self.metadata = metadata or {}
        self.provider = provider

        # State
        self.status = PaymentStatus(PaymentStatus.PENDING)
        self.provider_payment_id: Optional[str] = None
        self.failure_reason: Optional[str] = None
        self.processed_at: Optional[datetime] = None

        # Financial tracking
        self.fees: Money = Money(0, amount.currency)
        self.net_amount: Money = amount

        # Audit trail
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # Transactions (for refunds, etc.)
        self.transactions: List['Transaction'] = []

    def mark_as_processing(self) -> None:
        """Mark payment as being processed."""
        if not self.status.can_transition_to(PaymentStatus(PaymentStatus.PROCESSING)):
            raise ValueError(f"Cannot transition from {self.status} to processing")

        old_status = self.status
        self.status = PaymentStatus(PaymentStatus.PROCESSING)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PaymentStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

    def mark_as_succeeded(
        self,
        provider_payment_id: str,
        fees: Money,
        processed_at: datetime,
    ) -> None:
        """Mark payment as succeeded."""
        if not self.status.can_transition_to(PaymentStatus(PaymentStatus.SUCCEEDED)):
            raise ValueError(f"Cannot transition from {self.status} to succeeded")

        old_status = self.status
        self.status = PaymentStatus(PaymentStatus.SUCCEEDED)
        self.provider_payment_id = provider_payment_id
        self.fees = fees
        self.net_amount = self.amount - fees
        self.processed_at = processed_at
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PaymentStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(PaymentSucceeded(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            amount=self.amount,
            net_amount=self.net_amount,
            fees=self.fees,
            provider=self.provider,
            provider_payment_id=provider_payment_id,
            processed_at=processed_at,
            metadata=self.metadata,
        ))

    def mark_as_failed(self, reason: str) -> None:
        """Mark payment as failed."""
        if not self.status.can_transition_to(PaymentStatus(PaymentStatus.FAILED)):
            raise ValueError(f"Cannot transition from {self.status} to failed")

        old_status = self.status
        self.status = PaymentStatus(PaymentStatus.FAILED)
        self.failure_reason = reason
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PaymentStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(PaymentFailed(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            amount=self.amount,
            failure_reason=reason,
            provider=self.provider,
            metadata=self.metadata,
        ))

    def cancel(self) -> None:
        """Cancel the payment."""
        if not self.status.can_transition_to(PaymentStatus(PaymentStatus.CANCELLED)):
            raise ValueError(f"Cannot transition from {self.status} to cancelled")

        old_status = self.status
        self.status = PaymentStatus(PaymentStatus.CANCELLED)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PaymentStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(PaymentCancelled(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            amount=self.amount,
            cancelled_at=self.updated_at,
        ))

    def add_transaction(self, transaction: 'Transaction') -> None:
        """Add a transaction to this payment."""
        self.transactions.append(transaction)

        # Update payment status based on transaction
        if transaction.type == TransactionType.REFUND:
            if self.status.value == PaymentStatus.SUCCEEDED:
                self.status = PaymentStatus(PaymentStatus.REFUNDED)
            elif self.status.value == PaymentStatus.PARTIALLY_REFUNDED:
                # Check if fully refunded
                total_refunded = sum(
                    t.amount.amount for t in self.transactions
                    if t.type == TransactionType.REFUND and t.status == TransactionStatus.SUCCEEDED
                )
                if total_refunded >= self.amount.amount:
                    self.status = PaymentStatus(PaymentStatus.REFUNDED)
            self.updated_at = datetime.utcnow()


class Transaction:
    """Transaction entity for tracking payment operations."""

    def __init__(
        self,
        transaction_id: UUID,
        payment_id: UUID,
        type: str,
        amount: Money,
        status: str = "pending",
        provider_transaction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.transaction_id = transaction_id
        self.payment_id = payment_id
        self.type = type
        self.amount = amount
        self.status = status
        self.provider_transaction_id = provider_transaction_id
        self.metadata = metadata or {}

        self.created_at = datetime.utcnow()
        self.processed_at: Optional[datetime] = None


class TransactionType:
    """Transaction type constants."""
    CHARGE = "charge"
    REFUND = "refund"
    PARTIAL_REFUND = "partial_refund"


class TransactionStatus:
    """Transaction status constants."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# Domain Events
class PaymentCreated(DomainEvent):
    """Event emitted when a payment is created."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        amount: Money,
        payment_method_id: str,
        description: str,
        provider: str,
        idempotency_key: str,
        metadata: Dict[str, Any],
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.amount = amount
        self.payment_method_id = payment_method_id
        self.description = description
        self.provider = provider
        self.idempotency_key = idempotency_key
        self.metadata = metadata


class PaymentStatusChanged(DomainEvent):
    """Event emitted when payment status changes."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        old_status: str,
        new_status: str,
        changed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_at = changed_at


class PaymentSucceeded(DomainEvent):
    """Event emitted when payment succeeds."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        amount: Money,
        net_amount: Money,
        fees: Money,
        provider: str,
        provider_payment_id: str,
        processed_at: datetime,
        metadata: Dict[str, Any],
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.amount = amount
        self.net_amount = net_amount
        self.fees = fees
        self.provider = provider
        self.provider_payment_id = provider_payment_id
        self.processed_at = processed_at
        self.metadata = metadata


class PaymentFailed(DomainEvent):
    """Event emitted when payment fails."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        amount: Money,
        failure_reason: str,
        provider: str,
        metadata: Dict[str, Any],
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.amount = amount
        self.failure_reason = failure_reason
        self.provider = provider
        self.metadata = metadata


class PaymentCancelled(DomainEvent):
    """Event emitted when payment is cancelled."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        amount: Money,
        cancelled_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.amount = amount
        self.cancelled_at = cancelled_at


class PaymentRefunded(DomainEvent):
    """Event emitted when payment is refunded."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        refund_amount: Money,
        total_refunded: Money,
        provider_refund_id: str,
        refunded_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.refund_amount = refund_amount
        self.total_refunded = total_refunded
        self.provider_refund_id = provider_refund_id
        self.refunded_at = refunded_at


class WebhookReceived(DomainEvent):
    """Event emitted when a webhook is received from payment provider."""

    def __init__(
        self,
        aggregate_id: UUID,
        provider: str,
        event_type: str,
        provider_event_id: str,
        raw_payload: str,
        processed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.provider = provider
        self.event_type = event_type
        self.provider_event_id = provider_event_id
        self.raw_payload = raw_payload
        self.processed_at = processed_at