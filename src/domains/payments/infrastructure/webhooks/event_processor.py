"""Webhook event processor for Stripe → Domain Events mapping."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from shared.infrastructure.messaging.event_bus import EventBus
from shared.infrastructure.logging.audit_logger import AuditLogger

from ...domain.entities import Payment, Transaction, TransactionType, TransactionStatus
from ...domain.repositories import PaymentRepository
from ...infrastructure.repositories import SqlAlchemyTransactionRepository
from ...domain.events import (
    PaymentInitiated,
    PaymentProcessed,
    PaymentRefundInitiated,
)


class StripeEventProcessor:
    """Processes Stripe webhook events and maps to domain events."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        transaction_repository: SqlAlchemyTransactionRepository,
        event_bus: EventBus,
        audit_logger: AuditLogger,
    ):
        self.payment_repository = payment_repository
        self.transaction_repository = transaction_repository
        self.event_bus = event_bus
        self.audit_logger = audit_logger

        # Stripe event type mappings
        self.event_mappings = {
            "payment_intent.created": self._handle_payment_intent_created,
            "payment_intent.succeeded": self._handle_payment_intent_succeeded,
            "payment_intent.payment_failed": self._handle_payment_intent_failed,
            "payment_intent.canceled": self._handle_payment_intent_canceled,
            "payment_intent.requires_action": self._handle_payment_intent_requires_action,
            "charge.succeeded": self._handle_charge_succeeded,
            "charge.failed": self._handle_charge_failed,
            "charge.dispute.created": self._handle_charge_dispute_created,
            "refund.created": self._handle_refund_created,
            "refund.succeeded": self._handle_refund_succeeded,
            "refund.failed": self._handle_refund_failed,
        }

    async def process_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> Dict[str, Any]:
        """
        Process a Stripe webhook event.

        Returns processing result for idempotency.
        """
        processing_result = {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "processed_at": None,
            "domain_events_emitted": [],
            "errors": [],
        }

        try:
            # Get the appropriate handler
            handler = self.event_mappings.get(event_type)
            if not handler:
                processing_result["errors"].append(f"Unsupported event type: {event_type}")
                return processing_result

            # Process the event
            domain_events = await handler(event_data, webhook_id)

            # Emit domain events
            for event in domain_events:
                await self.event_bus.publish(event)
                processing_result["domain_events_emitted"].append({
                    "event_type": type(event).__name__,
                    "aggregate_id": str(event.aggregate_id),
                })

            processing_result["processed_at"] = str(domain_events[0].occurred_at) if domain_events else None

            # Audit successful processing
            self.audit_logger.log_business_event(
                event_type="webhook_processed",
                details={
                    "provider": "stripe",
                    "event_type": event_type,
                    "webhook_id": webhook_id,
                    "domain_events_count": len(domain_events),
                }
            )

        except Exception as e:
            error_msg = f"Event processing failed: {str(e)}"
            processing_result["errors"].append(error_msg)

            self.audit_logger.log_business_event(
                event_type="webhook_processing_error",
                details={
                    "provider": "stripe",
                    "event_type": event_type,
                    "webhook_id": webhook_id,
                    "error": error_msg,
                },
                severity="ERROR"
            )

        return processing_result

    async def _handle_payment_intent_created(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle payment_intent.created event."""
        payment_intent = event_data.get("object", {})
        payment_id = payment_intent.get("id")

        # Find associated payment by provider_payment_id
        payment = await self.payment_repository.find_by_provider_payment_id(payment_id)
        if not payment:
            # This might be a payment intent we don't have yet
            # Log for manual reconciliation
            self.audit_logger.log_business_event(
                event_type="payment_intent_created_unknown",
                details={"payment_intent_id": payment_id},
                severity="WARNING"
            )
            return []

        # Emit domain event
        event = PaymentInitiated(
            aggregate_id=payment.id,
            customer_id=payment.customer_id,
            amount=float(payment.amount.amount),
            currency=payment.amount.currency,
            payment_method_id=payment.payment_method.payment_method_id,
            provider="stripe",
            idempotency_key=payment.idempotency_key,
        )

        return [event]

    async def _handle_payment_intent_succeeded(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle payment_intent.succeeded event."""
        payment_intent = event_data.get("object", {})
        payment_id = payment_intent.get("id")

        # Find associated payment
        payment = await self.payment_repository.find_by_provider_payment_id(payment_id)
        if not payment:
            self.audit_logger.log_business_event(
                event_type="payment_intent_succeeded_unknown",
                details={"payment_intent_id": payment_id},
                severity="ERROR"
            )
            return []

        # Update payment status if not already updated
        if payment.status.value == "processing":
            from datetime import datetime
            # Extract fees from charges
            fees = self._extract_fees_from_payment_intent(payment_intent)
            payment.mark_as_succeeded(
                provider_payment_id=payment_id,
                fees=fees,
                processed_at=datetime.utcnow(),
            )
            await self.payment_repository.save(payment)

        # Emit domain event
        event = PaymentProcessed(
            aggregate_id=payment.id,
            customer_id=payment.customer_id,
            provider_payment_id=payment_id,
            status="succeeded",
            processed_at=datetime.utcnow(),
        )

        return [event]

    async def _handle_payment_intent_failed(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle payment_intent.payment_failed event."""
        payment_intent = event_data.get("object", {})
        payment_id = payment_intent.get("id")
        failure_reason = self._extract_failure_reason(payment_intent)

        # Find associated payment
        payment = await self.payment_repository.find_by_provider_payment_id(payment_id)
        if not payment:
            self.audit_logger.log_business_event(
                event_type="payment_intent_failed_unknown",
                details={"payment_intent_id": payment_id, "failure_reason": failure_reason},
                severity="ERROR"
            )
            return []

        # Update payment status
        payment.mark_as_failed(failure_reason)
        await self.payment_repository.save(payment)

        # Emit domain event
        from ...domain.events import PaymentFailed as PaymentFailedEvent
        event = PaymentFailedEvent(
            aggregate_id=payment.id,
            customer_id=payment.customer_id,
            amount=payment.amount,
            failure_reason=failure_reason,
            provider=payment.provider,
            metadata={"webhook_event_id": webhook_id},
        )

        return [event]

    async def _handle_payment_intent_canceled(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle payment_intent.canceled event."""
        payment_intent = event_data.get("object", {})
        payment_id = payment_intent.get("id")

        payment = await self.payment_repository.find_by_provider_payment_id(payment_id)
        if not payment:
            return []

        payment.cancel()
        await self.payment_repository.save(payment)

        from ...domain.events import PaymentCancelled as PaymentCancelledEvent
        event = PaymentCancelledEvent(
            aggregate_id=payment.id,
            customer_id=payment.customer_id,
            amount=payment.amount,
            cancelled_at=datetime.utcnow(),
        )

        return [event]

    async def _handle_payment_intent_requires_action(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle payment_intent.requires_action event."""
        # This indicates 3D Secure or other authentication required
        payment_intent = event_data.get("object", {})
        payment_id = payment_intent.get("id")

        payment = await self.payment_repository.find_by_provider_payment_id(payment_id)
        if not payment:
            return []

        # Log for monitoring - may need manual intervention
        self.audit_logger.log_business_event(
            event_type="payment_requires_action",
            details={
                "payment_id": str(payment.id),
                "payment_intent_id": payment_id,
            },
            severity="WARNING"
        )

        return []

    async def _handle_charge_succeeded(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle charge.succeeded event."""
        # This is a backup to payment_intent.succeeded
        # Usually we prefer payment_intent events
        charge = event_data.get("object", {})
        payment_intent_id = charge.get("payment_intent")

        if payment_intent_id:
            # Delegate to payment intent succeeded handler
            return await self._handle_payment_intent_succeeded(
                {"object": {"id": payment_intent_id}},
                webhook_id
            )

        return []

    async def _handle_charge_failed(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle charge.failed event."""
        charge = event_data.get("object", {})
        payment_intent_id = charge.get("payment_intent")
        failure_reason = self._extract_failure_reason_from_charge(charge)

        if payment_intent_id:
            return await self._handle_payment_intent_failed(
                {"object": {"id": payment_intent_id, "last_payment_error": {"message": failure_reason}}},
                webhook_id
            )

        return []

    async def _handle_charge_dispute_created(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle charge.dispute.created event."""
        dispute = event_data.get("object", {})
        charge_id = dispute.get("charge")

        # Find payment by charge ID (more complex lookup needed)
        # For now, log and alert
        self.audit_logger.log_business_event(
            event_type="payment_dispute_created",
            details={
                "charge_id": charge_id,
                "dispute_id": dispute.get("id"),
                "amount": dispute.get("amount"),
            },
            severity="CRITICAL"
        )

        return []

    async def _handle_refund_created(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle refund.created event."""
        refund = event_data.get("object", {})
        payment_intent_id = refund.get("payment_intent")
        refund_amount = refund.get("amount", 0) / 100  # Convert from cents

        if payment_intent_id:
            payment = await self.payment_repository.find_by_provider_payment_id(payment_intent_id)
            if payment:
                # Create refund transaction
                from shared.utils.money import Money
                transaction = Transaction(
                    transaction_id=uuid4(),
                    payment_id=payment.id,
                    type=TransactionType.REFUND,
                    amount=Money(refund_amount, payment.amount.currency),
                    status=TransactionStatus.PENDING,
                    provider_transaction_id=refund.get("id"),
                    metadata={"webhook_event_id": webhook_id},
                )
                await self.transaction_repository.save(transaction)

                # Emit domain event
                event = PaymentRefundInitiated(
                    aggregate_id=transaction.transaction_id,
                    payment_id=payment.id,
                    refund_amount=refund_amount,
                    currency=payment.amount.currency,
                    reason="Refund initiated via webhook",
                )

                return [event]

        return []

    async def _handle_refund_succeeded(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle refund.succeeded event."""
        refund = event_data.get("object", {})
        refund_id = refund.get("id")

        # Find transaction by provider_transaction_id
        # This requires a more complex lookup - simplified for demo
        self.audit_logger.log_business_event(
            event_type="refund_succeeded",
            details={"refund_id": refund_id},
        )

        return []

    async def _handle_refund_failed(
        self,
        event_data: Dict[str, Any],
        webhook_id: str,
    ) -> List[Any]:
        """Handle refund.failed event."""
        refund = event_data.get("object", {})
        refund_id = refund.get("id")
        failure_reason = refund.get("failure_reason", "Unknown")

        self.audit_logger.log_business_event(
            event_type="refund_failed",
            details={"refund_id": refund_id, "failure_reason": failure_reason},
            severity="ERROR"
        )

        return []

    def _extract_fees_from_payment_intent(self, payment_intent: Dict[str, Any]) -> 'Money':
        """Extract processing fees from payment intent."""
        from shared.utils.money import Money

        # Simplified fee calculation
        # In production, calculate based on Stripe's fee structure
        charges = payment_intent.get("charges", {}).get("data", [])
        if charges:
            charge = charges[0]
            # Stripe fee is approximately 2.9% + 30¢
            amount = charge.get("amount", 0) / 100  # Convert from cents
            fee = (amount * 0.029) + 0.30
            currency = charge.get("currency", "usd").upper()
            return Money(fee, currency)

        return Money(0, "USD")

    def _extract_failure_reason(self, payment_intent: Dict[str, Any]) -> str:
        """Extract failure reason from payment intent."""
        error = payment_intent.get("last_payment_error", {})
        return error.get("message", "Payment failed")

    def _extract_failure_reason_from_charge(self, charge: Dict[str, Any]) -> str:
        """Extract failure reason from charge."""
        error = charge.get("failure_message", "")
        if not error:
            error = charge.get("failure_code", "Unknown failure")
        return error