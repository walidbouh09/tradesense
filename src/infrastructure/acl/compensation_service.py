"""
Compensation Service for ACL failure scenarios.

Handles compensation strategies when cross-domain operations fail:
- Automatic refunds for failed challenge creation
- Manual review queues
- Notification systems
- SLA-based escalation
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

from shared.infrastructure.messaging.event_bus import EventBus
from shared.infrastructure.logging.audit_logger import AuditLogger


class CompensationService:
    """Handles compensation for failed cross-domain operations."""

    def __init__(
        self,
        event_bus: EventBus,
        audit_logger: AuditLogger,
        refund_service: Any,  # Would be PaymentRefundService
    ):
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self.refund_service = refund_service

        # SLA configurations
        self.sla_configs = {
            "challenge_creation": {
                "automatic_refund_hours": 24,  # Auto-refund after 24 hours
                "manual_review_hours": 4,      # Queue for manual review after 4 hours
                "escalation_hours": 72,       # Escalate to management after 72 hours
            }
        }

    async def register_handlers(self) -> None:
        """Register compensation event handlers."""
        await self.event_bus.subscribe("ChallengeCreationCompensationRequired", self._handle_compensation_required)
        await self.event_bus.subscribe("PaymentChallengeTransformationFailed", self._handle_transformation_failed)

    async def _handle_compensation_required(self, event_data: Dict[str, Any]) -> None:
        """
        Handle compensation required for failed challenge creation.

        Compensation Strategy:
        1. Immediate: Queue for manual review
        2. 4 hours: Send customer notification
        3. 24 hours: Automatic refund
        4. 72 hours: Management escalation
        """
        correlation_id = event_data.get("correlation_id")
        payment_id = event_data.get("payment_id")
        customer_id = event_data.get("customer_id")

        self.audit_logger.log_business_event(
            event_type="compensation_initiated",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "customer_id": customer_id,
                "reason": "challenge_creation_failed",
            },
            severity="WARNING"
        )

        # Schedule compensation actions
        await self._schedule_compensation_actions(correlation_id, payment_id, customer_id)

    async def _handle_transformation_failed(self, event_data: Dict[str, Any]) -> None:
        """
        Handle transformation failures.

        These are typically data validation issues that require manual intervention.
        """
        correlation_id = event_data.get("correlation_id")
        payment_id = event_data.get("payment_id")
        reason = event_data.get("reason")

        # Queue for immediate manual review
        await self._queue_manual_review(correlation_id, payment_id, reason, "transformation_error")

        self.audit_logger.log_business_event(
            event_type="transformation_compensation_queued",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "reason": reason,
            },
            severity="ERROR"
        )

    async def _schedule_compensation_actions(
        self,
        correlation_id: str,
        payment_id: str,
        customer_id: str,
    ) -> None:
        """Schedule compensation actions based on SLA."""
        sla = self.sla_configs["challenge_creation"]

        # Immediate: Queue for manual review
        await self._queue_manual_review(correlation_id, payment_id, "Challenge creation failed", "challenge_creation")

        # 4 hours: Send customer notification
        await asyncio.sleep(4 * 3600)  # Would be replaced with proper scheduling
        await self._send_customer_notification(customer_id, payment_id, "challenge_creation_delay")

        # 24 hours: Automatic refund
        await asyncio.sleep(20 * 3600)  # Additional 20 hours
        await self._process_automatic_refund(payment_id, correlation_id)

        # 72 hours: Management escalation
        await asyncio.sleep(48 * 3600)  # Additional 48 hours
        await self._escalate_to_management(correlation_id, payment_id, customer_id)

    async def _queue_manual_review(
        self,
        correlation_id: str,
        payment_id: str,
        reason: str,
        compensation_type: str,
    ) -> None:
        """Queue issue for manual review by operations team."""
        await self.event_bus.publish({
            "event_type": "ManualReviewRequired",
            "correlation_id": correlation_id,
            "payment_id": payment_id,
            "reason": reason,
            "compensation_type": compensation_type,
            "priority": "high",
            "queue": "payment_challenge_acl_failures",
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _send_customer_notification(
        self,
        customer_id: str,
        payment_id: str,
        notification_type: str,
    ) -> None:
        """Send notification to customer about processing delay."""
        await self.event_bus.publish({
            "event_type": "CustomerNotificationRequired",
            "customer_id": customer_id,
            "payment_id": payment_id,
            "notification_type": notification_type,
            "channel": "email",
            "template": "challenge_creation_delay",
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _process_automatic_refund(
        self,
        payment_id: str,
        correlation_id: str,
    ) -> None:
        """Process automatic refund after SLA breach."""
        try:
            # Check if already resolved
            if await self._is_issue_resolved(correlation_id):
                return

            # Process refund
            refund_result = await self.refund_service.process_full_refund(
                payment_id=payment_id,
                reason="Challenge creation failed - SLA breach",
                correlation_id=correlation_id,
            )

            if refund_result["success"]:
                await self.event_bus.publish({
                    "event_type": "AutomaticRefundProcessed",
                    "correlation_id": correlation_id,
                    "payment_id": payment_id,
                    "refund_id": refund_result["refund_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                })

                self.audit_logger.log_business_event(
                    event_type="automatic_refund_success",
                    details={
                        "correlation_id": correlation_id,
                        "payment_id": payment_id,
                        "refund_id": refund_result["refund_id"],
                    },
                )
            else:
                # Refund failed - escalate immediately
                await self._escalate_to_management(
                    correlation_id, payment_id, None, "Refund processing failed"
                )

        except Exception as e:
            self.audit_logger.log_business_event(
                event_type="automatic_refund_error",
                details={
                    "correlation_id": correlation_id,
                    "payment_id": payment_id,
                    "error": str(e),
                },
                severity="CRITICAL"
            )

    async def _escalate_to_management(
        self,
        correlation_id: str,
        payment_id: str,
        customer_id: Optional[str],
        reason: str = "SLA breach without resolution",
    ) -> None:
        """Escalate unresolved issues to management."""
        await self.event_bus.publish({
            "event_type": "ManagementEscalationRequired",
            "correlation_id": correlation_id,
            "payment_id": payment_id,
            "customer_id": customer_id,
            "reason": reason,
            "escalation_level": "senior_management",
            "requires_immediate_action": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.audit_logger.log_business_event(
            event_type="management_escalation",
            details={
                "correlation_id": correlation_id,
                "payment_id": payment_id,
                "reason": reason,
            },
            severity="CRITICAL"
        )

    async def _is_issue_resolved(self, correlation_id: str) -> bool:
        """Check if compensation issue has been resolved."""
        # Would query resolution status from database
        # For now, return False
        return False

    async def get_compensation_statistics(self) -> Dict[str, Any]:
        """Get compensation processing statistics."""
        # Would implement metrics collection
        return {
            "automatic_refunds_processed": 0,
            "manual_reviews_completed": 0,
            "escalations_triggered": 0,
            "average_resolution_time_hours": 0,
        }

    async def resolve_compensation_issue(
        self,
        correlation_id: str,
        resolution_type: str,
        resolution_details: Dict[str, Any],
    ) -> None:
        """
        Mark compensation issue as resolved.

        Resolution Types:
        - manual_challenge_created: Ops team manually created challenge
        - refund_processed: Refund issued to customer
        - issue_escalated: Sent to higher level
        - customer_credited: Alternative compensation provided
        """
        await self.event_bus.publish({
            "event_type": "CompensationIssueResolved",
            "correlation_id": correlation_id,
            "resolution_type": resolution_type,
            "resolution_details": resolution_details,
            "resolved_at": datetime.utcnow().isoformat(),
            "resolved_by": "system",  # Would be actual user/system
        })

        self.audit_logger.log_business_event(
            event_type="compensation_resolved",
            details={
                "correlation_id": correlation_id,
                "resolution_type": resolution_type,
                "resolution_details": resolution_details,
            },
        )