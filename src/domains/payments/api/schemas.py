"""Payment API Pydantic schemas."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, validator

from shared.utils.money import Money


class MoneySchema(BaseModel):
    """Money schema."""

    amount: str = Field(..., description="Amount as string to preserve precision")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")

    @validator('currency')
    def validate_currency(cls, v):
        supported = {"USD", "EUR", "GBP"}
        if v not in supported:
            raise ValueError(f"Unsupported currency: {v}")
        return v

    def to_money(self) -> Money:
        """Convert to Money value object."""
        return Money(float(self.amount), self.currency)


class AddressSchema(BaseModel):
    """Address schema."""

    street: str
    city: str
    state: str
    postal_code: str
    country: str
    street2: Optional[str] = None


class PaymentMethodSchema(BaseModel):
    """Payment method schema."""

    id: str = Field(..., description="Payment method ID from provider")
    type: str = Field(..., description="Payment method type (card, bank_account, etc.)")
    provider: str = Field(..., description="Payment provider (stripe, paypal, etc.)")
    is_default: bool = False
    metadata: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class CreatePaymentRequest(BaseModel):
    """Request schema for creating a payment."""

    idempotency_key: str = Field(..., description="Unique key to prevent duplicate payments")
    amount: MoneySchema
    customer_id: UUID
    payment_method_id: str
    description: str
    provider: str = "stripe"
    metadata: Optional[Dict[str, Any]] = None
    capture: bool = True  # Whether to capture immediately


class PaymentResponse(BaseModel):
    """Response schema for payment operations."""

    id: UUID
    idempotency_key: str
    amount: MoneySchema
    fees: MoneySchema
    net_amount: MoneySchema
    customer_id: UUID
    payment_method: PaymentMethodSchema
    status: str
    provider: str
    provider_payment_id: Optional[str] = None
    description: str
    metadata: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ListPaymentsResponse(BaseModel):
    """Response schema for listing payments."""

    payments: List[PaymentResponse]
    total_count: int
    limit: int
    offset: int


class ConfirmPaymentRequest(BaseModel):
    """Request schema for confirming a payment."""

    pass  # No additional data needed


class CancelPaymentRequest(BaseModel):
    """Request schema for cancelling a payment."""

    reason: Optional[str] = None


class RefundPaymentRequest(BaseModel):
    """Request schema for refunding a payment."""

    amount: MoneySchema
    reason: Optional[str] = None


class CreatePaymentMethodRequest(BaseModel):
    """Request schema for creating a payment method."""

    type: str
    provider: str = "stripe"
    payment_method_data: Dict[str, Any]  # Provider-specific data


class ListPaymentMethodsResponse(BaseModel):
    """Response schema for listing payment methods."""

    payment_methods: List[PaymentMethodSchema]


class SetDefaultPaymentMethodRequest(BaseModel):
    """Request schema for setting default payment method."""

    pass  # No additional data needed


class TransactionSchema(BaseModel):
    """Transaction schema."""

    id: UUID
    payment_id: UUID
    type: str
    amount: MoneySchema
    status: str
    provider_transaction_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


class ListTransactionsResponse(BaseModel):
    """Response schema for listing transactions."""

    transactions: List[TransactionSchema]
    total_count: int
    limit: int
    offset: int


class WebhookEventSchema(BaseModel):
    """Webhook event schema."""

    provider: str
    event_type: str
    payment_id: Optional[str] = None
    data: Dict[str, Any]
    received_at: datetime
    processed: bool = False


class WebhookResponse(BaseModel):
    """Response for webhook processing."""

    status: str = "ok"
    message: str = "Webhook processed successfully"


class PaymentStatusUpdateSchema(BaseModel):
    """Schema for payment status updates."""

    status: str
    provider_payment_id: Optional[str] = None
    failure_reason: Optional[str] = None
    processed_at: Optional[datetime] = None


# Error schemas
class ErrorDetail(BaseModel):
    """Error detail schema."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    request_id: Optional[str] = None