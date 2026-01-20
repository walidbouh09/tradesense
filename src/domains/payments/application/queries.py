"""Payment application queries."""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID


@dataclass
class GetPaymentQuery:
    """Query to get a payment."""

    payment_id: UUID


@dataclass
class GetPaymentByIdempotencyKeyQuery:
    """Query to get a payment by idempotency key."""

    idempotency_key: str


@dataclass
class ListPaymentsQuery:
    """Query to list payments."""

    customer_id: Optional[UUID] = None
    status: Optional[str] = None
    provider: Optional[str] = None
    limit: int = 50
    offset: int = 0


@dataclass
class GetPaymentMethodQuery:
    """Query to get a payment method."""

    payment_method_id: str


@dataclass
class ListPaymentMethodsQuery:
    """Query to list payment methods."""

    customer_id: UUID


@dataclass
class GetDefaultPaymentMethodQuery:
    """Query to get default payment method."""

    customer_id: UUID


@dataclass
class ListTransactionsQuery:
    """Query to list transactions."""

    payment_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    type: Optional[str] = None
    status: Optional[str] = None
    limit: int = 50
    offset: int = 0