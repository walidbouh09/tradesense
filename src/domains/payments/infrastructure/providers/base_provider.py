"""Base payment provider implementation."""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import httpx

from ...domain.services import PaymentProvider
from ...domain.value_objects import PaymentIntent, PaymentProviderResponse, WebhookEvent


class BasePaymentProvider(PaymentProvider, ABC):
    """Base class for payment provider implementations."""

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        base_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            headers=self._get_default_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retries: int = 0,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        if not self._client:
            raise RuntimeError("Provider not initialized. Use async context manager.")

        url = f"{self.base_url}{endpoint}"
        request_data = {"method": method, "url": url}

        if data:
            request_data["json" if method.upper() != "GET" else "params"] = data

        try:
            response = await self._client.request(**request_data)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)  # Exponential backoff
                return await self._make_request(method, endpoint, data, retries + 1)
            raise e
        except httpx.HTTPStatusError as e:
            # Don't retry on client errors (4xx)
            if 400 <= e.response.status_code < 500:
                raise e
            # Retry on server errors (5xx)
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)
                return await self._make_request(method, endpoint, data, retries + 1)
            raise e

    @abstractmethod
    async def create_payment_intent(
        self,
        amount: 'Money',
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
        amount: 'Money',
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
    ) -> 'PaymentMethod':
        """Create a payment method."""
        pass