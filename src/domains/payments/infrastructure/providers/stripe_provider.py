"""Stripe payment provider implementation."""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional

from ...domain.entities import PaymentMethod
from ...domain.value_objects import PaymentIntent as DomainPaymentIntent, PaymentProviderResponse, WebhookEvent
from ...domain.services import PaymentProvider
from .base_provider import BasePaymentProvider


class StripeProvider(BasePaymentProvider):
    """Stripe payment provider implementation."""

    @property
    def name(self) -> str:
        return "stripe"

    def _get_default_headers(self) -> Dict[str, str]:
        """Get Stripe-specific headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Stripe-Version": "2023-10-16",  # Use latest API version
        }

    async def create_payment_intent(
        self,
        amount: 'Money',
        currency: str,
        customer_id: str,
        payment_method_id: str,
        metadata: Dict[str, Any],
    ) -> DomainPaymentIntent:
        """Create a Stripe payment intent."""
        # Convert amount to cents (Stripe uses smallest currency unit)
        amount_cents = int(amount.amount * 100)

        data = {
            "amount": amount_cents,
            "currency": currency.lower(),
            "customer": customer_id,
            "payment_method": payment_method_id,
            "confirmation_method": "manual",  # We'll confirm later
            "capture_method": "automatic",  # Capture immediately when confirming
            "metadata": metadata,
        }

        response = await self._make_request("POST", "/payment_intents", data)

        return DomainPaymentIntent(
            intent_id=response["id"],
            client_secret=response["client_secret"],
            status=response["status"],
            metadata=response.get("metadata", {}),
        )

    async def confirm_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Confirm a Stripe payment intent."""
        data = {
            "payment_method_options": {
                "card": {
                    "request_three_d_secure": "automatic",
                }
            }
        }

        try:
            response = await self._make_request(
                "POST",
                f"/payment_intents/{payment_intent_id}/confirm",
                data
            )

            return PaymentProviderResponse(
                success=True,
                provider_payment_id=response["id"],
                raw_response=response,
                fees=self._calculate_fees(response),
            )

        except Exception as e:
            return PaymentProviderResponse(
                success=False,
                error_message=str(e),
            )

    async def cancel_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Cancel a Stripe payment intent."""
        try:
            response = await self._make_request(
                "POST",
                f"/payment_intents/{payment_intent_id}/cancel"
            )

            return PaymentProviderResponse(
                success=True,
                provider_payment_id=response["id"],
                raw_response=response,
            )

        except Exception as e:
            return PaymentProviderResponse(
                success=False,
                error_message=str(e),
            )

    async def refund_payment(
        self,
        payment_id: str,
        amount: 'Money',
        reason: Optional[str] = None,
    ) -> PaymentProviderResponse:
        """Refund a Stripe payment."""
        # Convert amount to cents
        amount_cents = int(amount.amount * 100)

        data = {
            "payment_intent": payment_id,
            "amount": amount_cents,
        }

        if reason:
            data["reason"] = self._map_refund_reason(reason)

        try:
            response = await self._make_request("POST", "/refunds", data)

            return PaymentProviderResponse(
                success=True,
                provider_payment_id=response["id"],
                raw_response=response,
            )

        except Exception as e:
            return PaymentProviderResponse(
                success=False,
                error_message=str(e),
            )

    async def get_payment_status(self, payment_id: str) -> str:
        """Get payment status from Stripe."""
        response = await self._make_request("GET", f"/payment_intents/{payment_id}")
        return response["status"]

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature."""
        try:
            # Parse signature header
            # Format: t=1492774577,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77
            timestamp = None
            signatures = []

            for part in signature.split(","):
                key, value = part.split("=", 1)
                if key == "t":
                    timestamp = value
                elif key.startswith("v"):
                    signatures.append(value)

            if not timestamp or not signatures:
                return False

            # Create signed payload
            signed_payload = f"{timestamp}.{payload.decode()}"

            # Verify signature
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            # Check if any signature matches
            return expected_signature in signatures

        except Exception:
            return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse Stripe webhook event."""
        event_type = payload.get("type", "")
        event_data = payload.get("data", {})

        # Extract payment intent ID if available
        payment_id = None
        if "object" in event_data:
            obj = event_data["object"]
            if obj.get("object") == "payment_intent":
                payment_id = obj.get("id")

        return WebhookEvent(
            event_id=payload.get("id", ""),
            event_type=self._map_stripe_event_type(event_type),
            provider="stripe",
            payment_id=payment_id,
            data=event_data,
            raw_payload=json.dumps(payload),
        )

    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_data: Dict[str, Any],
    ) -> PaymentMethod:
        """Create a Stripe payment method."""
        # First create the payment method
        response = await self._make_request("POST", "/payment_methods", payment_method_data)

        payment_method_id = response["id"]

        # Attach to customer if customer_id provided
        if customer_id:
            await self._make_request(
                "POST",
                f"/payment_methods/{payment_method_id}/attach",
                {"customer": customer_id}
            )

        # Determine expiry date for cards
        expires_at = None
        if response.get("card"):
            card = response["card"]
            expires_at = f"{card['exp_year']}-{card['exp_month']:02d}-01"

        return PaymentMethod(
            payment_method_id=payment_method_id,
            type=self._map_payment_method_type(response),
            provider="stripe",
            metadata=response,
            expires_at=expires_at,
        )

    def _calculate_fees(self, response: Dict[str, Any]) -> Optional[float]:
        """Calculate Stripe fees from response."""
        # This is a simplified fee calculation
        # In production, you'd want more sophisticated fee calculation
        charges = response.get("charges", {}).get("data", [])
        if charges:
            charge = charges[0]
            # Stripe fee is typically 2.9% + 30¢
            amount = charge["amount"] / 100  # Convert from cents
            fee = (amount * 0.029) + 0.30
            return fee
        return None

    def _map_refund_reason(self, reason: str) -> str:
        """Map our refund reasons to Stripe's reasons."""
        mapping = {
            "customer_request": "requested_by_customer",
            "duplicate": "duplicate",
            "fraudulent": "fraudulent",
        }
        return mapping.get(reason, "requested_by_customer")

    def _map_stripe_event_type(self, stripe_event_type: str) -> str:
        """Map Stripe event types to our internal types."""
        mapping = {
            "payment_intent.succeeded": "payment.succeeded",
            "payment_intent.payment_failed": "payment.failed",
            "payment_intent.canceled": "payment.cancelled",
            "charge.dispute.created": "payment.disputed",
            "refund.created": "refund.created",
            "refund.succeeded": "refund.succeeded",
            "refund.failed": "refund.failed",
        }
        return mapping.get(stripe_event_type, stripe_event_type)

    def _map_payment_method_type(self, response: Dict[str, Any]) -> str:
        """Map Stripe payment method to our internal types."""
        if response.get("card"):
            return "card"
        elif response.get("bank_account"):
            return "bank_account"
        else:
            return response.get("type", "unknown")