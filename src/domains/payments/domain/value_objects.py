"""Payment domain value objects."""

from typing import Dict, Any, Optional
from shared.kernel.value_object import ValueObject


class PaymentIntent(ValueObject):
    """Payment intent value object."""

    def __init__(
        self,
        intent_id: str,
        client_secret: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.intent_id = intent_id
        self.client_secret = client_secret
        self.status = status
        self.metadata = metadata or {}

    def is_succeeded(self) -> bool:
        return self.status == "succeeded"

    def is_failed(self) -> bool:
        return self.status == "failed"

    def is_processing(self) -> bool:
        return self.status == "processing"


class PaymentProviderResponse(ValueObject):
    """Payment provider response value object."""

    def __init__(
        self,
        success: bool,
        provider_payment_id: Optional[str] = None,
        error_message: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
        fees: Optional[float] = None,
    ) -> None:
        self.success = success
        self.provider_payment_id = provider_payment_id
        self.error_message = error_message
        self.raw_response = raw_response or {}
        self.fees = fees

    def is_success(self) -> bool:
        return self.success


class RefundRequest(ValueObject):
    """Refund request value object."""

    def __init__(
        self,
        amount: float,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.amount = amount
        self.reason = reason
        self.metadata = metadata or {}


class ProviderConfiguration(ValueObject):
    """Payment provider configuration value object."""

    def __init__(
        self,
        provider_name: str,
        api_key: str,
        webhook_secret: str,
        base_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries


class WebhookEvent(ValueObject):
    """Webhook event value object."""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        provider: str,
        payment_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        raw_payload: Optional[str] = None,
    ) -> None:
        self.event_id = event_id
        self.event_type = event_type
        self.provider = provider
        self.payment_id = payment_id
        self.data = data or {}
        self.raw_payload = raw_payload


class IdempotencyRecord(ValueObject):
    """Idempotency record value object."""

    def __init__(
        self,
        key: str,
        result: Dict[str, Any],
        expires_at: float,
    ) -> None:
        self.key = key
        self.result = result
        self.expires_at = expires_at