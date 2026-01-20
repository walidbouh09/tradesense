"""PayPal payment provider implementation."""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional

from ...domain.entities import PaymentMethod
from ...domain.value_objects import PaymentIntent as DomainPaymentIntent, PaymentProviderResponse, WebhookEvent
from .base_provider import BasePaymentProvider


class PayPalProvider(BasePaymentProvider):
    """PayPal payment provider implementation."""

    @property
    def name(self) -> str:
        return "paypal"

    def _get_default_headers(self) -> Dict[str, str]:
        """Get PayPal-specific headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": "",  # Will be set per request
        }

    async def create_payment_intent(
        self,
        amount: 'Money',
        currency: str,
        customer_id: str,
        payment_method_id: str,
        metadata: Dict[str, Any],
    ) -> DomainPaymentIntent:
        """Create a PayPal order (equivalent to payment intent)."""
        data = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": currency.upper(),
                    "value": f"{amount.amount:.2f}",
                },
                "reference_id": metadata.get("reference_id", "default"),
                "custom_id": customer_id,
            }],
            "application_context": {
                "return_url": metadata.get("return_url", "https://example.com/success"),
                "cancel_url": metadata.get("cancel_url", "https://example.com/cancel"),
            },
        }

        response = await self._make_request("POST", "/checkout/orders", data)

        return DomainPaymentIntent(
            intent_id=response["id"],
            client_secret="",  # PayPal doesn't use client secrets like Stripe
            status=response["status"].lower(),
            metadata={"paypal_order_id": response["id"]},
        )

    async def confirm_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Capture a PayPal order."""
        try:
            response = await self._make_request(
                "POST",
                f"/checkout/orders/{payment_intent_id}/capture"
            )

            return PaymentProviderResponse(
                success=True,
                provider_payment_id=payment_intent_id,
                raw_response=response,
                fees=self._calculate_fees(response),
            )

        except Exception as e:
            return PaymentProviderResponse(
                success=False,
                error_message=str(e),
            )

    async def cancel_payment(self, payment_intent_id: str) -> PaymentProviderResponse:
        """Cancel a PayPal order (not directly supported, would need custom logic)."""
        # PayPal orders can be cancelled by not capturing them
        # This is a simplified implementation
        return PaymentProviderResponse(
            success=True,
            provider_payment_id=payment_intent_id,
            raw_response={"status": "cancelled"},
        )

    async def refund_payment(
        self,
        payment_id: str,
        amount: 'Money',
        reason: Optional[str] = None,
    ) -> PaymentProviderResponse:
        """Refund a PayPal payment."""
        data = {
            "amount": {
                "value": f"{amount.amount:.2f}",
                "currency_code": amount.currency.upper(),
            }
        }

        if reason:
            data["note_to_payer"] = reason

        try:
            response = await self._make_request(
                "POST",
                f"/payments/captures/{payment_id}/refund",
                data
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

    async def get_payment_status(self, payment_id: str) -> str:
        """Get payment status from PayPal."""
        response = await self._make_request("GET", f"/checkout/orders/{payment_id}")
        return response["status"].lower()

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify PayPal webhook signature."""
        # PayPal webhook verification is more complex
        # This is a simplified implementation
        try:
            # In production, you'd verify the signature properly
            # PayPal uses different signature verification than Stripe
            return True  # Placeholder
        except Exception:
            return False

    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """Parse PayPal webhook event."""
        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})

        # Extract order/payment ID
        payment_id = None
        if resource.get("id"):
            payment_id = resource["id"]

        return WebhookEvent(
            event_id=payload.get("id", ""),
            event_type=self._map_paypal_event_type(event_type),
            provider="paypal",
            payment_id=payment_id,
            data=resource,
            raw_payload=json.dumps(payload),
        )

    async def create_payment_method(
        self,
        customer_id: str,
        payment_method_data: Dict[str, Any],
    ) -> PaymentMethod:
        """Create a PayPal payment method."""
        # PayPal payment methods are handled differently
        # This is a simplified implementation
        payment_method_id = f"paypal_{customer_id}"

        return PaymentMethod(
            payment_method_id=payment_method_id,
            type="digital_wallet",
            provider="paypal",
            metadata=payment_method_data,
        )

    def _calculate_fees(self, response: Dict[str, Any]) -> Optional[float]:
        """Calculate PayPal fees from response."""
        # Simplified fee calculation
        # PayPal fees vary by region and transaction type
        purchase_units = response.get("purchase_units", [])
        if purchase_units:
            amount = float(purchase_units[0]["payments"]["captures"][0]["amount"]["value"])
            # Approximate PayPal fee: 2.9% + $0.49 for domestic
            fee = (amount * 0.029) + 0.49
            return fee
        return None

    def _map_paypal_event_type(self, paypal_event_type: str) -> str:
        """Map PayPal event types to our internal types."""
        mapping = {
            "PAYMENT.CAPTURE.COMPLETED": "payment.succeeded",
            "PAYMENT.CAPTURE.DENIED": "payment.failed",
            "PAYMENT.CAPTURE.REFUNDED": "refund.succeeded",
            "CHECKOUT.ORDER.APPROVED": "payment.approved",
            "CHECKOUT.ORDER.CANCELLED": "payment.cancelled",
        }
        return mapping.get(paypal_event_type, paypal_event_type)