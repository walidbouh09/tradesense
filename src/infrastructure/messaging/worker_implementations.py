"""Concrete worker implementations for TradeSense AI domains."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog

from ...domains.risk.application.services import RiskMonitoringService
from ...shared.kernel.events import DomainEvent
from ..common.context import ExecutionContext
from .enhanced_event_bus import EventWorker

logger = structlog.get_logger()


class RiskMonitoringWorker(EventWorker):
    """Worker for processing risk-related events."""
    
    def __init__(
        self,
        risk_monitoring_service: RiskMonitoringService,
        worker_id: Optional[str] = None,
    ):
        super().__init__(worker_id)
        self.risk_monitoring_service = risk_monitoring_service
        self.handled_event_types = {
            "Trading.Position.Opened.v1",
            "Trading.Position.Closed.v1",
            "Trading.Trade.Executed.v1",
            "Trading.PnL.Updated.v1",
        }
    
    @property
    def worker_name(self) -> str:
        return "risk_monitoring_worker"
    
    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.handled_event_types
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Process risk-related events."""
        logger.info(
            "Processing risk event",
            event_type=event.event_type,
            event_id=str(event.event_id),
            worker_id=self.worker_id,
        )
        
        if event.event_type == "Trading.Position.Opened.v1":
            await self._handle_position_opened(event, context)
        elif event.event_type == "Trading.Position.Closed.v1":
            await self._handle_position_closed(event, context)
        elif event.event_type == "Trading.Trade.Executed.v1":
            await self._handle_trade_executed(event, context)
        elif event.event_type == "Trading.PnL.Updated.v1":
            await self._handle_pnl_updated(event, context)
    
    async def _handle_position_opened(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle position opened event."""
        # Extract position data from event
        position_data = {
            "position_id": getattr(event, "position_id", None),
            "user_id": getattr(event, "user_id", None),
            "symbol": getattr(event, "symbol", None),
            "size": getattr(event, "size", None),
            "entry_price": getattr(event, "entry_price", None),
        }
        
        # Update risk calculations
        await self.risk_monitoring_service.update_position_risk(
            user_id=UUID(position_data["user_id"]),
            position_data=position_data,
        )
    
    async def _handle_position_closed(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle position closed event."""
        position_data = {
            "position_id": getattr(event, "position_id", None),
            "user_id": getattr(event, "user_id", None),
            "realized_pnl": getattr(event, "realized_pnl", None),
        }
        
        await self.risk_monitoring_service.update_position_closure(
            user_id=UUID(position_data["user_id"]),
            position_data=position_data,
        )
    
    async def _handle_trade_executed(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle trade executed event."""
        trade_data = {
            "trade_id": getattr(event, "trade_id", None),
            "user_id": getattr(event, "user_id", None),
            "symbol": getattr(event, "symbol", None),
            "quantity": getattr(event, "quantity", None),
            "price": getattr(event, "price", None),
            "side": getattr(event, "side", None),
        }
        
        await self.risk_monitoring_service.process_trade_event(
            user_id=UUID(trade_data["user_id"]),
            trade_data=trade_data,
        )
    
    async def _handle_pnl_updated(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle PnL updated event."""
        pnl_data = {
            "user_id": getattr(event, "user_id", None),
            "current_balance": getattr(event, "current_balance", None),
            "daily_pnl": getattr(event, "daily_pnl", None),
            "total_pnl": getattr(event, "total_pnl", None),
            "unrealized_pnl": getattr(event, "unrealized_pnl", None),
        }
        
        # This would be implemented in the risk monitoring service
        # await self.risk_monitoring_service.process_pnl_event(
        #     user_id=UUID(pnl_data["user_id"]),
        #     pnl_data=pnl_data,
        # )


class AuditLogWorker(EventWorker):
    """Worker for writing all events to audit log."""
    
    def __init__(self, worker_id: Optional[str] = None):
        super().__init__(worker_id)
        self.audit_events: List[Dict[str, Any]] = []
    
    @property
    def worker_name(self) -> str:
        return "audit_log_worker"
    
    def can_handle(self, event: DomainEvent) -> bool:
        # Audit worker handles all events
        return True
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Write event to audit log."""
        audit_entry = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "occurred_at": event.occurred_at.isoformat(),
            "context": {
                "correlation_id": str(context.correlation_id),
                "user_id": str(context.user_id) if context.user_id else None,
                "source": context.source,
            },
            "event_data": event.to_dict(),
            "audit_timestamp": datetime.utcnow().isoformat(),
        }
        
        # In production, this would write to a persistent audit store
        self.audit_events.append(audit_entry)
        
        logger.info(
            "Event audited",
            event_type=event.event_type,
            event_id=str(event.event_id),
            audit_timestamp=audit_entry["audit_timestamp"],
        )
    
    def get_audit_events(self) -> List[Dict[str, Any]]:
        """Get all audit events (for testing/debugging)."""
        return self.audit_events.copy()


class NotificationWorker(EventWorker):
    """Worker for sending notifications based on events."""
    
    def __init__(self, worker_id: Optional[str] = None):
        super().__init__(worker_id)
        self.notification_event_types = {
            "Risk.Limit.Breached.v1",
            "Risk.Alert.Triggered.v1",
            "Challenge.Completed.v1",
            "Challenge.Failed.v1",
            "Auth.User.LoggedIn.v1",
        }
    
    @property
    def worker_name(self) -> str:
        return "notification_worker"
    
    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.notification_event_types
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Send notifications based on event type."""
        logger.info(
            "Processing notification event",
            event_type=event.event_type,
            event_id=str(event.event_id),
        )
        
        if event.event_type == "Risk.Limit.Breached.v1":
            await self._send_risk_alert(event)
        elif event.event_type == "Risk.Alert.Triggered.v1":
            await self._send_risk_notification(event)
        elif event.event_type == "Challenge.Completed.v1":
            await self._send_challenge_completion_notification(event)
        elif event.event_type == "Challenge.Failed.v1":
            await self._send_challenge_failure_notification(event)
        elif event.event_type == "Auth.User.LoggedIn.v1":
            await self._send_login_notification(event)
    
    async def _send_risk_alert(self, event: DomainEvent) -> None:
        """Send critical risk alert."""
        user_id = getattr(event, "user_id", None)
        limit_type = getattr(event, "limit_type", None)
        current_value = getattr(event, "current_value", None)
        limit_value = getattr(event, "limit_value", None)
        
        # In production, this would send email/SMS/push notification
        logger.warning(
            "CRITICAL RISK ALERT",
            user_id=user_id,
            limit_type=limit_type,
            current_value=current_value,
            limit_value=limit_value,
        )
    
    async def _send_risk_notification(self, event: DomainEvent) -> None:
        """Send risk notification."""
        user_id = getattr(event, "user_id", None)
        alert_type = getattr(event, "alert_type", None)
        message = getattr(event, "message", None)
        
        logger.info(
            "Risk notification sent",
            user_id=user_id,
            alert_type=alert_type,
            message=message,
        )
    
    async def _send_challenge_completion_notification(self, event: DomainEvent) -> None:
        """Send challenge completion notification."""
        user_id = getattr(event, "user_id", None)
        challenge_id = getattr(event, "challenge_id", None)
        challenge_type = getattr(event, "challenge_type", None)
        
        logger.info(
            "Challenge completion notification sent",
            user_id=user_id,
            challenge_id=challenge_id,
            challenge_type=challenge_type,
        )
    
    async def _send_challenge_failure_notification(self, event: DomainEvent) -> None:
        """Send challenge failure notification."""
        user_id = getattr(event, "user_id", None)
        challenge_id = getattr(event, "challenge_id", None)
        failure_reason = getattr(event, "failure_reason", None)
        
        logger.info(
            "Challenge failure notification sent",
            user_id=user_id,
            challenge_id=challenge_id,
            failure_reason=failure_reason,
        )
    
    async def _send_login_notification(self, event: DomainEvent) -> None:
        """Send login notification."""
        user_id = getattr(event, "user_id", None)
        ip_address = getattr(event, "ip_address", None)
        user_agent = getattr(event, "user_agent", None)
        
        logger.info(
            "Login notification sent",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )


class ReportingWorker(EventWorker):
    """Worker for generating reports based on events."""
    
    def __init__(self, worker_id: Optional[str] = None):
        super().__init__(worker_id)
        self.batch_size = 50  # Process more events in batch
        self.reporting_events = {
            "Trading.Trade.Executed.v1",
            "Trading.Position.Closed.v1",
            "Challenge.Completed.v1",
            "Risk.Limit.Breached.v1",
        }
        self.event_buffer: List[DomainEvent] = []
    
    @property
    def worker_name(self) -> str:
        return "reporting_worker"
    
    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.reporting_events
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Buffer events for batch processing."""
        self.event_buffer.append(event)
        
        # Process batch when buffer is full
        if len(self.event_buffer) >= self.batch_size:
            await self._process_event_batch()
    
    async def _process_event_batch(self) -> None:
        """Process buffered events in batch."""
        if not self.event_buffer:
            return
        
        logger.info(
            "Processing event batch for reporting",
            batch_size=len(self.event_buffer),
        )
        
        # Group events by type
        events_by_type = {}
        for event in self.event_buffer:
            if event.event_type not in events_by_type:
                events_by_type[event.event_type] = []
            events_by_type[event.event_type].append(event)
        
        # Process each event type
        for event_type, events in events_by_type.items():
            if event_type == "Trading.Trade.Executed.v1":
                await self._update_trading_metrics(events)
            elif event_type == "Trading.Position.Closed.v1":
                await self._update_position_metrics(events)
            elif event_type == "Challenge.Completed.v1":
                await self._update_challenge_metrics(events)
            elif event_type == "Risk.Limit.Breached.v1":
                await self._update_risk_metrics(events)
        
        # Clear buffer
        self.event_buffer.clear()
    
    async def _update_trading_metrics(self, events: List[DomainEvent]) -> None:
        """Update trading metrics from trade events."""
        total_volume = 0
        trade_count = len(events)
        
        for event in events:
            quantity = getattr(event, "quantity", 0)
            price = getattr(event, "price", 0)
            total_volume += quantity * price
        
        logger.info(
            "Trading metrics updated",
            trade_count=trade_count,
            total_volume=total_volume,
        )
    
    async def _update_position_metrics(self, events: List[DomainEvent]) -> None:
        """Update position metrics from position events."""
        total_pnl = 0
        position_count = len(events)
        
        for event in events:
            realized_pnl = getattr(event, "realized_pnl", 0)
            total_pnl += float(realized_pnl) if realized_pnl else 0
        
        logger.info(
            "Position metrics updated",
            position_count=position_count,
            total_pnl=total_pnl,
        )
    
    async def _update_challenge_metrics(self, events: List[DomainEvent]) -> None:
        """Update challenge metrics from challenge events."""
        completion_count = len(events)
        
        logger.info(
            "Challenge metrics updated",
            completion_count=completion_count,
        )
    
    async def _update_risk_metrics(self, events: List[DomainEvent]) -> None:
        """Update risk metrics from risk events."""
        breach_count = len(events)
        
        # Group by limit type
        breaches_by_type = {}
        for event in events:
            limit_type = getattr(event, "limit_type", "unknown")
            breaches_by_type[limit_type] = breaches_by_type.get(limit_type, 0) + 1
        
        logger.info(
            "Risk metrics updated",
            breach_count=breach_count,
            breaches_by_type=breaches_by_type,
        )
    
    async def _cleanup(self) -> None:
        """Process remaining events in buffer before shutdown."""
        if self.event_buffer:
            await self._process_event_batch()


class IntegrationWorker(EventWorker):
    """Worker for handling external system integrations."""
    
    def __init__(self, worker_id: Optional[str] = None):
        super().__init__(worker_id)
        self.integration_events = {
            "Trading.Trade.Executed.v1",
            "Challenge.Completed.v1",
            "Risk.Limit.Breached.v1",
        }
    
    @property
    def worker_name(self) -> str:
        return "integration_worker"
    
    @property
    def max_retries(self) -> int:
        return 5  # More retries for external integrations
    
    @property
    def retry_delay_seconds(self) -> int:
        return 10  # Longer delay for external systems
    
    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.integration_events
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle external system integrations."""
        logger.info(
            "Processing integration event",
            event_type=event.event_type,
            event_id=str(event.event_id),
        )
        
        if event.event_type == "Trading.Trade.Executed.v1":
            await self._sync_trade_to_external_system(event)
        elif event.event_type == "Challenge.Completed.v1":
            await self._notify_external_challenge_system(event)
        elif event.event_type == "Risk.Limit.Breached.v1":
            await self._alert_external_risk_system(event)
    
    async def _sync_trade_to_external_system(self, event: DomainEvent) -> None:
        """Sync trade data to external trading system."""
        trade_data = {
            "trade_id": getattr(event, "trade_id", None),
            "user_id": getattr(event, "user_id", None),
            "symbol": getattr(event, "symbol", None),
            "quantity": getattr(event, "quantity", None),
            "price": getattr(event, "price", None),
            "timestamp": event.occurred_at.isoformat(),
        }
        
        # Simulate external API call
        await asyncio.sleep(0.1)  # Simulate network delay
        
        logger.info(
            "Trade synced to external system",
            trade_id=trade_data["trade_id"],
        )
    
    async def _notify_external_challenge_system(self, event: DomainEvent) -> None:
        """Notify external challenge management system."""
        challenge_data = {
            "challenge_id": getattr(event, "challenge_id", None),
            "user_id": getattr(event, "user_id", None),
            "completion_time": event.occurred_at.isoformat(),
        }
        
        # Simulate external API call
        await asyncio.sleep(0.1)
        
        logger.info(
            "Challenge completion notified to external system",
            challenge_id=challenge_data["challenge_id"],
        )
    
    async def _alert_external_risk_system(self, event: DomainEvent) -> None:
        """Alert external risk management system."""
        risk_data = {
            "user_id": getattr(event, "user_id", None),
            "limit_type": getattr(event, "limit_type", None),
            "breach_time": event.occurred_at.isoformat(),
        }
        
        # Simulate external API call
        await asyncio.sleep(0.1)
        
        logger.info(
            "Risk breach alerted to external system",
            user_id=risk_data["user_id"],
            limit_type=risk_data["limit_type"],
        )