"""Payment domain events."""

from uuid import UUID
from datetime import datetime
from typing import Dict, Any

from shared.kernel.events import DomainEvent


class PaymentInitiated(DomainEvent):
    """Event emitted when a payment is initiated."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        amount: float,
        currency: str,
        payment_method_id: str,
        provider: str,
        idempotency_key: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.amount = amount
        self.currency = currency
        self.payment_method_id = payment_method_id
        self.provider = provider
        self.idempotency_key = idempotency_key


class PaymentProcessed(DomainEvent):
    """Event emitted when a payment is processed."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        provider_payment_id: str,
        status: str,
        processed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.provider_payment_id = provider_payment_id
        self.status = status
        self.processed_at = processed_at


class PaymentRefundInitiated(DomainEvent):
    """Event emitted when a refund is initiated."""

    def __init__(
        self,
        aggregate_id: UUID,
        payment_id: UUID,
        refund_amount: float,
        currency: str,
        reason: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.payment_id = payment_id
        self.refund_amount = refund_amount
        self.currency = currency
        self.reason = reason


class PaymentMethodCreated(DomainEvent):
    """Event emitted when a payment method is created."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        payment_method_id: str,
        type: str,
        provider: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.payment_method_id = payment_method_id
        self.type = type
        self.provider = provider


class WebhookProcessed(DomainEvent):
    """Event emitted when a webhook is successfully processed."""

    def __init__(
        self,
        aggregate_id: UUID,
        provider: str,
        event_type: str,
        payment_id: Optional[str],
        processed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.provider = provider
        self.event_type = event_type
        self.payment_id = payment_id
        self.processed_at = processed_at