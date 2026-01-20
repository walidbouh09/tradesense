"""
Example demonstrating TradeSense AI infrastructure usage.

This example shows how to use the core infrastructure components together
in a realistic financial application scenario.
"""

import asyncio
from datetime import datetime
from uuid import UUID, uuid4

from src.infrastructure import (
    # Configuration
    get_settings,
    
    # Database
    DatabaseConnectionManager,
    DatabaseSessionManager,
    TransactionManager,
    
    # Security
    JWTManager,
    RoleBasedAccessControl,
    SecureHasher,
    
    # Messaging
    InMemoryEventBus,
    EventHandler,
    
    # Logging
    configure_logging,
    get_logger,
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    
    # Context
    ExecutionContext,
    AuditContext,
    
    # Decorators
    with_execution_context,
    with_audit_context,
    with_retry,
    with_performance_monitoring,
)
from src.shared.kernel.events import DomainEvent


class OrderPlacedEvent(DomainEvent):
    """Example domain event for order placement."""
    
    def __init__(self, aggregate_id: UUID, user_id: UUID, symbol: str, quantity: str):
        super().__init__(
            aggregate_id=aggregate_id,
            user_id=user_id,
            symbol=symbol,
            quantity=quantity,
        )


class AuditEventHandler(EventHandler):
    """Example event handler for audit logging."""
    
    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
    
    async def handle(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Handle domain event by creating audit log entry."""
        await self.audit_logger.log_business_event(
            event_type=AuditEventType.ORDER_PLACED,
            user_id=event.user_id,
            resource_type="order",
            resource_id=event.aggregate_id,
            action="place_order",
            details=event.to_dict(),
            execution_context=context,
        )
    
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if handler can handle this event type."""
        return event.event_type == "OrderPlaced"
    
    @property
    def handler_name(self) -> str:
        """Get handler name."""
        return "audit_event_handler"


class TradingService:
    """Example trading service using infrastructure components."""
    
    def __init__(
        self,
        session_manager: DatabaseSessionManager,
        transaction_manager: TransactionManager,
        jwt_manager: JWTManager,
        rbac: RoleBasedAccessControl,
        event_bus: InMemoryEventBus,
        audit_logger: AuditLogger,
    ):
        self.session_manager = session_manager
        self.transaction_manager = transaction_manager
        self.jwt_manager = jwt_manager
        self.rbac = rbac
        self.event_bus = event_bus
        self.audit_logger = audit_logger
        self.logger = get_logger("trading_service")
    
    @with_execution_context("place_order")
    @with_audit_context("order", "place", "User requested order placement")
    @with_performance_monitoring(slow_threshold_ms=500)
    @with_retry(max_attempts=3, exceptions=(Exception,))
    async def place_order(
        self,
        user_id: UUID,
        symbol: str,
        quantity: str,
        price: str,
    ) -> UUID:
        """Place a trading order with full infrastructure integration."""
        
        # Get execution context
        execution_context = ExecutionContext.create_for_system("place_order")
        
        # Check permissions
        from src.infrastructure.security.authorization import ResourceType, Action
        await self.rbac.require_permission(
            user_id=user_id,
            resource=ResourceType.ORDER,
            action=Action.CREATE,
            execution_context=execution_context,
        )
        
        # Generate order ID
        order_id = uuid4()
        
        self.logger.info(
            "Placing order",
            user_id=str(user_id),
            order_id=str(order_id),
            symbol=symbol,
            quantity=quantity,
            price=price,
        )
        
        # Execute in transaction
        async with self.transaction_manager.transaction(execution_context) as session:
            # Simulate database operations
            self.logger.debug("Saving order to database", order_id=str(order_id))
            
            # Create and publish domain event
            event = OrderPlacedEvent(
                aggregate_id=order_id,
                user_id=user_id,
                symbol=symbol,
                quantity=quantity,
            )
            
            await self.event_bus.publish(event, context=execution_context)
            
            # Log business event
            await self.audit_logger.log_business_event(
                event_type=AuditEventType.ORDER_PLACED,
                user_id=user_id,
                resource_type="order",
                resource_id=order_id,
                action="place_order",
                details={
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                },
                execution_context=execution_context,
                business_justification="User requested order placement",
            )
        
        self.logger.info("Order placed successfully", order_id=str(order_id))
        return order_id
    
    @with_execution_context("authenticate_user")
    @with_performance_monitoring()
    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str,
    ) -> tuple[str, str]:
        """Authenticate user and return access/refresh tokens."""
        
        execution_context = ExecutionContext.create_for_system("authenticate_user")
        
        # Simulate user lookup and password verification
        user_id = uuid4()  # In real implementation, lookup from database
        
        # Hash and verify password
        hasher = SecureHasher(get_settings().security)
        # In real implementation, get stored hash from database
        stored_hash = hasher.hash_password(password)  # Simulate stored hash
        
        if not hasher.verify_password(password, stored_hash):
            # Log failed authentication
            await self.audit_logger.log_authentication_event(
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=None,
                success=False,
                ip_address=ip_address,
                failure_reason="Invalid password",
                execution_context=execution_context,
            )
            raise Exception("Invalid credentials")
        
        # Create tokens
        permissions = ["order:create", "order:read", "position:read"]
        access_token = await self.jwt_manager.create_access_token(
            user_id=user_id,
            permissions=permissions,
            execution_context=execution_context,
        )
        
        refresh_token = await self.jwt_manager.create_refresh_token(
            user_id=user_id,
            execution_context=execution_context,
        )
        
        # Log successful authentication
        await self.audit_logger.log_authentication_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            execution_context=execution_context,
        )
        
        self.logger.info(
            "User authenticated successfully",
            user_id=str(user_id),
            ip_address=ip_address,
        )
        
        return access_token, refresh_token


async def main():
    """Main example function demonstrating infrastructure usage."""
    
    # Load configuration
    settings = get_settings()
    
    # Configure logging
    configure_logging(settings.logging)
    logger = get_logger("example")
    
    logger.info("Starting TradeSense AI infrastructure example")
    
    # Initialize database components
    db_manager = DatabaseConnectionManager(settings.database)
    await db_manager.initialize()
    
    session_manager = DatabaseSessionManager(db_manager)
    await session_manager.initialize()
    
    transaction_manager = TransactionManager(session_manager)
    
    # Initialize security components
    jwt_manager = JWTManager(settings.security)
    rbac = RoleBasedAccessControl()
    
    # Initialize messaging
    event_bus = InMemoryEventBus(enable_event_store=True)
    await event_bus.start()
    
    # Initialize audit logging
    audit_logger = AuditLogger(settings.security.encryption_key.get_secret_value())
    
    # Set up event handler
    audit_handler = AuditEventHandler(audit_logger)
    await event_bus.subscribe("OrderPlaced", audit_handler)
    
    # Create trading service
    trading_service = TradingService(
        session_manager=session_manager,
        transaction_manager=transaction_manager,
        jwt_manager=jwt_manager,
        rbac=rbac,
        event_bus=event_bus,
        audit_logger=audit_logger,
    )
    
    try:
        # Example 1: User authentication
        logger.info("Example 1: User authentication")
        access_token, refresh_token = await trading_service.authenticate_user(
            username="trader1",
            password="SecurePassword123!",
            ip_address="192.168.1.100",
        )
        
        # Validate token
        token_payload = await jwt_manager.validate_token(access_token)
        logger.info("Token validated", user_id=token_payload.sub)
        
        # Example 2: Place order
        logger.info("Example 2: Place trading order")
        order_id = await trading_service.place_order(
            user_id=token_payload.user_id,
            symbol="EURUSD",
            quantity="10000",
            price="1.0850",
        )
        
        logger.info("Order placed", order_id=str(order_id))
        
        # Example 3: Check event bus metrics
        logger.info("Example 3: Event bus metrics")
        metrics = event_bus.get_metrics()
        logger.info(
            "Event bus metrics",
            events_published=metrics.events_published,
            events_processed=metrics.events_processed,
            events_failed=metrics.events_failed,
        )
        
        # Example 4: Database health check
        logger.info("Example 4: Database health check")
        health_status = await db_manager.get_health_status()
        logger.info("Database health", **health_status)
        
        # Example 5: Generate compliance report
        logger.info("Example 5: Generate compliance report")
        report = await audit_logger.generate_compliance_report(
            start_date=datetime.utcnow().replace(hour=0, minute=0, second=0),
            end_date=datetime.utcnow(),
        )
        logger.info("Compliance report generated", report_id=report["report_id"])
        
    except Exception as e:
        logger.error("Example execution failed", error=str(e))
        raise
    
    finally:
        # Cleanup
        logger.info("Cleaning up infrastructure components")
        await event_bus.stop()
        await db_manager.close()
    
    logger.info("TradeSense AI infrastructure example completed")


if __name__ == "__main__":
    asyncio.run(main())