"""
Anti-Corruption Layer: Payment Context → Challenge Context

Scenario: PaymentSucceeded → ChallengeCreated

Responsibilities:
- Translate Payment domain events to Challenge domain commands
- Handle cross-domain communication without tight coupling
- Implement failure scenarios and compensation strategies
- Maintain transactional consistency across domains
"""

from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime
import asyncio

from shared.infrastructure.messaging.event_bus import EventBus
from shared.infrastructure.logging.audit_logger import AuditLogger
from shared.infrastructure.database.session import get_session

from domains.payments.domain.events import PaymentSucceeded
from domains.challenges.domain.commands import CreateChallengeCommand
from domains.challenges.application.handlers import CreateChallengeHandler
from domains.challenges.domain.repositories import ChallengeRepository


class PaymentToChallengeACL:
    """
    Anti-Corruption Layer for Payment → Challenge context transformation.

    This ACL:
    1. Listens to PaymentSucceeded events
    2. Translates payment data to challenge creation parameters
    3. Handles failure scenarios with compensation
    4. Maintains audit trail of transformations
    """

    def __init__(
        self,
        event_bus: EventBus,
        audit_logger: AuditLogger,
    ):
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self._registered = False

    async def register_handlers(self) -> None:
        """Register ACL event handlers."""
        if self._registered:
            return

        await self.event_bus.subscribe("PaymentSucceeded", self._handle_payment_succeeded)
        await self.event_bus.subscribe("ChallengeCreationFailed", self._handle_challenge_creation_failed)

        self._registered = True
        self.audit_logger.log_business_event(
            event_type="acl_registered",
            details={"acl": "payment_to_challenge", "handlers": ["PaymentSucceeded", "ChallengeCreationFailed"]},
        )

    async def _handle_payment_succeeded(self, event_data: Dict[str, Any]) -> None:
        """
        Handle PaymentSucceeded event and create challenge.

        Event Flow:
        1. Receive PaymentSucceeded event
        2. Validate payment is for challenge purchase
        3. Transform payment data to challenge parameters
        4. Create challenge via command
        5. Handle success/failure with compensation
        """
        correlation_id = str(uuid4())
        payment_id = event_data.get("aggregate_id")
        customer_id = event_data.get("customer_id")

        self.audit_logger.log_business_event(
            event_type="acl_payment_succeeded_received",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "customer_id": customer_id,
                "amount": event_data.get("amount"),
            },
        )

        try:
            # Step 1: Validate this payment is for a challenge
            if not await self._is_challenge_payment(payment_id, event_data):
                self.audit_logger.log_business_event(
                    event_type="acl_payment_not_for_challenge",
                    details={"payment_id": payment_id},
                )
                return

            # Step 2: Transform payment data to challenge parameters
            challenge_params = await self._transform_payment_to_challenge(
                payment_id, event_data, correlation_id
            )

            if not challenge_params:
                await self._handle_transformation_failure(payment_id, "Invalid payment data", correlation_id)
                return

            # Step 3: Create challenge with transactional safety
            challenge_id = await self._create_challenge_with_compensation(
                challenge_params, correlation_id
            )

            if challenge_id:
                # Success: Emit correlation event
                await self.event_bus.publish({
                    "event_type": "PaymentChallengeCorrelationEstablished",
                    "correlation_id": correlation_id,
                    "payment_id": payment_id,
                    "challenge_id": challenge_id,
                    "customer_id": customer_id,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                self.audit_logger.log_business_event(
                    event_type="acl_challenge_created_success",
                    details={
                        "correlation_id": correlation_id,
                        "payment_id": payment_id,
                        "challenge_id": challenge_id,
                    },
                )
            else:
                await self._handle_challenge_creation_failure(payment_id, correlation_id)

        except Exception as e:
            await self._handle_unexpected_error(payment_id, str(e), correlation_id)

    async def _is_challenge_payment(self, payment_id: str, event_data: Dict[str, Any]) -> bool:
        """
        Determine if payment is for challenge purchase.

        Strategies:
        1. Check payment metadata for challenge_type
        2. Check payment description
        3. Check customer subscription/product type
        """
        # Check metadata
        metadata = event_data.get("metadata", {})
        if metadata.get("product_type") == "challenge":
            return True

        # Check description patterns
        description = event_data.get("description", "").lower()
        challenge_keywords = ["challenge", "prop trading", "evaluation", "funded account"]
        if any(keyword in description for keyword in challenge_keywords):
            return True

        # Check customer data (would query customer service)
        # For now, assume all payments could be for challenges
        return True

    async def _transform_payment_to_challenge(
        self,
        payment_id: str,
        event_data: Dict[str, Any],
        correlation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Transform PaymentSucceeded event to Challenge creation parameters.

        Mapping Rules:
        - Payment amount → Challenge initial_balance
        - Customer ID → Challenge trader_id
        - Metadata → Challenge parameters (challenge_type, etc.)
        - Payment currency → Challenge currency
        """
        try:
            metadata = event_data.get("metadata", {})
            amount = event_data.get("amount")

            # Determine challenge type from payment
            challenge_type = self._determine_challenge_type(metadata, amount)

            # Build challenge parameters
            challenge_params = {
                "trader_id": event_data.get("customer_id"),
                "challenge_type": challenge_type,
                "initial_balance": amount,
                "currency": event_data.get("currency", "USD"),
                "payment_reference": payment_id,
                "correlation_id": correlation_id,
                "created_from_payment": True,
                "payment_metadata": metadata,
            }

            # Validate transformation
            if not self._validate_challenge_params(challenge_params):
                return None

            self.audit_logger.log_business_event(
                event_type="acl_transformation_success",
                details={
                    "correlation_id": correlation_id,
                    "payment_id": payment_id,
                    "challenge_params": challenge_params,
                },
            )

            return challenge_params

        except Exception as e:
            self.audit_logger.log_business_event(
                event_type="acl_transformation_error",
                details={
                    "correlation_id": correlation_id,
                    "payment_id": payment_id,
                    "error": str(e),
                },
                severity="ERROR"
            )
            return None

    def _determine_challenge_type(self, metadata: Dict[str, Any], amount: float) -> str:
        """Determine challenge type from payment data."""
        # Explicit type in metadata
        if metadata.get("challenge_type"):
            return metadata["challenge_type"]

        # Amount-based determination (example logic)
        if amount >= 500:  # $500+ for Phase 2
            return "PHASE_2"
        elif amount >= 200:  # $200+ for Phase 1
            return "PHASE_1"
        else:
            return "PHASE_1"  # Default

    def _validate_challenge_params(self, params: Dict[str, Any]) -> bool:
        """Validate challenge creation parameters."""
        required_fields = ["trader_id", "challenge_type", "initial_balance", "currency"]

        for field in required_fields:
            if not params.get(field):
                return False

        # Validate challenge type
        valid_types = ["PHASE_1", "PHASE_2", "PHASE_3"]
        if params["challenge_type"] not in valid_types:
            return False

        # Validate amount ranges
        amount = params["initial_balance"]
        if not isinstance(amount, (int, float)) or amount <= 0:
            return False

        return True

    async def _create_challenge_with_compensation(
        self,
        challenge_params: Dict[str, Any],
        correlation_id: str,
    ) -> Optional[str]:
        """
        Create challenge with compensation strategy.

        If challenge creation fails, we need compensation strategies:
        1. Retry with backoff
        2. Manual intervention queue
        3. Refund payment (last resort)
        """
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async for session in get_session():
                    # Get challenge repository and handler
                    challenge_repo = ChallengeRepository(session)  # Would be injected
                    handler = CreateChallengeHandler(challenge_repo, self.event_bus)

                    # Create command
                    command = CreateChallengeCommand(**challenge_params)

                    # Execute command
                    challenge = await handler.handle(command)

                    return str(challenge.id)

            except Exception as e:
                self.audit_logger.log_business_event(
                    event_type="acl_challenge_creation_retry",
                    details={
                        "correlation_id": correlation_id,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                    severity="WARNING"
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    # Final failure - trigger compensation
                    await self._trigger_compensation(challenge_params, correlation_id, str(e))

        return None

    async def _trigger_compensation(
        self,
        challenge_params: Dict[str, Any],
        correlation_id: str,
        error: str,
    ) -> None:
        """
        Trigger compensation for failed challenge creation.

        Compensation Strategies:
        1. Queue for manual processing
        2. Alert operations team
        3. Schedule refund (if SLA exceeded)
        """
        # Emit compensation event
        await self.event_bus.publish({
            "event_type": "ChallengeCreationCompensationRequired",
            "correlation_id": correlation_id,
            "payment_id": challenge_params.get("payment_reference"),
            "customer_id": challenge_params.get("trader_id"),
            "challenge_params": challenge_params,
            "error": error,
            "compensation_type": "manual_review",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Log for alerting
        self.audit_logger.log_business_event(
            event_type="acl_compensation_triggered",
            details={
                "correlation_id": correlation_id,
                "compensation_type": "manual_review",
                "error": error,
            },
            severity="CRITICAL"
        )

    async def _handle_transformation_failure(
        self,
        payment_id: str,
        reason: str,
        correlation_id: str,
    ) -> None:
        """Handle transformation failure."""
        await self.event_bus.publish({
            "event_type": "PaymentChallengeTransformationFailed",
            "correlation_id": correlation_id,
            "payment_id": payment_id,
            "reason": reason,
            "requires_compensation": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.audit_logger.log_business_event(
            event_type="acl_transformation_failure",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "reason": reason,
            },
            severity="ERROR"
        )

    async def _handle_challenge_creation_failure(
        self,
        payment_id: str,
        correlation_id: str,
    ) -> None:
        """Handle challenge creation failure after retries."""
        await self.event_bus.publish({
            "event_type": "ChallengeCreationFailed",
            "correlation_id": correlation_id,
            "payment_id": payment_id,
            "requires_compensation": True,
            "compensation_type": "refund_or_manual",
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.audit_logger.log_business_event(
            event_type="acl_challenge_creation_failure",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
            },
            severity="CRITICAL"
        )

    async def _handle_unexpected_error(
        self,
        payment_id: str,
        error: str,
        correlation_id: str,
    ) -> None:
        """Handle unexpected errors in ACL processing."""
        await self.event_bus.publish({
            "event_type": "ACLProcessingError",
            "correlation_id": correlation_id,
            "payment_id": payment_id,
            "error": error,
            "requires_investigation": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.audit_logger.log_business_event(
            event_type="acl_unexpected_error",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "error": error,
            },
            severity="CRITICAL"
        )

    async def _handle_challenge_creation_failed(self, event_data: Dict[str, Any]) -> None:
        """
        Handle ChallengeCreationFailed events for compensation.

        This creates a feedback loop for compensation handling.
        """
        correlation_id = event_data.get("correlation_id")
        payment_id = event_data.get("payment_id")

        self.audit_logger.log_business_event(
            event_type="acl_compensation_feedback_received",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
            },
        )

        # Here you would implement compensation logic:
        # 1. Check SLA for automatic refund
        # 2. Queue for manual processing
        # 3. Send notifications
        # 4. Update payment status

    async def get_acl_statistics(self) -> Dict[str, Any]:
        """Get ACL processing statistics for monitoring."""
        # Would implement metrics collection
        return {
            "transformations_successful": 0,
            "transformations_failed": 0,
            "compensations_triggered": 0,
            "average_processing_time": 0,
        }