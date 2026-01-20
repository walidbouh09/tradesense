# TradeSense AI Event-Driven System Design

## Overview

This document outlines the design of TradeSense AI's internal event-driven system, providing a scalable, reliable, and maintainable architecture for handling domain events across all trading operations.

## Architecture Principles

- **Domain-Driven Design**: Events represent meaningful business occurrences
- **Async-First**: All event processing is asynchronous for performance
- **Pluggable Infrastructure**: Easy migration from in-memory to Redis/RabbitMQ
- **No Circular Dependencies**: Clear separation of concerns
- **Reliability**: Built-in retry, dead letter queues, and monitoring

## Event Naming Conventions

### Format: `{Domain}.{Entity}.{Action}.{Version}`

```
Examples:
- Trading.Position.Opened.v1
- Risk.Limit.Breached.v1
- Auth.User.LoggedIn.v1
- Challenge.Phase.Completed.v1
- Evaluation.Rule.Violated.v1
```

### Event Categories

#### Trading Domain Events
```
Trading.Position.Opened.v1
Trading.Position.Closed.v1
Trading.Position.Modified.v1
Trading.Order.Placed.v1
Trading.Order.Filled.v1
Trading.Order.Cancelled.v1
Trading.Trade.Executed.v1
Trading.PnL.Updated.v1
```

#### Risk Domain Events
```
Risk.Limit.Breached.v1
Risk.Alert.Triggered.v1
Risk.Score.Updated.v1
Risk.Profile.Modified.v1
Risk.Trading.Halted.v1
Risk.Trading.Resumed.v1
```

#### Challenge Domain Events
```
Challenge.Started.v1
Challenge.Completed.v1
Challenge.Failed.v1
Challenge.Phase.Advanced.v1
Challenge.Metrics.Updated.v1
```

#### Auth Domain Events
```
Auth.User.Registered.v1
Auth.User.LoggedIn.v1
Auth.User.LoggedOut.v1
Auth.Session.Expired.v1
Auth.Permission.Granted.v1
Auth.Permission.Revoked.v1
```

#### Evaluation Domain Events
```
Evaluation.Rule.Violated.v1
Evaluation.Metric.Calculated.v1
Evaluation.Report.Generated.v1
Evaluation.Status.Changed.v1
```

## Producer/Consumer Responsibilities

### Event Producers (Domain Services)
- **Responsibility**: Publish events when domain state changes
- **Location**: Domain application services
- **Rules**:
  - Publish events after successful state changes
  - Include all necessary context in event payload
  - Use domain-specific event types
  - Handle publishing failures gracefully

### Event Consumers (Workers & Handlers)
- **Responsibility**: React to events and perform side effects
- **Location**: Separate worker processes or handlers
- **Rules**:
  - Idempotent processing (handle duplicate events)
  - Fail fast with proper error handling
  - No direct domain dependencies (use event data only)
  - Implement proper retry logic

### Consumer Types

#### 1. Domain Event Handlers
- Process events within the same domain
- Update read models and projections
- Trigger domain workflows

#### 2. Integration Workers
- Handle cross-domain communication
- External system integrations
- Audit logging and compliance

#### 3. Notification Workers
- Send alerts and notifications
- Update user interfaces
- Generate reports

## Worker Design

### Base Worker Interface

```python
class EventWorker(ABC):
    """Base class for all event workers."""
    
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
```

### Worker Categories

#### 1. Real-time Workers
- Process events immediately
- Low latency requirements
- Examples: Risk monitoring, position updates

#### 2. Batch Workers
- Process events in batches
- Higher throughput
- Examples: Reporting, analytics

#### 3. Scheduled Workers
- Process events on schedule
- Examples: Daily reports, cleanup tasks

## Failure & Retry Strategy

### Retry Policies

#### 1. Exponential Backoff
```python
retry_delay = base_delay * (2 ** attempt_number)
max_delay = min(retry_delay, max_retry_delay)
```

#### 2. Circuit Breaker
- Open circuit after consecutive failures
- Half-open state for testing recovery
- Close circuit when service recovers

#### 3. Dead Letter Queue
- Store events that exceed max retries
- Manual processing and investigation
- Replay capability for recovered services

### Error Categories

#### 1. Transient Errors (Retry)
- Network timeouts
- Database connection issues
- Temporary service unavailability

#### 2. Permanent Errors (Dead Letter)
- Invalid event format
- Business rule violations
- Missing required data

#### 3. Poison Messages (Skip)
- Malformed events
- Corrupted data
- Security violations

## Implementation Components

### 1. Event Bus Abstraction
- Pluggable implementations (In-Memory, Redis, RabbitMQ)
- Reliable delivery guarantees
- Monitoring and metrics

### 2. Worker Registry
- Dynamic worker registration
- Load balancing across instances
- Health monitoring

### 3. Event Store
- Event sourcing capability
- Replay functionality
- Audit trail

### 4. Monitoring & Observability
- Event processing metrics
- Error tracking
- Performance monitoring

## Migration Strategy

### Phase 1: In-Memory (Current)
- Development and testing
- Single instance deployment
- Fast iteration

### Phase 2: Redis Streams
- Multi-instance deployment
- Persistent event storage
- Consumer groups

### Phase 3: RabbitMQ/Apache Kafka
- High-throughput production
- Advanced routing
- Enterprise features

## Security Considerations

### Event Encryption
- Sensitive data encryption in transit
- Key rotation policies
- Access control

### Audit Requirements
- Immutable event log
- Compliance tracking
- Data retention policies

## Performance Targets

### Throughput
- 10,000+ events/second (Phase 2)
- 100,000+ events/second (Phase 3)

### Latency
- < 10ms event publishing
- < 100ms event processing
- < 1s end-to-end for critical events

### Reliability
- 99.9% event delivery
- < 0.1% duplicate events
- Zero data loss

## Monitoring & Alerting

### Key Metrics
- Event publishing rate
- Processing latency
- Error rates
- Dead letter queue size
- Worker health status

### Alerts
- High error rates
- Processing delays
- Worker failures
- Dead letter queue growth

## Testing Strategy

### Unit Tests
- Event serialization/deserialization
- Worker logic
- Retry mechanisms

### Integration Tests
- End-to-end event flow
- Cross-domain communication
- Failure scenarios

### Load Tests
- Throughput limits
- Latency under load
- Resource utilization