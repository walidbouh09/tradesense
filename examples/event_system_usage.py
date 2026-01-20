"""
Event System Usage Examples

This file demonstrates how to use the TradeSense AI event-driven system
for publishing domain events and processing them with workers.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from src.infrastructure.messaging.enhanced_event_bus import EnhancedEventBus
from src.infrastructure.messaging.worker_implementations import (
    AuditLogWorker,
    IntegrationWorker,
    NotificationWorker,
    ReportingWorker,
    RiskMonitoringWorker,
)
from src.shared.events.domain_events import (
    TradingPositionOpenedEvent,
    TradingTradeExecutedEvent,
    RiskLimitBreachedEvent,
    ChallengeCompletedEvent,
    AuthUserLoggedInEvent,
)


async def example_1_basic_event_publishing():
    """Example 1: Basic event publishing and processing."""
    
    print("=== Example 1: Basic Event Publishing ===")
    
    # Create enhanced event bus
    event_bus = EnhancedEventBus()
    
    # Register workers
    audit_worker = AuditLogWorker()
    notification_worker = NotificationWorker()
    
    await event_bus.register_worker(audit_worker)
    await event_bus.register_worker(notification_worker)
    
    # Start event bus
    await event_bus.start()
    
    print(f"📊 Event bus started with {len(event_bus.worker_registry.get_all_workers())} workers")
    
    # Create and publish events
    user_id = uuid4()
    challenge_id = uuid4()
    
    # Trading position opened event
    position_event = TradingPositionOpenedEvent(
        aggregate_id=user_id,
        position_id=uuid4(),
        user_id=user_id,
        symbol="EURUSD",
        size=Decimal("100000"),
        entry_price=Decimal("1.0850"),
        side="long",
        leverage=Decimal("100"),
    )
    
    await event_bus.publish(position_event)
    print(f"📈 Published position opened event: {position_event.event_id}")
    
    # Risk limit breached event
    risk_event = RiskLimitBreachedEvent(
        aggregate_id=user_id,
        user_id=user_id,
        challenge_id=challenge_id,
        limit_type="daily_loss",
        current_value=Decimal("5500"),
        limit_value=Decimal("5000"),
        severity="critical",
    )
    
    await event_bus.publish(risk_event)
    print(f"⚠️ Published risk limit breached event: {risk_event.event_id}")
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    # Check audit log
    audit_events = audit_worker.get_audit_events()
    print(f"📝 Audit log contains {len(audit_events)} events")
    
    # Stop event bus
    await event_bus.stop()
    print("🛑 Event bus stopped")


async def example_2_worker_metrics_and_monitoring():
    """Example 2: Worker metrics and monitoring."""
    
    print("\n=== Example 2: Worker Metrics and Monitoring ===")
    
    # Create event bus with multiple workers
    event_bus = EnhancedEventBus()
    
    # Register different types of workers
    workers = [
        AuditLogWorker(),
        NotificationWorker(),
        ReportingWorker(),
        IntegrationWorker(),
    ]
    
    for worker in workers:
        await event_bus.register_worker(worker)
    
    await event_bus.start()
    
    print(f"🔧 Started event bus with {len(workers)} workers")
    
    # Publish multiple events to generate metrics
    events = []
    
    # Create various event types
    user_id = uuid4()
    
    # Trading events
    for i in range(5):
        trade_event = TradingTradeExecutedEvent(
            aggregate_id=user_id,
            trade_id=uuid4(),
            user_id=user_id,
            symbol=f"SYMBOL{i}",
            quantity=Decimal("1000"),
            price=Decimal("100.50"),
            side="buy",
            order_type="market",
            commission=Decimal("2.50"),
        )
        events.append(trade_event)
    
    # Challenge completion event
    challenge_event = ChallengeCompletedEvent(
        aggregate_id=user_id,
        challenge_id=uuid4(),
        user_id=user_id,
        challenge_type="PHASE_1",
        final_balance=Decimal("110000"),
        profit_achieved=Decimal("10000"),
        completion_time_days=25,
    )
    events.append(challenge_event)
    
    # Login event
    login_event = AuthUserLoggedInEvent(
        aggregate_id=user_id,
        user_id=user_id,
        session_id=uuid4(),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    )
    events.append(login_event)
    
    # Publish all events
    for event in events:
        await event_bus.publish(event)
        print(f"📤 Published {event.event_type}: {event.event_id}")
    
    # Wait for processing
    await asyncio.sleep(0.2)
    
    # Display worker metrics
    worker_metrics = event_bus.get_worker_metrics()
    
    print("\n📊 Worker Metrics:")
    for worker_id, metrics in worker_metrics.items():
        worker = event_bus.worker_registry.get_worker_by_id(worker_id)
        print(f"  {worker.worker_name}:")
        print(f"    Events Processed: {metrics.events_processed}")
        print(f"    Events Failed: {metrics.events_failed}")
        print(f"    Avg Processing Time: {metrics.average_processing_time_ms:.2f}ms")
        print(f"    Uptime: {metrics.uptime_seconds}s")
    
    # Display circuit breaker status
    circuit_status = event_bus.get_circuit_breaker_status()
    print("\n🔌 Circuit Breaker Status:")
    for worker_id, status in circuit_status.items():
        worker = event_bus.worker_registry.get_worker_by_id(worker_id)
        print(f"  {worker.worker_name}: {status}")
    
    await event_bus.stop()


async def example_3_error_handling_and_retries():
    """Example 3: Error handling and retry mechanisms."""
    
    print("\n=== Example 3: Error Handling and Retries ===")
    
    # Create a custom worker that fails sometimes
    class FailingWorker(AuditLogWorker):
        def __init__(self):
            super().__init__()
            self.failure_count = 0
        
        @property
        def worker_name(self) -> str:
            return "failing_worker"
        
        async def process_event(self, event, context):
            self.failure_count += 1
            
            # Fail first 2 attempts, succeed on 3rd
            if self.failure_count <= 2:
                print(f"💥 Worker failing (attempt {self.failure_count})")
                raise Exception(f"Simulated failure #{self.failure_count}")
            
            print(f"✅ Worker succeeded on attempt {self.failure_count}")
            await super().process_event(event, context)
    
    event_bus = EnhancedEventBus()
    failing_worker = FailingWorker()
    
    await event_bus.register_worker(failing_worker)
    await event_bus.start()
    
    # Publish an event that will trigger retries
    test_event = TradingTradeExecutedEvent(
        aggregate_id=uuid4(),
        trade_id=uuid4(),
        user_id=uuid4(),
        symbol="TESTFAIL",
        quantity=Decimal("1000"),
        price=Decimal("100.00"),
        side="buy",
        order_type="market",
        commission=Decimal("2.00"),
    )
    
    print("📤 Publishing event that will trigger retries...")
    
    try:
        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)
        
        # Check metrics
        metrics = event_bus.get_worker_metrics()
        worker_metrics = metrics[failing_worker.worker_id]
        
        print(f"📊 Final metrics:")
        print(f"  Events Processed: {worker_metrics.events_processed}")
        print(f"  Events Failed: {worker_metrics.events_failed}")
        
    except Exception as e:
        print(f"❌ Event processing failed: {e}")
    
    await event_bus.stop()


async def example_4_batch_processing():
    """Example 4: Batch processing with reporting worker."""
    
    print("\n=== Example 4: Batch Processing ===")
    
    event_bus = EnhancedEventBus()
    reporting_worker = ReportingWorker()
    
    await event_bus.register_worker(reporting_worker)
    await event_bus.start()
    
    print("📊 Starting batch processing example...")
    
    # Generate many trading events to trigger batch processing
    user_id = uuid4()
    
    print("📈 Publishing 60 trading events to trigger batch processing...")
    
    for i in range(60):  # More than batch size (50) to trigger processing
        trade_event = TradingTradeExecutedEvent(
            aggregate_id=user_id,
            trade_id=uuid4(),
            user_id=user_id,
            symbol=f"PAIR{i % 10}",
            quantity=Decimal("1000"),
            price=Decimal(f"{100 + i}"),
            side="buy" if i % 2 == 0 else "sell",
            order_type="market",
            commission=Decimal("2.50"),
        )
        
        await event_bus.publish(trade_event)
        
        if (i + 1) % 10 == 0:
            print(f"  📤 Published {i + 1} events...")
    
    # Wait for batch processing
    await asyncio.sleep(0.5)
    
    # Check worker metrics
    metrics = event_bus.get_worker_metrics()
    worker_metrics = metrics[reporting_worker.worker_id]
    
    print(f"📊 Reporting worker processed {worker_metrics.events_processed} events")
    print(f"⏱️ Average processing time: {worker_metrics.average_processing_time_ms:.2f}ms")
    
    await event_bus.stop()


async def example_5_event_filtering_and_routing():
    """Example 5: Event filtering and routing to specific workers."""
    
    print("\n=== Example 5: Event Filtering and Routing ===")
    
    # Create specialized workers for different event types
    class TradingOnlyWorker(AuditLogWorker):
        @property
        def worker_name(self) -> str:
            return "trading_only_worker"
        
        def can_handle(self, event):
            return event.event_type.startswith("Trading.")
    
    class RiskOnlyWorker(AuditLogWorker):
        @property
        def worker_name(self) -> str:
            return "risk_only_worker"
        
        def can_handle(self, event):
            return event.event_type.startswith("Risk.")
    
    event_bus = EnhancedEventBus()
    
    trading_worker = TradingOnlyWorker()
    risk_worker = RiskOnlyWorker()
    general_worker = AuditLogWorker()  # Handles all events
    
    await event_bus.register_worker(trading_worker)
    await event_bus.register_worker(risk_worker)
    await event_bus.register_worker(general_worker)
    
    await event_bus.start()
    
    print("🎯 Testing event routing to specialized workers...")
    
    # Publish different types of events
    user_id = uuid4()
    
    # Trading event - should go to trading_worker and general_worker
    trading_event = TradingTradeExecutedEvent(
        aggregate_id=user_id,
        trade_id=uuid4(),
        user_id=user_id,
        symbol="EURUSD",
        quantity=Decimal("1000"),
        price=Decimal("1.0850"),
        side="buy",
        order_type="market",
        commission=Decimal("2.50"),
    )
    
    # Risk event - should go to risk_worker and general_worker
    risk_event = RiskLimitBreachedEvent(
        aggregate_id=user_id,
        user_id=user_id,
        challenge_id=uuid4(),
        limit_type="daily_loss",
        current_value=Decimal("5500"),
        limit_value=Decimal("5000"),
        severity="warning",
    )
    
    # Auth event - should only go to general_worker
    auth_event = AuthUserLoggedInEvent(
        aggregate_id=user_id,
        user_id=user_id,
        session_id=uuid4(),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0",
    )
    
    await event_bus.publish(trading_event)
    await event_bus.publish(risk_event)
    await event_bus.publish(auth_event)
    
    await asyncio.sleep(0.1)
    
    # Check which workers processed which events
    metrics = event_bus.get_worker_metrics()
    
    print("📊 Event routing results:")
    for worker_id, worker_metrics in metrics.items():
        worker = event_bus.worker_registry.get_worker_by_id(worker_id)
        print(f"  {worker.worker_name}: {worker_metrics.events_processed} events")
    
    await event_bus.stop()


async def main():
    """Run all examples."""
    print("🚀 TradeSense AI Event System Examples\n")
    
    await example_1_basic_event_publishing()
    await example_2_worker_metrics_and_monitoring()
    await example_3_error_handling_and_retries()
    await example_4_batch_processing()
    await example_5_event_filtering_and_routing()
    
    print("\n✅ All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())