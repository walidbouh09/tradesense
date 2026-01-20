"""Risk monitoring worker for real-time risk assessment."""

from typing import List
from uuid import UUID
import structlog

from ...infrastructure.messaging.enhanced_event_bus import BaseEventWorker, TransientError, PermanentError
from ...infrastructure.common.context import ExecutionContext
from ...shared.kernel.events import DomainEvent
from ...shared.events.domain_events import (
    TradingPositionOpenedV1,
    TradingPositionClosedV1,
    TradingOrderFilledV1,
    TradingPnLUpdatedV1,
)
from ...domains.risk.application.services import RiskMonitoringService

logger = structlog.get_logger()


class RiskMonitoringWorker(BaseEventWorker):
    """Worker for real-time risk monitoring and assessment."""
    
    def __init__(
        self,
        event_bus,
        risk_monitoring_service: RiskMonitoringService,
    ):
        super().__init__(
            worker_name="risk_monitoring",
            event_bus=event_bus,
            concurrency=5,  # High concurrency for real-time processing
            batch_size=1,   # Process immediately for risk monitoring
        )
        self.risk_service = risk_monitoring_service
        self.logger = logger.bind(worker="risk_monitoring")
    
    def get_subscribed_events(self) -> List[str]:
        """Subscribe to trading events that affect risk."""
        return [
            "TradingPositionOpenedV1",
            "TradingPositionClosedV1", 
            "TradingOrderFilledV1",
            "TradingPnLUpdatedV1",
        ]
    
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Process trading events for risk monitoring."""
        
        try:
            if isinstance(event, TradingPositionOpenedV1):
                await self._handle_position_opened(event, context)
            elif isinstance(event, TradingPositionClosedV1):
                await self._handle_position_closed(event, context)
            elif isinstance(event, TradingOrderFilledV1):
                await self._handle_order_filled(event, context)
            elif isinstance(event, TradingPnLUpdatedV1):
                await self._handle_pnl_updated(event, context)
            else:
                self.logger.warning(
                    "Unhandled event type",
                    event_type=event.event_type,
                    event_id=str(event.event_id)
                )
                
        except ValueError as e:
            # Data validation errors are permanent
            raise PermanentError(f"Invalid event data: {e}") from e
        except ConnectionError as e:
            # Network/database errors are transient
            raise TransientError(f"Connection error: {e}") from e
        except Exception as e:
            # Unknown errors are treated as transient by default
            self.logger.error(
                "Unexpected error processing event",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e)
            )
            raise TransientError(f"Unexpected error: {e}") from e
    
    async def _handle_position_opened(
        self,
        event: TradingPositionOpenedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle position opened event."""
        
        self.logger.info(
            "Processing position opened event",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            symbol=event.symbol,
            size=str(event.size),
            entry_price=str(event.entry_price)
        )
        
        # Update position risk metrics
        await self.risk_service.update_position_risk(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            position_data={
                "position_id": event.aggregate_id,
                "symbol": event.symbol,
                "side": event.side,
                "size": event.size,
                "entry_price": event.entry_price,
                "leverage": event.leverage,
            }
        )
        
        # Check position size limits
        await self.risk_service.check_position_size_limits(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            new_position_size=event.size,
            symbol=event.symbol,
        )
        
        # Check correlation risk
        await self.risk_service.check_correlation_risk(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            symbol=event.symbol,
        )
        
        self.logger.debug(
            "Position opened event processed",
            position_id=str(event.aggregate_id),
            user_id=str(event.user_id)
        )
    
    async def _handle_position_closed(
        self,
        event: TradingPositionClosedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle position closed event."""
        
        self.logger.info(
            "Processing position closed event",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            symbol=event.symbol,
            realized_pnl=str(event.realized_pnl),
            close_reason=event.close_reason
        )
        
        # Update position risk metrics
        await self.risk_service.remove_position_risk(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            position_id=event.aggregate_id,
        )
        
        # Update P&L risk metrics
        await self.risk_service.update_pnl_risk(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            realized_pnl=event.realized_pnl,
        )
        
        # Check if position was closed due to risk management
        if event.close_reason in ["stop_loss", "margin_call"]:
            await self.risk_service.handle_risk_closure(
                user_id=event.user_id,
                challenge_id=event.challenge_id,
                position_id=event.aggregate_id,
                close_reason=event.close_reason,
                loss_amount=event.realized_pnl,
            )
        
        self.logger.debug(
            "Position closed event processed",
            position_id=str(event.aggregate_id),
            user_id=str(event.user_id)
        )
    
    async def _handle_order_filled(
        self,
        event: TradingOrderFilledV1,
        context: ExecutionContext,
    ) -> None:
        """Handle order filled event."""
        
        self.logger.info(
            "Processing order filled event",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            symbol=event.symbol,
            quantity=str(event.quantity),
            fill_price=str(event.fill_price)
        )
        
        # Update trade frequency metrics
        await self.risk_service.update_trade_frequency(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            trade_data={
                "order_id": event.aggregate_id,
                "symbol": event.symbol,
                "side": event.side,
                "quantity": event.quantity,
                "fill_price": event.fill_price,
                "commission": event.commission,
                "timestamp": event.occurred_at,
            }
        )
        
        # Check daily trade limits
        await self.risk_service.check_daily_trade_limits(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
        )
        
        self.logger.debug(
            "Order filled event processed",
            order_id=str(event.aggregate_id),
            user_id=str(event.user_id)
        )
    
    async def _handle_pnl_updated(
        self,
        event: TradingPnLUpdatedV1,
        context: ExecutionContext,
    ) -> None:
        """Handle P&L updated event."""
        
        self.logger.info(
            "Processing P&L updated event",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id),
            current_balance=str(event.current_balance),
            daily_pnl=str(event.daily_pnl),
            total_pnl=str(event.total_pnl)
        )
        
        # Update P&L risk metrics
        await self.risk_service.update_pnl_metrics(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            pnl_data={
                "current_balance": event.current_balance,
                "daily_pnl": event.daily_pnl,
                "total_pnl": event.total_pnl,
                "unrealized_pnl": event.unrealized_pnl,
            }
        )
        
        # Check daily loss limits
        await self.risk_service.check_daily_loss_limits(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            daily_pnl=event.daily_pnl,
        )
        
        # Check total loss limits
        await self.risk_service.check_total_loss_limits(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
            total_pnl=event.total_pnl,
        )
        
        # Calculate and update overall risk score
        await self.risk_service.calculate_risk_score(
            user_id=event.user_id,
            challenge_id=event.challenge_id,
        )
        
        self.logger.debug(
            "P&L updated event processed",
            user_id=str(event.user_id),
            challenge_id=str(event.challenge_id)
        )