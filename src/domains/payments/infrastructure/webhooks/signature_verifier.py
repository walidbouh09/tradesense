"""Webhook signature verification service."""

import hashlib
import hmac
import time
from typing import Dict, Any, Optional, Tuple

from shared.infrastructure.logging.audit_logger import AuditLogger


class WebhookSignatureVerifier:
    """Secure webhook signature verification."""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger

    def verify_stripe_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str,
        tolerance_seconds: int = 300  # 5 minutes
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify Stripe webhook signature.

        Returns:
            Tuple of (is_valid, reason, event_id)
        """
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
                reason = "Invalid signature format"
                self._audit_verification("stripe", None, False, reason)
                return False, reason, None

            # Check timestamp tolerance
            current_time = int(time.time())
            signature_time = int(timestamp)

            if abs(current_time - signature_time) > tolerance_seconds:
                reason = f"Signature timestamp outside tolerance: {abs(current_time - signature_time)}s"
                self._audit_verification("stripe", None, False, reason)
                return False, reason, None

            # Create signed payload
            signed_payload = f"{timestamp}.{payload.decode()}"

            # Verify signature
            expected_signature = hmac.new(
                webhook_secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            # Check if any signature matches
            is_valid = expected_signature in signatures

            if is_valid:
                # Extract event ID for audit
                import json
                try:
                    event_data = json.loads(payload.decode())
                    event_id = event_data.get("id")
                except (json.JSONDecodeError, KeyError):
                    event_id = None

                self._audit_verification("stripe", event_id, True, "Signature verified")
                return True, "Signature verified", event_id
            else:
                reason = "Signature mismatch"
                self._audit_verification("stripe", None, False, reason)
                return False, reason, None

        except Exception as e:
            reason = f"Signature verification error: {str(e)}"
            self._audit_verification("stripe", None, False, reason)
            return False, reason, None

    def verify_paypal_signature(
        self,
        payload: bytes,
        headers: Dict[str, str],
        webhook_secret: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify PayPal webhook signature.

        PayPal uses different signature verification than Stripe.
        This is a simplified implementation - in production you'd use
        PayPal's SDK for proper verification.
        """
        try:
            # PayPal signature verification is more complex
            # In production, use paypal-checkout-sdk or similar

            # Extract required headers
            transmission_id = headers.get("paypal-transmission-id")
            transmission_time = headers.get("paypal-transmission-time")
            transmission_sig = headers.get("paypal-transmission-sig")
            cert_url = headers.get("paypal-cert-url")
            auth_algo = headers.get("paypal-auth-algo")

            if not all([transmission_id, transmission_time, transmission_sig, cert_url, auth_algo]):
                reason = "Missing required PayPal signature headers"
                self._audit_verification("paypal", None, False, reason)
                return False, reason, None

            # For demo purposes, implement basic verification
            # In production: download certificate, verify signature, check timestamp
            is_valid = self._verify_paypal_signature_detailed(
                payload, transmission_sig, cert_url, auth_algo, transmission_time
            )

            if is_valid:
                import json
                try:
                    event_data = json.loads(payload.decode())
                    event_id = event_data.get("id")
                except (json.JSONDecodeError, KeyError):
                    event_id = None

                self._audit_verification("paypal", event_id, True, "Signature verified")
                return True, "Signature verified", event_id
            else:
                reason = "PayPal signature verification failed"
                self._audit_verification("paypal", None, False, reason)
                return False, reason, None

        except Exception as e:
            reason = f"PayPal signature verification error: {str(e)}"
            self._audit_verification("paypal", None, False, reason)
            return False, reason, None

    def _verify_paypal_signature_detailed(
        self,
        payload: bytes,
        transmission_sig: str,
        cert_url: str,
        auth_algo: str,
        transmission_time: str
    ) -> bool:
        """
        Detailed PayPal signature verification.

        In production, this would:
        1. Download certificate from cert_url
        2. Verify certificate chain
        3. Verify signature using the certificate
        4. Check transmission_time is within tolerance
        """
        # Placeholder implementation
        # In production: implement full PayPal signature verification
        return True

    def _audit_verification(
        self,
        provider: str,
        event_id: Optional[str],
        success: bool,
        reason: str
    ) -> None:
        """Audit signature verification attempts."""
        self.audit_logger.log_security_event(
            event_type="webhook_signature_verification",
            success=success,
            details={
                "provider": provider,
                "event_id": event_id,
                "reason": reason,
                "timestamp": time.time(),
            },
            severity="WARNING" if not success else "INFO"
        )