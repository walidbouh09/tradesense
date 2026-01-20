"""Payment application handlers."""

from typing import List, Optional
from uuid import UUID, uuid4

from shared.infrastructure.messaging.event_bus import EventBus
from shared.utils.money import Money

from ..domain.entities import Payment, PaymentMethod, Transaction, TransactionType, TransactionStatus
from ..domain.repositories import PaymentRepository, PaymentMethodRepository, TransactionRepository
from ..domain.services import PaymentProvider, PaymentValidationService, IdempotencyService, WebhookProcessingService
from ..domain.value_objects import PaymentProviderResponse
from .commands import (
    CreatePaymentCommand,
    ConfirmPaymentCommand,
    CancelPaymentCommand,
    RefundPaymentCommand,
    CreatePaymentMethodCommand,
    ProcessWebhookCommand,
    GetPaymentCommand,
    ListPaymentsCommand,
    GetPaymentMethodCommand,
    ListPaymentMethodsCommand,
    SetDefaultPaymentMethodCommand,
)
from .queries import (
    GetPaymentQuery,
    GetPaymentByIdempotencyKeyQuery,
    ListPaymentsQuery,
    GetPaymentMethodQuery,
    ListPaymentMethodsQuery,
    GetDefaultPaymentMethodQuery,
    ListTransactionsQuery,
)


class CreatePaymentHandler:
    """Handler for creating payments."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        payment_method_repository: PaymentMethodRepository,
        idempotency_service: IdempotencyService,
        payment_validation_service: PaymentValidationService,
        payment_provider: PaymentProvider,
        event_bus: EventBus,
    ) -> None:
        self.payment_repository = payment_repository
        self.payment_method_repository = payment_method_repository
        self.idempotency_service = idempotency_service
        self.validation_service = payment_validation_service
        self.payment_provider = payment_provider
        self.event_bus = event_bus

    async def handle(self, command: CreatePaymentCommand) -> Payment:
        """Handle create payment command."""

        async def create_payment_operation():
            # Validate payment amount
            self.validation_service.validate_payment_amount(command.amount)

            # Get payment method
            payment_method = await self.payment_method_repository.find_by_id(
                command.payment_method_id
            )
            if not payment_method:
                raise ValueError(f"Payment method {command.payment_method_id} not found")

            # Validate payment method
            self.validation_service.validate_payment_method(payment_method)

            # Create payment entity
            payment_id = uuid4()
            payment = Payment(
                payment_id=payment_id,
                idempotency_key=command.idempotency_key,
                amount=command.amount,
                customer_id=command.customer_id,
                payment_method=payment_method,
                description=command.description,
                provider=command.provider,
                metadata=command.metadata,
            )

            # Create payment intent with provider
            intent = await self.payment_provider.create_payment_intent(
                amount=command.amount,
                currency=command.amount.currency,
                customer_id=str(command.customer_id),
                payment_method_id=command.payment_method_id,
                metadata=command.metadata or {},
            )

            # If capture is requested, confirm the payment
            if command.capture:
                payment.mark_as_processing()
                response = await self.payment_provider.confirm_payment(intent.intent_id)

                if response.is_success():
                    from datetime import datetime
                    payment.mark_as_succeeded(
                        provider_payment_id=response.provider_payment_id,
                        fees=Money(response.fees or 0, command.amount.currency),
                        processed_at=datetime.utcnow(),
                    )
                else:
                    payment.mark_as_failed(response.error_message or "Payment failed")

            # Save payment
            await self.payment_repository.save(payment)

            # Publish domain events
            for event in payment.domain_events:
                await self.event_bus.publish(event)

            return payment

        # Use idempotency service to prevent duplicates
        return await self.idempotency_service.check_and_store(
            key=f"payment:{command.idempotency_key}",
            operation=create_payment_operation,
        )


class ConfirmPaymentHandler:
    """Handler for confirming payments."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        payment_provider: PaymentProvider,
        event_bus: EventBus,
    ) -> None:
        self.payment_repository = payment_repository
        self.payment_provider = payment_provider
        self.event_bus = event_bus

    async def handle(self, command: ConfirmPaymentCommand) -> None:
        """Handle confirm payment command."""
        payment = await self.payment_repository.find_by_id(command.payment_id)
        if not payment:
            raise ValueError(f"Payment {command.payment_id} not found")

        if payment.status.value != "pending":
            raise ValueError(f"Payment {command.payment_id} is not in pending state")

        # Confirm with provider
        response = await self.payment_provider.confirm_payment(
            payment.provider_payment_id or ""
        )

        if response.is_success():
            from datetime import datetime
            payment.mark_as_succeeded(
                provider_payment_id=response.provider_payment_id,
                fees=Money(response.fees or 0, payment.amount.currency),
                processed_at=datetime.utcnow(),
            )
        else:
            payment.mark_as_failed(response.error_message or "Payment confirmation failed")

        await self.payment_repository.save(payment)

        # Publish domain events
        for event in payment.domain_events:
            await self.event_bus.publish(event)


class CancelPaymentHandler:
    """Handler for cancelling payments."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        payment_provider: PaymentProvider,
        event_bus: EventBus,
    ) -> None:
        self.payment_repository = payment_repository
        self.payment_provider = payment_provider
        self.event_bus = event_bus

    async def handle(self, command: CancelPaymentCommand) -> None:
        """Handle cancel payment command."""
        payment = await self.payment_repository.find_by_id(command.payment_id)
        if not payment:
            raise ValueError(f"Payment {command.payment_id} not found")

        # Cancel with provider if it has a provider payment ID
        if payment.provider_payment_id:
            await self.payment_provider.cancel_payment(payment.provider_payment_id)

        # Cancel locally
        payment.cancel()
        await self.payment_repository.save(payment)

        # Publish domain events
        for event in payment.domain_events:
            await self.event_bus.publish(event)


class RefundPaymentHandler:
    """Handler for refunding payments."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        transaction_repository: TransactionRepository,
        payment_provider: PaymentProvider,
        validation_service: PaymentValidationService,
        event_bus: EventBus,
    ) -> None:
        self.payment_repository = payment_repository
        self.transaction_repository = transaction_repository
        self.payment_provider = payment_provider
        self.validation_service = validation_service
        self.event_bus = event_bus

    async def handle(self, command: RefundPaymentCommand) -> Transaction:
        """Handle refund payment command."""
        payment = await self.payment_repository.find_by_id(command.payment_id)
        if not payment:
            raise ValueError(f"Payment {command.payment_id} not found")

        # Validate refund amount
        self.validation_service.validate_refund_amount(payment, command.amount)

        # Create refund transaction
        transaction = Transaction(
            transaction_id=uuid4(),
            payment_id=command.payment_id,
            type=TransactionType.REFUND,
            amount=command.amount,
            status=TransactionStatus.PENDING,
            metadata={"reason": command.reason} if command.reason else {},
        )

        # Process refund with provider
        response = await self.payment_provider.refund_payment(
            payment.provider_payment_id or "",
            command.amount,
            command.reason,
        )

        if response.is_success():
            transaction.status = TransactionStatus.SUCCEEDED
            transaction.provider_transaction_id = response.provider_payment_id
            transaction.processed_at = datetime.utcnow()

            # Add transaction to payment
            payment.add_transaction(transaction)
            await self.payment_repository.save(payment)

        else:
            transaction.status = TransactionStatus.FAILED

        await self.transaction_repository.save(transaction)

        # Publish events
        if transaction.status == TransactionStatus.SUCCEEDED:
            from ..domain.events import PaymentRefundInitiated
            event = PaymentRefundInitiated(
                aggregate_id=transaction.transaction_id,
                payment_id=command.payment_id,
                refund_amount=command.amount.amount,
                currency=command.amount.currency,
                reason=command.reason or "Customer refund",
            )
            await self.event_bus.publish(event)

        return transaction


class CreatePaymentMethodHandler:
    """Handler for creating payment methods."""

    def __init__(
        self,
        payment_method_repository: PaymentMethodRepository,
        payment_provider: PaymentProvider,
        event_bus: EventBus,
    ) -> None:
        self.payment_method_repository = payment_method_repository
        self.payment_provider = payment_provider
        self.event_bus = event_bus

    async def handle(self, command: CreatePaymentMethodCommand) -> PaymentMethod:
        """Handle create payment method command."""
        # Create payment method with provider
        payment_method = await self.payment_provider.create_payment_method(
            customer_id=str(command.customer_id),
            payment_method_data=command.payment_method_data,
        )

        await self.payment_method_repository.save(payment_method)

        # Publish domain event
        from ..domain.events import PaymentMethodCreated
        event = PaymentMethodCreated(
            aggregate_id=uuid4(),  # Use UUID for aggregate ID
            customer_id=command.customer_id,
            payment_method_id=payment_method.payment_method_id,
            type=payment_method.type,
            provider=payment_method.provider,
        )
        await self.event_bus.publish(event)

        return payment_method


class ProcessWebhookHandler:
    """Handler for processing webhooks."""

    def __init__(
        self,
        webhook_service: WebhookProcessingService,
        payment_repository: PaymentRepository,
        event_bus: EventBus,
    ) -> None:
        self.webhook_service = webhook_service
        self.payment_repository = payment_repository
        self.event_bus = event_bus

    async def handle(self, command: ProcessWebhookCommand) -> None:
        """Handle process webhook command."""
        # Validate webhook signature
        if not self.webhook_service.validate_webhook(
            command.provider,
            command.payload,
            command.signature,
        ):
            raise ValueError("Invalid webhook signature")

        # Parse webhook event
        import json
        payload_dict = json.loads(command.payload.decode())
        webhook_event = self.webhook_service.parse_webhook_event(
            command.provider,
            payload_dict,
        )

        # Process webhook based on event type
        if webhook_event.event_type == "payment.succeeded":
            await self._handle_payment_succeeded(webhook_event)
        elif webhook_event.event_type == "payment.failed":
            await self._handle_payment_failed(webhook_event)
        elif webhook_event.event_type == "refund.succeeded":
            await self._handle_refund_succeeded(webhook_event)

        # Publish webhook processed event
        from ..domain.events import WebhookProcessed
        from datetime import datetime
        event = WebhookProcessed(
            aggregate_id=uuid4(),
            provider=command.provider,
            event_type=webhook_event.event_type,
            payment_id=webhook_event.payment_id,
            processed_at=datetime.utcnow(),
        )
        await self.event_bus.publish(event)

    async def _handle_payment_succeeded(self, webhook_event):
        """Handle payment succeeded webhook."""
        if webhook_event.payment_id:
            payment = await self.payment_repository.find_by_provider_payment_id(
                webhook_event.payment_id
            )
            if payment and payment.status.value == "processing":
                # Update payment status
                from datetime import datetime
                payment.mark_as_succeeded(
                    provider_payment_id=webhook_event.payment_id,
                    fees=Money(0, payment.amount.currency),  # Fees would come from webhook data
                    processed_at=datetime.utcnow(),
                )
                await self.payment_repository.save(payment)

    async def _handle_payment_failed(self, webhook_event):
        """Handle payment failed webhook."""
        if webhook_event.payment_id:
            payment = await self.payment_repository.find_by_provider_payment_id(
                webhook_event.payment_id
            )
            if payment and payment.status.value == "processing":
                payment.mark_as_failed("Payment failed via webhook")
                await self.payment_repository.save(payment)

    async def _handle_refund_succeeded(self, webhook_event):
        """Handle refund succeeded webhook."""
        # Refund processing would be implemented here
        pass


# Query Handlers
class GetPaymentHandler:
    """Handler for getting a payment."""

    def __init__(self, payment_repository: PaymentRepository) -> None:
        self.payment_repository = payment_repository

    async def handle(self, query: GetPaymentQuery) -> Optional[Payment]:
        """Handle get payment query."""
        return await self.payment_repository.find_by_id(query.payment_id)


class ListPaymentsHandler:
    """Handler for listing payments."""

    def __init__(self, payment_repository: PaymentRepository) -> None:
        self.payment_repository = payment_repository

    async def handle(self, query: ListPaymentsQuery) -> List[Payment]:
        """Handle list payments query."""
        # For now, just return payments by customer
        # In a real implementation, you'd add filtering by status, provider, etc.
        if query.customer_id:
            return await self.payment_repository.find_by_customer_id(
                query.customer_id,
                query.limit,
                query.offset,
            )
        return []


class GetPaymentMethodHandler:
    """Handler for getting a payment method."""

    def __init__(self, payment_method_repository: PaymentMethodRepository) -> None:
        self.payment_method_repository = payment_method_repository

    async def handle(self, query: GetPaymentMethodQuery) -> Optional[PaymentMethod]:
        """Handle get payment method query."""
        return await self.payment_method_repository.find_by_id(query.payment_method_id)


class ListPaymentMethodsHandler:
    """Handler for listing payment methods."""

    def __init__(self, payment_method_repository: PaymentMethodRepository) -> None:
        self.payment_method_repository = payment_method_repository

    async def handle(self, query: ListPaymentMethodsQuery) -> List[PaymentMethod]:
        """Handle list payment methods query."""
        return await self.payment_method_repository.find_by_customer_id(query.customer_id)