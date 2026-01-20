"""Payment processor worker for background payment processing."""

import asyncio
import json
from typing import Dict, Any, Optional

import redis.asyncio as redis
import structlog

from shared.infrastructure.messaging.event_bus import EventBus
from shared.infrastructure.messaging.redis_event_bus import RedisEventBus
from domains.payments.application.services import PaymentApplicationService
from domains.payments.infrastructure.repositories import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyPaymentMethodRepository,
    SqlAlchemyTransactionRepository,
    RedisIdempotencyRepository,
)
from domains.payments.domain.services import (
    PaymentValidationService,
    IdempotencyService,
    WebhookProcessingService,
)
from domains.payments.infrastructure.providers.stripe_provider import StripeProvider
from domains.payments.infrastructure.providers.paypal_provider import PayPalProvider


logger = structlog.get_logger()


class PaymentProcessorWorker:
    """Worker for processing payment-related background tasks."""

    def __init__(
        self,
        redis_client: redis.Redis,
        database_url: str,
        stripe_config: Dict[str, str],
        paypal_config: Dict[str, str],
    ) -> None:
        self.redis_client = redis_client
        self.database_url = database_url
        self.stripe_config = stripe_config
        self.paypal_config = paypal_config

        self.event_bus: Optional[RedisEventBus] = None
        self.payment_service: Optional[PaymentApplicationService] = None
        self.running = False

    async def start(self) -> None:
        """Start the payment processor worker."""
        logger.info("Starting payment processor worker")

        # Initialize event bus
        self.event_bus = RedisEventBus(self.redis_client)

        # Initialize database session and repositories
        # Note: In production, you'd use a proper session factory
        from shared.infrastructure.database.session import get_session
        async for session in get_session():
            # Initialize repositories
            payment_repo = SqlAlchemyPaymentRepository(session)
            payment_method_repo = SqlAlchemyPaymentMethodRepository(session)
            transaction_repo = SqlAlchemyTransactionRepository(session)
            idempotency_repo = RedisIdempotencyRepository(self.redis_client)

            # Initialize services
            validation_service = PaymentValidationService()
            idempotency_service = IdempotencyService(idempotency_repo)

            # Initialize providers
            providers = {}
            if self.stripe_config:
                providers["stripe"] = StripeProvider(
                    api_key=self.stripe_config["api_key"],
                    webhook_secret=self.stripe_config["webhook_secret"],
                    base_url=self.stripe_config.get("base_url", "https://api.stripe.com/v1"),
                )
            if self.paypal_config:
                providers["paypal"] = PayPalProvider(
                    api_key=self.paypal_config["api_key"],
                    webhook_secret=self.paypal_config["webhook_secret"],
                    base_url=self.paypal_config.get("base_url", "https://api.paypal.com/v1"),
                )

            webhook_service = WebhookProcessingService(providers)

            # Initialize payment application service
            self.payment_service = PaymentApplicationService(
                payment_repository=payment_repo,
                payment_method_repository=payment_method_repo,
                transaction_repository=transaction_repo,
                idempotency_service=idempotency_service,
                validation_service=validation_service,
                webhook_service=webhook_service,
                providers=providers,
                event_bus=self.event_bus,
            )

            break

        self.running = True

        # Register event handlers
        await self._register_event_handlers()

        # Start processing loop
        await self._process_loop()

    async def stop(self) -> None:
        """Stop the payment processor worker."""
        logger.info("Stopping payment processor worker")
        self.running = False

    async def _register_event_handlers(self) -> None:
        """Register event handlers for payment-related events."""
        if not self.event_bus:
            return

        # Register handlers for payment events that need background processing
        # For example, delayed payment processing, reconciliation, etc.

        # Note: Event handlers would be registered here
        # await self.event_bus.subscribe("PaymentCreated", self._handle_payment_created)
        # await self.event_bus.subscribe("PaymentStatusChanged", self._handle_payment_status_changed)

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self.running:
            try:
                # Process pending payments
                await self._process_pending_payments()

                # Process payment reconciliation
                await self._process_payment_reconciliation()

                # Clean up expired idempotency records
                await self._cleanup_expired_idempotency()

                # Wait before next iteration
                await asyncio.sleep(30)  # Process every 30 seconds

            except Exception as e:
                logger.error("Error in payment processor loop", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error

    async def _process_pending_payments(self) -> None:
        """Process payments that are stuck in pending state."""
        # This would query for payments that have been pending too long
        # and attempt to get their status from the provider

        logger.debug("Processing pending payments")
        # Implementation would go here

    async def _process_payment_reconciliation(self) -> None:
        """Reconcile payments with provider data."""
        # This would periodically check payment statuses
        # and update local state if it doesn't match provider state

        logger.debug("Processing payment reconciliation")
        # Implementation would go here

    async def _cleanup_expired_idempotency(self) -> None:
        """Clean up expired idempotency records."""
        try:
            # Get idempotency repository
            idempotency_repo = RedisIdempotencyRepository(self.redis_client)
            deleted_count = await idempotency_repo.delete_expired()
            if deleted_count > 0:
                logger.info("Cleaned up expired idempotency records", count=deleted_count)
        except Exception as e:
            logger.error("Error cleaning up idempotency records", error=str(e))

    # Event handlers
    async def _handle_payment_created(self, event_data: Dict[str, Any]) -> None:
        """Handle payment created event."""
        logger.info("Handling payment created event", payment_id=event_data.get("aggregate_id"))

        # Could implement additional processing here
        # For example, sending notifications, updating metrics, etc.

    async def _handle_payment_status_changed(self, event_data: Dict[str, Any]) -> None:
        """Handle payment status changed event."""
        logger.info(
            "Handling payment status changed event",
            payment_id=event_data.get("aggregate_id"),
            old_status=event_data.get("old_status"),
            new_status=event_data.get("new_status"),
        )

        # Could implement status-specific processing here
        # For example, sending emails on failure, updating subscriptions on success, etc.


class WebhookProcessorWorker:
    """Worker for processing payment webhooks asynchronously."""

    def __init__(
        self,
        redis_client: redis.Redis,
        payment_service: PaymentApplicationService,
    ) -> None:
        self.redis_client = redis_client
        self.payment_service = payment_service
        self.running = False

    async def start(self) -> None:
        """Start the webhook processor worker."""
        logger.info("Starting webhook processor worker")
        self.running = True

        # Start processing webhooks from queue
        await self._process_webhook_queue()

    async def stop(self) -> None:
        """Stop the webhook processor worker."""
        logger.info("Stopping webhook processor worker")
        self.running = False

    async def _process_webhook_queue(self) -> None:
        """Process webhooks from Redis queue."""
        while self.running:
            try:
                # Get webhook from queue
                webhook_data = await self.redis_client.blpop("payment_webhooks", timeout=5)
                if not webhook_data:
                    continue

                _, webhook_json = webhook_data
                webhook = json.loads(webhook_json)

                # Process webhook
                await self._process_webhook(webhook)

            except Exception as e:
                logger.error("Error processing webhook", error=str(e))
                await asyncio.sleep(5)

    async def _process_webhook(self, webhook: Dict[str, Any]) -> None:
        """Process a single webhook."""
        try:
            provider = webhook["provider"]
            payload = webhook["payload"].encode()
            signature = webhook["signature"]
            headers = webhook.get("headers", {})

            await self.payment_service.process_webhook(provider, payload, signature, headers)

            logger.info("Successfully processed webhook", provider=provider)

        except Exception as e:
            logger.error("Failed to process webhook", error=str(e), webhook=webhook)

            # Could implement retry logic here
            # For example, move to dead letter queue after max retries