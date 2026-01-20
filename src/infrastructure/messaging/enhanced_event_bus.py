"""Enhanced event bus with worker support and advanced features."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from ...shared.kernel.events import DomainEvent
from ..common.context import ExecutionContext
from ..common.exceptions import EventBusError, EventHandlingError
from .event_bus import EventBus, EventBusHealth, EventHandler, EventSubscription

logger = structlog.get_logger()


class WorkerStatus(Enum):
    """Worker status enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class WorkerMetrics(BaseModel):
    """Worker performance metrics."""
    events_processed: int = 0
    events_failed: int = 0
    average_processing_time_ms: float = 0.0
    last_processed_at: Optional[datetime] = None
    uptime_seconds: int = 0
    memory_usage_mb: float = 0.0


class EventWorker(ABC):
    """Base class for all event workers."""
    
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or str(uuid4())
        self.status = WorkerStatus.STOPPED
        self.metrics = WorkerMetrics()
        self.started_at: Optional[datetime] = None
        self._stop_event = asyncio.Event()
    
    @abstractmethod
    async def process_event(self, event: DomainEvent, context: ExecutionContext) -> None:
        """Process a single event."""
        pass
    
    @abstractmethod
    def can_handle(self, event: DomainEvent) -> bool:
        """Check if worker can handle this event type."""
        pass
    
    @property
    @abstractmethod
    def worker_name(self) -> str:
        """Unique worker identifier."""
        pass
    
    @property
    def max_retries(self) -> int:
        """Maximum retry attempts."""
        return 3
    
    @property
    def retry_delay_seconds(self) -> int:
        """Base delay between retries."""
        return 5
    
    @property
    def consumer_group(self) -> str:
        """Consumer group for load balancing."""
        return f"{self.worker_name}_group"
    
    @property
    def batch_size(self) -> int:
        """Number of events to process in batch."""
        return 10
    
    @property
    def processing_timeout_seconds(self) -> int:
        """Timeout for processing single event."""
        return 30
    
    async def start(self) -> None:
        """Start the worker."""
        if self.status != WorkerStatus.STOPPED:
            return
        
        self.status = WorkerStatus.STARTING
        self.started_at = datetime.utcnow()
        self._stop_event.clear()
        
        logger.info(
            "Worker starting",
            worker_name=self.worker_name,
            worker_id=self.worker_id,
        )
        
        try:
            await self._initialize()
            self.status = WorkerStatus.RUNNING
            
            logger.info(
                "Worker started",
                worker_name=self.worker_name,
                worker_id=self.worker_id,
            )
        except Exception as e:
            self.status = WorkerStatus.ERROR
            logger.error(
                "Worker failed to start",
                worker_name=self.worker_name,
                worker_id=self.worker_id,
                error=str(e),
            )
            raise
    
    async def stop(self) -> None:
        """Stop the worker."""
        if self.status in [WorkerStatus.STOPPED, WorkerStatus.STOPPING]:
            return
        
        self.status = WorkerStatus.STOPPING
        self._stop_event.set()
        
        logger.info(
            "Worker stopping",
            worker_name=self.worker_name,
            worker_id=self.worker_id,
        )
        
        try:
            await self._cleanup()
            self.status = WorkerStatus.STOPPED
            
            logger.info(
                "Worker stopped",
                worker_name=self.worker_name,
                worker_id=self.worker_id,
            )
        except Exception as e:
            self.status = WorkerStatus.ERROR
            logger.error(
                "Worker failed to stop cleanly",
                worker_name=self.worker_name,
                worker_id=self.worker_id,
                error=str(e),
            )
    
    async def _initialize(self) -> None:
        """Initialize worker resources."""
        pass
    
    async def _cleanup(self) -> None:
        """Cleanup worker resources."""
        pass
    
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self.status == WorkerStatus.RUNNING
    
    def should_stop(self) -> bool:
        """Check if worker should stop."""
        return self._stop_event.is_set()
    
    def update_metrics(self, processing_time_ms: float, success: bool) -> None:
        """Update worker metrics."""
        if success:
            self.metrics.events_processed += 1
        else:
            self.metrics.events_failed += 1
        
        # Update average processing time
        if self.metrics.events_processed == 1:
            self.metrics.average_processing_time_ms = processing_time_ms
        else:
            alpha = 0.1  # Exponential moving average factor
            self.metrics.average_processing_time_ms = (
                alpha * processing_time_ms + 
                (1 - alpha) * self.metrics.average_processing_time_ms
            )
        
        self.metrics.last_processed_at = datetime.utcnow()
        
        # Update uptime
        if self.started_at:
            self.metrics.uptime_seconds = int(
                (datetime.utcnow() - self.started_at).total_seconds()
            )


class WorkerRegistry:
    """Registry for managing event workers."""
    
    def __init__(self):
        self.workers: Dict[str, EventWorker] = {}
        self.workers_by_event_type: Dict[str, List[EventWorker]] = {}
    
    def register_worker(self, worker: EventWorker) -> None:
        """Register a worker."""
        self.workers[worker.worker_id] = worker
        
        logger.info(
            "Worker registered",
            worker_name=worker.worker_name,
            worker_id=worker.worker_id,
        )
    
    def unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker."""
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            del self.workers[worker_id]
            
            # Remove from event type mappings
            for event_type, workers in self.workers_by_event_type.items():
                self.workers_by_event_type[event_type] = [
                    w for w in workers if w.worker_id != worker_id
                ]
            
            logger.info(
                "Worker unregistered",
                worker_name=worker.worker_name,
                worker_id=worker_id,
            )
    
    def get_workers_for_event(self, event: DomainEvent) -> List[EventWorker]:
        """Get workers that can handle the event."""
        return [
            worker for worker in self.workers.values()
            if worker.can_handle(event) and worker.is_running()
        ]
    
    def get_all_workers(self) -> List[EventWorker]:
        """Get all registered workers."""
        return list(self.workers.values())
    
    def get_worker_by_id(self, worker_id: str) -> Optional[EventWorker]:
        """Get worker by ID."""
        return self.workers.get(worker_id)
    
    async def start_all_workers(self) -> None:
        """Start all registered workers."""
        tasks = []
        for worker in self.workers.values():
            if worker.status == WorkerStatus.STOPPED:
                tasks.append(asyncio.create_task(worker.start()))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all_workers(self) -> None:
        """Stop all registered workers."""
        tasks = []
        for worker in self.workers.values():
            if worker.is_running():
                tasks.append(asyncio.create_task(worker.stop()))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class CircuitBreaker:
    """Circuit breaker for handling service failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        expected_exception: Type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise EventHandlingError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if not self.last_failure_time:
            return True
        
        return (
            datetime.utcnow() - self.last_failure_time
        ).total_seconds() > self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful execution."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class EnhancedEventBus(EventBus):
    """Enhanced event bus with worker support and advanced features."""
    
    def __init__(self):
        super().__init__()
        self.worker_registry = WorkerRegistry()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._worker_tasks: Set[asyncio.Task] = set()
    
    async def register_worker(self, worker: EventWorker) -> None:
        """Register an event worker."""
        self.worker_registry.register_worker(worker)
        
        # Create circuit breaker for worker
        self.circuit_breakers[worker.worker_id] = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=60,
        )
        
        # Start worker if bus is running
        if self._running:
            await worker.start()
    
    async def unregister_worker(self, worker_id: str) -> None:
        """Unregister an event worker."""
        worker = self.worker_registry.get_worker_by_id(worker_id)
        if worker and worker.is_running():
            await worker.stop()
        
        self.worker_registry.unregister_worker(worker_id)
        
        if worker_id in self.circuit_breakers:
            del self.circuit_breakers[worker_id]
    
    async def publish(
        self,
        event: DomainEvent,
        routing_key: Optional[str] = None,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Publish event to workers."""
        if not self._running:
            raise EventBusError("Event bus is not running")
        
        # Get workers that can handle this event
        workers = self.worker_registry.get_workers_for_event(event)
        
        if not workers:
            logger.debug(
                "No workers available for event",
                event_type=event.event_type,
                event_id=str(event.event_id),
            )
            return
        
        # Create execution context if not provided
        if context is None:
            context = ExecutionContext.create_for_worker("enhanced_event_bus")
        
        # Process event with each worker
        tasks = []
        for worker in workers:
            circuit_breaker = self.circuit_breakers.get(worker.worker_id)
            if circuit_breaker:
                task = asyncio.create_task(
                    self._process_event_with_worker(event, worker, circuit_breaker, context)
                )
                tasks.append(task)
                self._worker_tasks.add(task)
        
        # Wait for all workers to process
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Worker failed to process event",
                        event_type=event.event_type,
                        event_id=str(event.event_id),
                        worker_id=workers[i].worker_id,
                        error=str(result),
                    )
        
        # Clean up completed tasks
        self._worker_tasks = {
            task for task in self._worker_tasks if not task.done()
        }
        
        # Update metrics
        self.metrics.events_published += 1
        self.metrics.last_event_timestamp = datetime.utcnow()
    
    async def _process_event_with_worker(
        self,
        event: DomainEvent,
        worker: EventWorker,
        circuit_breaker: CircuitBreaker,
        context: ExecutionContext,
    ) -> None:
        """Process event with a specific worker."""
        start_time = datetime.utcnow()
        
        try:
            # Use circuit breaker to protect against failing workers
            await circuit_breaker.call(
                self._execute_worker_with_timeout,
                worker,
                event,
                context,
            )
            
            # Update worker metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            worker.update_metrics(processing_time, success=True)
            
            logger.debug(
                "Worker processed event successfully",
                event_type=event.event_type,
                event_id=str(event.event_id),
                worker_id=worker.worker_id,
                processing_time_ms=processing_time,
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            worker.update_metrics(processing_time, success=False)
            
            logger.error(
                "Worker failed to process event",
                event_type=event.event_type,
                event_id=str(event.event_id),
                worker_id=worker.worker_id,
                error=str(e),
            )
            raise
    
    async def _execute_worker_with_timeout(
        self,
        worker: EventWorker,
        event: DomainEvent,
        context: ExecutionContext,
    ) -> None:
        """Execute worker with timeout protection."""
        try:
            await asyncio.wait_for(
                worker.process_event(event, context),
                timeout=worker.processing_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise EventHandlingError(
                f"Worker {worker.worker_id} timed out processing event"
            )
    
    async def start(self) -> None:
        """Start the enhanced event bus."""
        await super().start()
        await self.worker_registry.start_all_workers()
        
        logger.info(
            "Enhanced event bus started",
            worker_count=len(self.worker_registry.get_all_workers()),
        )
    
    async def stop(self) -> None:
        """Stop the enhanced event bus."""
        # Stop all workers
        await self.worker_registry.stop_all_workers()
        
        # Wait for worker tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()
        
        await super().stop()
        
        logger.info("Enhanced event bus stopped")
    
    def get_worker_metrics(self) -> Dict[str, WorkerMetrics]:
        """Get metrics for all workers."""
        return {
            worker.worker_id: worker.metrics
            for worker in self.worker_registry.get_all_workers()
        }
    
    def get_circuit_breaker_status(self) -> Dict[str, str]:
        """Get circuit breaker status for all workers."""
        return {
            worker_id: breaker.state
            for worker_id, breaker in self.circuit_breakers.items()
        }