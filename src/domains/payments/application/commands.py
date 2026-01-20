"""Payment application commands."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from uuid import UUID

from shared.utils.money import Money


@dataclass
class CreatePaymentCommand:
    """Command to create a new payment."""

    idempotency_key: str
    amount: Money
    customer_id: UUID
    payment_method_id: str
    description: str
    provider: str = "stripe"
    metadata: Optional[Dict[str, Any]] = None
    capture: bool = True


@dataclass
class ConfirmPaymentCommand:
    """Command to confirm a payment."""

    payment_id: UUID


@dataclass
class CancelPaymentCommand:
    """Command to cancel a payment."""

    payment_id: UUID
    reason: Optional[str] = None


@dataclass
class RefundPaymentCommand:
    """Command to refund a payment."""

    payment_id: UUID
    amount: Money
    reason: Optional[str] = None


@dataclass
class CreatePaymentMethodCommand:
    """Command to create a payment method."""

    customer_id: UUID
    type: str
    provider: str
    payment_method_data: Dict[str, Any]


@dataclass
class ProcessWebhookCommand:
    """Command to process a webhook from payment provider."""

    provider: str
    payload: bytes
    signature: str
    headers: Dict[str, str]


@dataclass
class GetPaymentCommand:
    """Command to get a payment."""

    payment_id: UUID


@dataclass
class ListPaymentsCommand:
    """Command to list payments for a customer."""

    customer_id: UUID
    limit: int = 50
    offset: int = 0


@dataclass
class GetPaymentMethodCommand:
    """Command to get a payment method."""

    payment_method_id: str


@dataclass
class ListPaymentMethodsCommand:
    """Command to list payment methods for a customer."""

    customer_id: UUID


@dataclass
class SetDefaultPaymentMethodCommand:
    """Command to set a payment method as default."""

    payment_method_id: str
    customer_id: UUID