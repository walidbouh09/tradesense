"""Payment application services."""

from typing import Dict, Any, List, Optional
from uuid import UUID

from shared.infrastructure.messaging.event_bus import EventBus
from shared.utils.money import Money

from ..domain.entities import Payment, PaymentMethod
from ..domain.repositories import PaymentRepository, PaymentMethodRepository, TransactionRepository
from ..domain.services import PaymentProvider, PaymentValidationService, IdempotencyService, WebhookProcessingService


class PaymentApplicationService:
    """Application service for payment operations."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        payment_method_repository: PaymentMethodRepository,
        transaction_repository: TransactionRepository,
        idempotency_service: IdempotencyService,
        validation_service: PaymentValidationService,
        webhook_service: WebhookProcessingService,
        providers: Dict[str, PaymentProvider],
        event_bus: EventBus,
    ) -> None:
        self.payment_repository = payment_repository
        self.payment_method_repository = payment_method_repository
        self.transaction_repository = transaction_repository
        self.idempotency_service = idempotency_service
        self.validation_service = validation_service
        self.webhook_service = webhook_service
        self.providers = providers
        self.event_bus = event_bus

    async def create_payment(
        self,
        idempotency_key: str,
        amount: Money,
        customer_id: UUID,
        payment_method_id: str,
        description: str,
        provider: str = "stripe",
        metadata: Optional[Dict[str, Any]] = None,
        capture: bool = True,
    ) -> Payment:
        """Create a new payment."""
        from .handlers import CreatePaymentHandler

        handler = CreatePaymentHandler(
            payment_repository=self.payment_repository,
            payment_method_repository=self.payment_method_repository,
            idempotency_service=self.idempotency_service,
            payment_validation_service=self.validation_service,
            payment_provider=self.providers[provider],
            event_bus=self.event_bus,
        )

        from .commands import CreatePaymentCommand
        command = CreatePaymentCommand(
            idempotency_key=idempotency_key,
            amount=amount,
            customer_id=customer_id,
            payment_method_id=payment_method_id,
            description=description,
            provider=provider,
            metadata=metadata,
            capture=capture,
        )

        return await handler.handle(command)

    async def get_payment(self, payment_id: UUID) -> Optional[Payment]:
        """Get a payment by ID."""
        from .handlers import GetPaymentHandler

        handler = GetPaymentHandler(self.payment_repository)
        from .queries import GetPaymentQuery
        query = GetPaymentQuery(payment_id=payment_id)

        return await handler.handle(query)

    async def list_payments(
        self,
        customer_id: Optional[UUID] = None,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Payment]:
        """List payments with optional filters."""
        from .handlers import ListPaymentsHandler

        handler = ListPaymentsHandler(self.payment_repository)
        from .queries import ListPaymentsQuery
        query = ListPaymentsQuery(
            customer_id=customer_id,
            status=status,
            provider=provider,
            limit=limit,
            offset=offset,
        )

        return await handler.handle(query)

    async def confirm_payment(self, payment_id: UUID) -> None:
        """Confirm a payment."""
        from .handlers import ConfirmPaymentHandler

        handler = ConfirmPaymentHandler(
            payment_repository=self.payment_repository,
            payment_provider=self.providers["stripe"],  # Default provider
            event_bus=self.event_bus,
        )

        from .commands import ConfirmPaymentCommand
        command = ConfirmPaymentCommand(payment_id=payment_id)

        await handler.handle(command)

    async def cancel_payment(self, payment_id: UUID, reason: Optional[str] = None) -> None:
        """Cancel a payment."""
        from .handlers import CancelPaymentHandler

        handler = CancelPaymentHandler(
            payment_repository=self.payment_repository,
            payment_provider=self.providers["stripe"],  # Default provider
            event_bus=self.event_bus,
        )

        from .commands import CancelPaymentCommand
        command = CancelPaymentCommand(payment_id=payment_id, reason=reason)

        await handler.handle(command)

    async def refund_payment(
        self,
        payment_id: UUID,
        amount: Money,
        reason: Optional[str] = None,
    ) -> None:
        """Refund a payment."""
        from .handlers import RefundPaymentHandler

        handler = RefundPaymentHandler(
            payment_repository=self.payment_repository,
            transaction_repository=self.transaction_repository,
            payment_provider=self.providers["stripe"],  # Default provider
            validation_service=self.validation_service,
            event_bus=self.event_bus,
        )

        from .commands import RefundPaymentCommand
        command = RefundPaymentCommand(
            payment_id=payment_id,
            amount=amount,
            reason=reason,
        )

        await handler.handle(command)

    async def create_payment_method(
        self,
        customer_id: UUID,
        type: str,
        provider: str,
        payment_method_data: Dict[str, Any],
    ) -> PaymentMethod:
        """Create a payment method."""
        from .handlers import CreatePaymentMethodHandler

        handler = CreatePaymentMethodHandler(
            payment_method_repository=self.payment_method_repository,
            payment_provider=self.providers[provider],
            event_bus=self.event_bus,
        )

        from .commands import CreatePaymentMethodCommand
        command = CreatePaymentMethodCommand(
            customer_id=customer_id,
            type=type,
            provider=provider,
            payment_method_data=payment_method_data,
        )

        return await handler.handle(command)

    async def get_payment_method(self, payment_method_id: str) -> Optional[PaymentMethod]:
        """Get a payment method by ID."""
        from .handlers import GetPaymentMethodHandler

        handler = GetPaymentMethodHandler(self.payment_method_repository)
        from .queries import GetPaymentMethodQuery
        query = GetPaymentMethodQuery(payment_method_id=payment_method_id)

        return await handler.handle(query)

    async def list_payment_methods(self, customer_id: UUID) -> List[PaymentMethod]:
        """List payment methods for a customer."""
        from .handlers import ListPaymentMethodsHandler

        handler = ListPaymentMethodsHandler(self.payment_method_repository)
        from .queries import ListPaymentMethodsQuery
        query = ListPaymentMethodsQuery(customer_id=customer_id)

        return await handler.handle(query)

    async def process_webhook(
        self,
        provider: str,
        payload: bytes,
        signature: str,
        headers: Dict[str, str],
    ) -> None:
        """Process a webhook from a payment provider."""
        from .handlers import ProcessWebhookHandler

        handler = ProcessWebhookHandler(
            webhook_service=self.webhook_service,
            payment_repository=self.payment_repository,
            event_bus=self.event_bus,
        )

        from .commands import ProcessWebhookCommand
        command = ProcessWebhookCommand(
            provider=provider,
            payload=payload,
            signature=signature,
            headers=headers,
        )

        await handler.handle(command)