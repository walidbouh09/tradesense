# Anti-Corruption Layer (ACL) - Payment to Challenge Context

## Overview

The Anti-Corruption Layer (ACL) provides a translation boundary between the Payment Context and Challenge Context, ensuring clean separation while enabling necessary cross-domain communication.

## Scenario: PaymentSucceeded → ChallengeCreated

When a customer successfully pays for a prop trading challenge, the system must:
1. Recognize this as a challenge purchase
2. Transform payment data into challenge parameters
3. Create the challenge in the Challenge Context
4. Handle failures gracefully with compensation strategies

## Architecture

```
┌─────────────────┐    ┌─────────────┐    ┌─────────────────┐
│  Payment Context │───▶   ACL       │───▶│ Challenge Context │
│                 │    │             │    │                 │
│ • PaymentSucceeded │    │ • Translation │    │ • CreateChallenge │
│ • PaymentFailed   │    │ • Validation  │    │ • ChallengeCreated │
│ • PaymentRefunded │    │ • Compensation│    │ • ChallengeFailed  │
└─────────────────┘    └─────────────┘    └─────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Compensation Service│
                   │                     │
                   │ • Automatic Refunds │
                   │ • Manual Review     │
                   │ • SLA Monitoring    │
                   └─────────────────────┘
```

## ACL Responsibilities

### 1. Event Translation
- **Input**: `PaymentSucceeded` domain event
- **Validation**: Confirm payment is for challenge purchase
- **Transformation**: Map payment data to challenge parameters
- **Output**: `CreateChallenge` command

### 2. Data Mapping

```python
# Payment Event → Challenge Parameters
{
    "customer_id": payment.customer_id,           # → trader_id
    "amount": payment.amount,                     # → initial_balance
    "currency": payment.currency,                 # → currency
    "metadata.challenge_type": "PHASE_1",        # → challenge_type
    "payment_id": payment.id,                     # → payment_reference
}
```

### 3. Failure Scenarios

#### Scenario 1: Payment succeeds, Challenge creation fails
```
Payment Context: ✅ Payment processed successfully
Challenge Context: ❌ Challenge creation fails (e.g., invalid parameters)

ACL Response:
1. Log failure with correlation ID
2. Queue for manual review (4-hour SLA)
3. Send customer notification (4 hours)
4. Process automatic refund (24-hour SLA)
5. Escalate to management (72-hour SLA)
```

#### Scenario 2: Payment succeeds, Transformation fails
```
Payment Context: ✅ Payment processed successfully
ACL: ❌ Cannot transform payment data to challenge parameters

ACL Response:
1. Log transformation error
2. Queue for manual data review
3. Alert operations team
4. Potential refund if unresolvable
```

#### Scenario 3: Challenge created successfully
```
Payment Context: ✅ Payment processed successfully
Challenge Context: ✅ Challenge created
ACL: ✅ Correlation established

Result: Clean success path with audit trail
```

## Compensation Strategies

### 1. Automatic Compensation (24-hour SLA)
```python
async def _process_automatic_refund(payment_id, correlation_id):
    # Check if issue resolved manually
    if await is_issue_resolved(correlation_id):
        return

    # Process full refund
    refund_result = await refund_service.process_full_refund(
        payment_id=payment_id,
        reason="Challenge creation failed - SLA breach",
        correlation_id=correlation_id
    )

    # Emit success/failure events
    if refund_result["success"]:
        await event_bus.publish(AutomaticRefundProcessed(...))
    else:
        await escalate_to_management(...)
```

### 2. Manual Review Queue (4-hour SLA)
```python
async def _queue_manual_review(correlation_id, payment_id, reason):
    await event_bus.publish({
        "event_type": "ManualReviewRequired",
        "correlation_id": correlation_id,
        "payment_id": payment_id,
        "reason": reason,
        "priority": "high",
        "queue": "payment_challenge_acl_failures"
    })
```

### 3. Customer Communication
```python
async def _send_customer_notification(customer_id, payment_id, template):
    await event_bus.publish({
        "event_type": "CustomerNotificationRequired",
        "customer_id": customer_id,
        "template": template,  # "challenge_creation_delay", "refund_processed", etc.
        "context": {"payment_id": payment_id}
    })
```

### 4. Management Escalation (72-hour SLA)
```python
async def _escalate_to_management(correlation_id, payment_id, reason):
    await event_bus.publish({
        "event_type": "ManagementEscalationRequired",
        "correlation_id": correlation_id,
        "payment_id": payment_id,
        "reason": reason,
        "escalation_level": "senior_management"
    })
```

## Implementation Example

```python
# Initialize ACL
acl = PaymentToChallengeACL(event_bus, audit_logger)
await acl.register_handlers()

# Payment succeeds → ACL processes automatically
# Event: PaymentSucceeded
# ACL: Transforms → CreateChallenge command
# Result: Challenge created or compensation triggered
```

## Monitoring & Observability

### Key Metrics
- **Transformation Success Rate**: % of payments successfully converted to challenges
- **Compensation Trigger Rate**: % of payments requiring compensation
- **Average Resolution Time**: Time from failure to resolution
- **SLA Compliance**: % meeting 24-hour automatic refund SLA

### Alerting
- Transformation failure rate > 5%
- Compensation queue > 10 items
- SLA breach rate > 1%
- Refund processing failures

## Testing Strategy

### Unit Tests
- Event transformation logic
- Parameter validation
- SLA calculation
- Compensation strategy selection

### Integration Tests
- Full Payment → Challenge flow
- Failure scenario simulation
- Compensation execution
- Event correlation verification

### End-to-End Tests
- Real payment webhook → Challenge creation
- Failure injection and recovery
- SLA timing validation
- Customer notification delivery

## Security Considerations

### Data Isolation
- ACL only accesses necessary data from each context
- No direct database sharing between contexts
- Event-based communication prevents coupling

### Audit Trail
- Complete correlation between payment and challenge
- Immutable log of all transformations
- Compensation actions fully traceable

### Authorization
- ACL operations run with minimal required permissions
- Compensation actions require elevated permissions
- Manual review requires human approval workflow

## Disaster Recovery

### Data Consistency
- Use saga pattern for multi-step operations
- Compensation actions are idempotent
- Failed operations can be replayed

### Backup & Restore
- ACL state stored in database for recovery
- Correlation IDs enable operation reconstruction
- Compensation actions can be replayed after restore

### Failure Scenarios
- ACL service down: Queue events for later processing
- Database unavailable: Store transformations locally
- Event bus down: Use backup communication channels

## Performance Characteristics

### Latency
- Event processing: <100ms
- Challenge creation: <500ms
- Compensation queuing: <50ms

### Throughput
- 1000+ transformations per minute
- 100+ compensations per minute
- Scales horizontally with event bus

### Resource Usage
- Minimal memory footprint
- Database connections pooled
- Event processing is stateless