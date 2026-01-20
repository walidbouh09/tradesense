"""Notification worker for sending alerts and notifications."""

from typing import List, Dict, Any
from decimal import Decimal
import structlog

from ...infrastructure.messaging.enhanced_event_bus import BaseEventWorker, TransientError, PermanentError
from ...infrastructure.common.context import ExecutionContext
from ...shared.kernel.events import DomainEvent
from ...shared.events.domain_events import (
    RiskAlertTriggeredV1,
    RiskLimitBreachedV1,
    ChallengePhaseCompletedV1,
    TradingPositionClosedV1,
    AuthUserLoggedInV1,
)

logger = structlog.get_logger()


class NotificationService:
    """Service for sending notifications (placeholder implementation)."""
    
    async def send_risk_alert(self, alert_data: Dict[str, Any]) -> None:
        """Send risk alert notification."""
        logger.info("NOTIFICATION: Risk alert", **alert_data)
    
    async def send_limit_breach_alert(self, breach_data: Dict[str, Any]) -> None:
        """Send limit breach notification."""
        logger.warning("NOTIFICATION: Limit breached", **breach_data)
    
    async def send_phase_completion(self, completion_data: Dict[str, Any]) -> None:
        """Send phase completion notification."""
        logger.info("NOTIFICATION: Phase completed", **completion_data)
    
    async def send_pnl_notification(self, pnl_data: Dict[str, Any]) -> None:
        """Send significant P&L notification."""
        logger.info("NOTIFICATION: Significant P&L", **pnl_data)
    
    async def send_security_alert(self, security_data: Dict[str, Any]) -> None:
        """Send security alert notification."""
        logger.warning("NOTIFICATION: Security alert", **security_data)


class NotificationWorker(BaseEventWorker):
    """Worker for sending notifications based on domain events."""
    
    def __init__(
        self,
        event_bus,
        notification_service: NotificationService = None,
    ):
        super().__init__(
            worker_name="notification",
            event_bus=event_bus,
            concurrency=3,  # Moderate concurrency for I/O operations
            batch_size=5,   # Process in small batches for efficiency
        )
        self.notification_service = notification_service or NotificationService()
        self.logger = logger.bind(worker="notification")
    
    def get_subscribed_events(self) -> List[str]:
        """Subscribe to events that require notifications."""
        return [
            "RiskAlertTriggeredV1",
            "RiskLimitBreachedV1",
            "ChallengePhaseCompletedV1",
            "TradingPositionClosedV1",
            "AuthUserLoggedInV1",
        ]
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Process events and send appropriate notifications."""
        
        try:
            if isinstance(event, RiskAlertTriggeredV1):
                await self._handle_risk_alert(event, context)
            elif isinstance(event, RiskLimitBreachedV1):
                await self._handle_limit_breach(event, context)
            elif isinstance(event, ChallengePhaseCompletedV1):
                await self._handle_phase_completion(event, context)
            elif isinstance(event, TradingPositionClosedV1):
                await self._handle_position_closed(event, context)
            elif isinstance(event, AuthUserLoggedInV1):
                await self._handle_user_login(event, context)
            else:
                self.logger.warning(
                    "Unhandled event type for notifications",
                    event_type=event.event_type,
                    event_id=str(event.event_id)
                )
                
        except ValueError as e:
            # Data validation errors are permanent
            raise PermanentError(f"Invalid notification data: {e}") from e
        except ConnectionError as e:
            # Network errors for notifications are transient
            raise TransientError(f"Notification service unavailable: {e}") from e
        except Exception as e:
            # Most notification errors should be retried
            self.logger.error(
                "Error sending notification",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e)
            )
            raise TransientError(f"Notification error: {e}") from e
    
    async def _handle_risk_alert(
        self,
        event: RiskAlertTriggeredV1,
        context: ExecutionContext,
    ) -> None:
        """Handle risk alert event."""
        
        self.logger.info(
            "Processing risk alert notification",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            alert_type=event.alert_type,
            severity=event.severity
        )
        
        alert_data = {
            "user_id": str(event.user_id),
            "challenge_id": str(event.challenge_id),
            "alert_type": event.alert_type,
            "message": event.message,
            "severity": event.severity,
            "data": event.data,
            "timestamp": event.occurred_at.isoformat(),
        }
        
        await self.notification_service.send_risk_alert(alert_data)
        
        # For critical alerts, also send immediate notifications
        if event.severity == "critical":
            # In a real implementation, this might send SMS, push notifications, etc.
            self.logger.critical(
                "CRITICAL RISK ALERT",
                user_id=str(event.user_id),
                message=event.message
            )
    
    async def _handle_limit_breach(
        self,
        event: RiskLimitBreachedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle risk limit breach event."""
        
        self.logger.warning(
            "Processing limit breach notification",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            limit_type=event.limit_type,
            severity=event.severity
        )
        
        breach_data = {
            "user_id": str(event.user_id),
            "challenge_id": str(event.challenge_id),
            "limit_type": event.limit_type,
            "limit_value": str(event.limit_value),
            "current_value": str(event.current_value),
            "severity": event.severity,
            "timestamp": event.occurred_at.isoformat(),
        }
        
        await self.notification_service.send_limit_breach_alert(breach_data)
        
        # For critical breaches, log as error
        if event.severity == "critical":
            self.logger.error(
                "CRITICAL LIMIT BREACH",
                user_id=str(event.user_id),
                limit_type=event.limit_type,
                current_value=str(event.current_value),
                limit_value=str(event.limit_value)
            )
    
    async def _handle_phase_completion(
        self,
        event: ChallengePhaseCompletedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle challenge phase completion event."""
        
        self.logger.info(
            "Processing phase completion notification",
            user_id=str(event.user_id),
            challenge_id=str(event.aggregate_id),
            phase_type=event.phase_type,
            completion_status=event.completion_status
        )
        
        completion_data = {
            "user_id": str(event.user_id),
            "challenge_id": str(event.aggregate_id),
            "phase_type": event.phase_type,
            "completion_status": event.completion_status,
            "final_balance": str(event.final_balance),
            "total_pnl": str(event.total_pnl),
            "completion_reason": event.completion_reason,
            "timestamp": event.occurred_at.isoformat(),
        }
        
        await self.notification_service.send_phase_completion(completion_data)
        
        # Special handling for phase progression
        if event.completion_status == "passed":
            self.logger.info(
                "PHASE PASSED",
                user_id=str(event.user_id),
                phase_type=event.phase_type,
                final_balance=str(event.final_balance)
            )
        else:
            self.logger.warning(
                "PHASE FAILED",
                user_id=str(event.user_id),
                phase_type=event.phase_type,
                reason=event.completion_reason
            )
    
    async def _handle_position_closed(
        self,
        event: TradingPositionClosedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle position closed event for significant P&L notifications."""
        
        # Only notify for significant P&L events
        if not self._is_significant_pnl(event.realized_pnl):
            return
        
        self.logger.info(
            "Processing significant P&L notification",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            symbol=event.symbol,
            realized_pnl=str(event.realized_pnl)
        )
        
        pnl_data = {
            "user_id": str(event.user_id),
            "challenge_id": str(event.challenge_id),
            "position_id": str(event.aggregate_id),
            "symbol": event.symbol,
            "side": event.side,
            "size": str(event.size),
            "entry_price": str(event.entry_price),
            "exit_price": str(event.exit_price),
            "realized_pnl": str(event.realized_pnl),
            "close_reason": event.close_reason,
            "timestamp": event.occurred_at.isoformat(),
        }
        
        await self.notification_service.send_pnl_notification(pnl_data)
        
        # Log significant wins/losses
        if event.realized_pnl > Decimal("5000"):
            self.logger.info(
                "SIGNIFICANT WIN",
                user_id=str(event.user_id),
                symbol=event.symbol,
                pnl=str(event.realized_pnl)
            )
        elif event.realized_pnl < Decimal("-2000"):
            self.logger.warning(
                "SIGNIFICANT LOSS",
                user_id=str(event.user_id),
                symbol=event.symbol,
                pnl=str(event.realized_pnl)
            )
    
    async def _handle_user_login(
        self,
        event: AuthUserLoggedInV1,
        context: ExecutionContext,
    ) -> None:
        """Handle user login event for security monitoring."""
        
        # Check for suspicious login patterns
        if self._is_suspicious_login(event):
            self.logger.warning(
                "Processing suspicious login notification",
                user_id=str(event.aggregate_id),
                email=event.email,
                ip_address=event.ip_address
            )
            
            security_data = {
                "user_id": str(event.aggregate_id),
                "email": event.email,
                "login_method": event.login_method,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "timestamp": event.occurred_at.isoformat(),
                "alert_reason": "suspicious_login_pattern",
            }
            
            await self.notification_service.send_security_alert(security_data)
    
    def _is_significant_pnl(self, pnl: Decimal) -> bool:
        """Check if P&L is significant enough for notification."""
        # Notify for P&L > $1000 (win or loss)
        return abs(pnl) > Decimal("1000")
    
    def _is_suspicious_login(self, event: AuthUserLoggedInV1) -> bool:
        """Check if login appears suspicious."""
        # Simple heuristics for suspicious logins
        # In a real implementation, this would be more sophisticated
        
        # Check for unusual hours (example: 2 AM - 6 AM UTC)
        hour = event.occurred_at.hour
        if 2 <= hour <= 6:
            return True
        
        # Check for known suspicious IP patterns (example)
        if event.ip_address.startswith("192.168."):
            return False  # Local network, not suspicious
        
        # In a real implementation, you might check:
        # - Geolocation changes
        # - Device fingerprinting
        # - Login frequency
        # - Known malicious IPs
        
        return False