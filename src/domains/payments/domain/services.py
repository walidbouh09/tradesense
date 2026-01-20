"""Payment domain services."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol
from uuid import UUID

from shared.utils.money import Money

from .entities import Payment, PaymentMethod
from .value_objects import PaymentIntent, PaymentProviderResponse, RefundRequest, WebhookEvent


class PaymentProvider(ABC):
    """Abstract payment provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def create_payment_intent(
        self,
        amount: Money,
        currency: str,
        customer_id: str,
        payment_method_id: str,
        metadata: Dict[str, Any],
    ) -> PaymentIntent:
        """Create a payment intent."""
        pass

    @abstractmethod
    async def confirm_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Confirm a payment intent."""
        pass

    @abstractmethod
    async def cancel_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Cancel a payment intent."""
        pass

    @abstractmethod
    async def refund_payment(
        self,
        payment_id: str,
        amount: Money,
        reason: Optional[str] = None,
    ) -> PaymentProviderResponse:
        """Refund a payment."""
        pass

    @abstractmethod
    async def get_payment_status(self, payment_id: str) -> str:
        """Get payment status from provider."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature."""
        pass

    @abstractmethod
    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse webhook event from provider."""
        pass

    @abstractmethod
    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_data: Dict[str, Any],
    ) -> PaymentMethod:
        """Create a payment method."""
        pass


class PaymentValidationService:
    """Service for payment validation business rules."""

    def validate_payment_amount(self, amount: Money) -> None:
        """Validate payment amount."""
        if amount.amount <= 0:
            raise ValueError("Payment amount must be positive")

        # Check currency support
        supported_currencies = {"USD", "EUR", "GBP"}
        if amount.currency not in supported_currencies:
            raise ValueError(f"Unsupported currency: {amount.currency}")

    def validate_payment_method(self, payment_method: PaymentMethod) -> None:
        """Validate payment method."""
        if payment_method.is_expired():
            raise ValueError("Payment method is expired")

        supported_types = {"card", "bank_account", "digital_wallet"}
        if payment_method.type not in supported_types:
            raise ValueError(f"Unsupported payment method type: {payment_method.type}")

    def validate_refund_amount(self, payment: Payment, refund_amount: Money) -> None:
        """Validate refund amount against original payment."""
        if refund_amount.currency != payment.amount.currency:
            raise ValueError("Refund currency must match payment currency")

        # Calculate total refunded amount
        total_refunded = sum(
            tx.amount.amount for tx in payment.transactions
            if tx.type == "refund" and tx.status == "succeeded"
        )

        if total_refunded + refund_amount.amount > payment.amount.amount:
            raise ValueError("Refund amount exceeds remaining payment amount")


class IdempotencyService:
    """Service for handling payment idempotency."""

    def __init__(self, repository: 'IdempotencyRepository') -> None:
        self.repository = repository

    async def check_and_store(
        self,
        key: str,
        operation: callable,
        ttl_seconds: int = 86400,  # 24 hours
    ) -> Any:
        """Check idempotency key and execute operation if not exists."""
        # Check if key exists
        existing = await self.repository.find_by_key(key)
        if existing:
            # Return cached result
            return existing.result

        # Execute operation
        result = await operation()

        # Store result
        from .value_objects import IdempotencyRecord
        import time

        record = IdempotencyRecord(
            key=key,
            result=result,
            expires_at=time.time() + ttl_seconds,
        )
        await self.repository.save(record)

        return result


class WebhookProcessingService:
    """Service for processing payment webhooks."""

    def __init__(self, providers: Dict[str, PaymentProvider]) -> None:
        self.providers = providers

    def validate_webhook(
        self,
        provider_name: str,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate webhook signature."""
        provider = self.providers.get(provider_name)
        if not provider:
            return False

        return provider.verify_webhook_signature(payload, signature)

    def parse_webhook_event(
        self,
        provider_name: str,
        payload: Dict[str, Any],
    ) -> WebhookEvent:
        """Parse webhook event."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        return provider.parse_webhook_event(payload)


# Type hints for repository dependencies
class IdempotencyRepository(Protocol):
    """Protocol for idempotency repository."""
    async def save(self, record: 'IdempotencyRecord') -> None: ...
    async def find_by_key(self, key: str) -> Optional['IdempotencyRecord']: ...