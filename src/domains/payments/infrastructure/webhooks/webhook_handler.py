"""Main webhook handler for secure, idempotent webhook processing."""

import json
import time
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.logging.audit_logger import AuditLogger
from shared.infrastructure.messaging.event_bus import EventBus

from ...domain.repositories import PaymentRepository
from ...infrastructure.repositories import SqlAlchemyTransactionRepository
from .repository import SqlAlchemyWebhookEventRepository
from .models import WebhookEventModel, WebhookProcessingLog
from .signature_verifier import WebhookSignatureVerifier
from .idempotency_service import WebhookIdempotencyService
from .event_processor import StripeEventProcessor


class WebhookHandler:
    """Secure webhook handler with idempotency and audit trail."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Any,  # Redis client
        event_bus: EventBus,
        audit_logger: AuditLogger,
        webhook_secrets: Dict[str, str],
    ):
        self.session = session
        self.redis_client = redis_client
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self.webhook_secrets = webhook_secrets

        # Initialize components
        self.signature_verifier = WebhookSignatureVerifier(audit_logger)
        self.idempotency_service = WebhookIdempotencyService(redis_client, audit_logger)

        # Initialize repositories
        self.webhook_repository = SqlAlchemyWebhookEventRepository(session)
        self.payment_repository = PaymentRepository(session)  # Should be injected properly
        self.transaction_repository = SqlAlchemyTransactionRepository(session)

        # Initialize event processors
        self.stripe_processor = StripeEventProcessor(
            payment_repository=self.payment_repository,
            transaction_repository=self.transaction_repository,
            event_bus=event_bus,
            audit_logger=audit_logger,
        )

    async def handle_webhook(
        self,
        provider: str,
        payload: bytes,
        signature: str,
        headers: Dict[str, str],
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook with full security and audit trail.

        Returns processing result.
        """
        start_time = time.time()
        processing_result = {
            "provider": provider,
            "processed": False,
            "signature_verified": False,
            "idempotent": False,
            "processing_time_seconds": 0,
            "error": None,
        }

        try:
            # Step 1: Verify signature
            is_valid, verification_reason, event_id = await self._verify_signature(
                provider, payload, signature, headers
            )

            if not is_valid:
                processing_result["error"] = verification_reason
                return processing_result

            processing_result["signature_verified"] = True

            # Step 2: Parse and store webhook event
            webhook_event = await self._store_webhook_event(
                provider, payload, signature, headers,
                source_ip, user_agent, event_id
            )

            # Step 3: Check idempotency
            is_duplicate, previous_result = await self.idempotency_service.check_and_store(
                provider, event_id or webhook_event.event_id, processing_result
            )

            if is_duplicate:
                processing_result["idempotent"] = True
                processing_result["processed"] = True
                processing_result["previous_result"] = previous_result
                return processing_result

            # Step 4: Process webhook event
            await self._process_webhook_event(webhook_event, provider)

            # Step 5: Mark as processed
            await self._mark_webhook_processed(webhook_event.id)

            processing_result["processed"] = True

        except Exception as e:
            processing_result["error"] = str(e)
            await self._log_processing_error(provider, event_id, str(e))

        finally:
            processing_result["processing_time_seconds"] = time.time() - start_time

        return processing_result

    async def _verify_signature(
        self,
        provider: str,
        payload: bytes,
        signature: str,
        headers: Dict[str, str],
    ) -> tuple[bool, str, Optional[str]]:
        """Verify webhook signature."""
        webhook_secret = self.webhook_secrets.get(provider)
        if not webhook_secret:
            return False, f"No webhook secret configured for provider: {provider}", None

        if provider == "stripe":
            return self.signature_verifier.verify_stripe_signature(
                payload, signature, webhook_secret
            )
        elif provider == "paypal":
            return self.signature_verifier.verify_paypal_signature(
                payload, headers, webhook_secret
            )
        else:
            return False, f"Unsupported provider: {provider}", None

    async def _store_webhook_event(
        self,
        provider: str,
        payload: bytes,
        signature: str,
        headers: Dict[str, str],
        source_ip: Optional[str],
        user_agent: Optional[str],
        event_id: Optional[str],
    ) -> WebhookEventModel:
        """Store webhook event for audit trail."""
        try:
            payload_str = payload.decode()
            payload_data = json.loads(payload_str)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload_str = payload.decode(errors='replace')
            payload_data = None

        # Extract event ID if not provided
        if not event_id:
            if payload_data and isinstance(payload_data, dict):
                event_id = payload_data.get("id")

        if not event_id:
            # Generate unique ID for audit purposes
            event_id = f"{provider}_{int(time.time())}_{hash(payload_str) % 1000000}"

        # Extract event type
        event_type = "unknown"
        if payload_data and isinstance(payload_data, dict):
            event_type = payload_data.get("type", payload_data.get("event_type", "unknown"))

        # Extract payment ID if available
        payment_id = None
        if payload_data and isinstance(payload_data, dict):
            payment_id = self._extract_payment_id(provider, payload_data)

        webhook_event = WebhookEventModel(
            id=f"{provider}_{event_id}",
            provider=provider,
            event_type=event_type,
            event_id=event_id,
            payment_id=payment_id,
            raw_payload=payload_str,
            parsed_data=payload_data,
            signature=signature,
            signature_verified=True,
            received_at=datetime.utcnow(),
            user_agent=user_agent,
            source_ip=source_ip,
            headers=headers,
        )

        self.session.add(webhook_event)
        await self.session.commit()

        return webhook_event

    async def _process_webhook_event(
        self,
        webhook_event: WebhookEventModel,
        provider: str,
    ) -> None:
        """Process webhook event based on provider."""
        if provider == "stripe":
            await self._process_stripe_event(webhook_event)
        elif provider == "paypal":
            await self._process_paypal_event(webhook_event)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def _process_stripe_event(self, webhook_event: WebhookEventModel) -> None:
        """Process Stripe webhook event."""
        if not webhook_event.parsed_data:
            raise ValueError("No parsed data for Stripe event")

        event_type = webhook_event.parsed_data.get("type")
        event_data = webhook_event.parsed_data.get("data", {})

        processing_result = await self.stripe_processor.process_event(
            event_type=event_type,
            event_data=event_data,
            webhook_id=webhook_event.id,
        )

        # Log processing steps
        await self._log_processing_steps(webhook_event.id, processing_result)

        # Update idempotency with final result
        await self.idempotency_service.check_and_store(
            "stripe", webhook_event.event_id, processing_result
        )

    async def _process_paypal_event(self, webhook_event: WebhookEventModel) -> None:
        """Process PayPal webhook event."""
        # PayPal event processing would be implemented here
        # For now, just log
        self.audit_logger.log_business_event(
            event_type="paypal_webhook_received",
            details={
                "webhook_id": webhook_event.id,
                "event_type": webhook_event.event_type,
            }
        )

    async def _mark_webhook_processed(self, webhook_id: str) -> None:
        """Mark webhook as processed."""
        await self.session.execute(
            update(WebhookEventModel)
            .where(WebhookEventModel.id == webhook_id)
            .values(
                processed=True,
                processed_at=datetime.utcnow(),
            )
        )
        await self.session.commit()

    async def _log_processing_error(self, provider: str, event_id: Optional[str], error: str) -> None:
        """Log webhook processing error."""
        self.audit_logger.log_business_event(
            event_type="webhook_processing_error",
            details={
                "provider": provider,
                "event_id": event_id,
                "error": error,
            },
            severity="ERROR"
        )

    async def _log_processing_steps(self, webhook_id: str, processing_result: Dict[str, Any]) -> None:
        """Log detailed processing steps."""
        for step in processing_result.get("domain_events_emitted", []):
            log_entry = WebhookProcessingLog(
                webhook_event_id=webhook_id,
                processing_step="domain_event_emitted",
                step_status="SUCCESS",
                message=f"Emitted {step['event_type']} for aggregate {step['aggregate_id']}",
                context_data=step,
            )
            self.session.add(log_entry)

        for error in processing_result.get("errors", []):
            log_entry = WebhookProcessingLog(
                webhook_event_id=webhook_id,
                processing_step="processing_error",
                step_status="ERROR",
                message=error,
            )
            self.session.add(log_entry)

        await self.session.commit()

    def _extract_payment_id(self, provider: str, payload_data: Dict[str, Any]) -> Optional[str]:
        """Extract payment ID from webhook payload."""
        if provider == "stripe":
            # Try different possible locations for payment intent ID
            obj = payload_data.get("data", {}).get("object", {})
            return (
                obj.get("id") or
                obj.get("payment_intent") or
                obj.get("charge")
            )
        elif provider == "paypal":
            # PayPal webhook structure
            resource = payload_data.get("resource", {})
            return resource.get("id")

        return None


# Missing imports that need to be added
from datetime import datetime
from sqlalchemy import update