# WebSocket Resilience Strategies

## Overview

Real-time WebSocket communication in trading platforms requires robust resilience strategies.
This document outlines approaches to handle connection failures, event delivery guarantees,
and system degradation while maintaining data integrity.

## Connection Resilience

### Client-Side Reconnection Strategy

**Automatic Reconnection with Exponential Backoff:**

```javascript
// In useLiveChallenge hook
const connectWithRetry = useCallback(() => {
  const maxRetries = 5;
  let retryCount = 0;
  let retryDelay = 1000; // Start with 1 second

  const attemptConnection = () => {
    socket.connect();

    socket.on('connect', () => {
      console.log('Reconnected successfully');
      retryCount = 0;
      retryDelay = 1000;
      // Rejoin challenge rooms
      if (challengeId) {
        socket.emit('join_challenge', { challenge_id: challengeId });
      }
    });

    socket.on('connect_error', (error) => {
      retryCount++;
      if (retryCount <= maxRetries) {
        console.log(`Reconnection attempt ${retryCount}/${maxRetries} in ${retryDelay}ms`);
        setTimeout(attemptConnection, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000); // Max 30 seconds
      } else {
        console.error('Max reconnection attempts reached');
        setError('Unable to reconnect to live updates');
      }
    });
  };

  attemptConnection();
}, [challengeId]);
```

**Connection State Management:**
- Track connection health metrics
- Provide user feedback on connection status
- Allow manual reconnection attempts
- Graceful degradation to polling if WebSocket fails

### Server-Side Connection Handling

**Connection Limits and Cleanup:**
```python
# In websocket.py
@socketio.on('connect')
def handle_connect():
    # Rate limiting per user
    user_connections = get_user_connection_count(request.sid_data['user_id'])
    if user_connections >= MAX_CONNECTIONS_PER_USER:
        socketio.emit('error', {'message': 'Connection limit exceeded'})
        disconnect()
        return False

    # Connection tracking
    track_connection(request.sid_data['user_id'], request.sid)

    return True

@socketio.on('disconnect')
def handle_disconnect():
    # Clean up connection tracking
    cleanup_connection(request.sid_data['user_id'], request.sid)
```

## Event Delivery Guarantees

### At-Most-Once Delivery (Current Implementation)

**Characteristics:**
- Events may be lost during connection failures
- No event buffering or redelivery
- Simplest implementation with lowest overhead

**Trade-offs:**
- ✅ Low complexity
- ✅ Minimal resource usage
- ❌ Missed updates during outages
- ❌ No delivery guarantees

### At-Least-Once Delivery (Recommended Enhancement)

**Implementation Strategy:**
```python
# Server-side event queuing
class EventQueue:
    def __init__(self):
        self.pending_events = {}  # user_id -> [events]
        self.max_queue_size = 100

    def enqueue_event(self, user_id, event_type, payload):
        if user_id not in self.pending_events:
            self.pending_events[user_id] = []

        self.pending_events[user_id].append({
            'event_type': event_type,
            'payload': payload,
            'timestamp': datetime.utcnow(),
            'id': str(uuid.uuid4())  # Event ID for deduplication
        })

        # Prevent unbounded growth
        if len(self.pending_events[user_id]) > self.max_queue_size:
            self.pending_events[user_id].pop(0)

    def deliver_pending_events(self, user_id, socket):
        """Deliver queued events when client reconnects"""
        if user_id in self.pending_events:
            for event in self.pending_events[user_id]:
                socket.emit(event['event_type'], event['payload'])
            self.pending_events[user_id].clear()

# Client-side deduplication
const receivedEventIds = new Set();

socket.on('equity_updated', (data) => {
  if (receivedEventIds.has(data.event_id)) {
    return; // Duplicate event
  }
  receivedEventIds.add(data.event_id);
  // Process event...
});
```

### Event Idempotency

**Event ID Generation:**
```python
# In ChallengeEngine
def _emit_events(self, challenge, status_changed, trade_event):
    event_id = f"{challenge.id}_{trade_event.executed_at.isoformat()}_{status_changed}"

    event_bus.emit('EQUITY_UPDATED', {
        'event_id': event_id,  # Unique identifier
        'challenge_id': str(challenge.id),
        # ... other payload
    })
```

**Client-Side Deduplication:**
- Track processed event IDs
- Ignore duplicate deliveries
- Clean up old IDs to prevent memory leaks

## Failure Mode Analysis

### 1. Client Disconnects

**Impact:** Live updates stop until reconnection

**Mitigation:**
- Automatic reconnection with backoff
- Connection status indicators in UI
- Graceful degradation to manual refresh
- Preserve application state during reconnect

**Recovery:**
```javascript
socket.on('reconnect', () => {
  // Rejoin challenge rooms
  socket.emit('join_challenge', { challenge_id: challengeId });

  // Request latest state if needed
  refreshChallengeData();
});
```

### 2. WebSocket Server Restarts

**Impact:** All connections lost, events buffered on server

**Mitigation:**
- Stateless server design (reconnection doesn't lose data)
- Horizontal scaling with load balancer sticky sessions
- Health checks and automatic restarts
- Database-backed event queuing (future enhancement)

**Recovery:**
- Clients automatically reconnect
- Server state reconstruction from database
- Event replay for missed updates

### 3. Missed Events

**Current Behavior:** Events lost during disconnection

**Enhanced Solution:**
```python
# Server-side event persistence
class PersistentEventStore:
    def store_event(self, user_id, event_type, payload):
        # Store in Redis/database with TTL
        pass

    def get_pending_events(self, user_id, since_timestamp):
        # Retrieve missed events for replay
        pass
```

### 4. High-Frequency Updates

**Problem:** UI overwhelmed by rapid trade updates

**Solutions:**
- **Throttling:** Limit update frequency (max 1 per second)
- **Buffering:** Aggregate rapid changes
- **Progressive Enhancement:** Show summary for high-volume periods

```javascript
// Client-side throttling
let lastUpdate = 0;
const THROTTLE_MS = 100;

socket.on('equity_updated', (data) => {
  const now = Date.now();
  if (now - lastUpdate < THROTTLE_MS) {
    return; // Skip this update
  }
  lastUpdate = now;
  updateEquity(data);
});
```

## Domain Isolation

### Critical Principle: WebSocket Failures ≠ Business Failures

**Why This Matters:**
- Trading decisions must work without real-time updates
- WebSocket is enhancement, not requirement
- Business logic remains synchronous and deterministic

**Implementation:**
```python
# ChallengeEngine remains synchronous
def handle_trade_executed(self, event, session):
    # All business logic here - no WebSocket dependencies
    self._update_equity(event)
    self._evaluate_rules()
    self._update_status()

    # WebSocket emission happens after business logic succeeds
    self._emit_events(event)  # Can fail without affecting trade
```

**Failure Scenarios Handled:**
- WebSocket server down → Trading continues normally
- Client offline → Trades processed, updates delivered on reconnect
- Network partition → Local trading, sync on recovery
- UI crashes → Backend continues processing

## Monitoring and Observability

### Key Metrics to Track

**Connection Health:**
- Connection success rate
- Average reconnection time
- Connection duration distribution
- Concurrent connection count

**Event Delivery:**
- Events emitted per second
- Events delivered vs lost
- Average delivery latency
- Queue depth (if buffered)

**Error Rates:**
- Connection failure rate
- Event emission failure rate
- Client-side error rate

### Alerting Thresholds

```python
# Example monitoring
alerts = {
    'websocket_connections_low': 'avg < 100',
    'event_delivery_failure_high': 'rate > 5%',
    'reconnection_time_high': 'p95 > 30s',
    'queue_depth_high': 'depth > 1000'
}
```

## Testing Strategies

### Chaos Engineering

**Network Partition Testing:**
```bash
# Simulate network issues
iptables -A INPUT -p tcp --dport 5000 -j DROP  # Block WebSocket port
# Verify trading continues, updates resume on recovery
iptables -D INPUT -p tcp --dport 5000 -j DROP  # Restore
```

**Server Failure Testing:**
```bash
# Kill WebSocket server
kill -9 $(pgrep -f "python.*socketio")
# Verify clients reconnect automatically
# Verify no trade data loss
```

### Load Testing

**High-Frequency Trading Simulation:**
- Generate 1000 trades/second
- Monitor WebSocket delivery latency
- Test throttling mechanisms
- Verify UI responsiveness

**Connection Scaling:**
- 10,000 concurrent WebSocket connections
- Measure memory usage
- Test horizontal scaling
- Verify room isolation

## Future Enhancements

### Redis Adapter for Production
```python
# Flask-SocketIO Redis adapter
socketio = SocketIO(
    app,
    message_queue='redis://localhost:6379',
    channel='tradesense'
)
```

### Event Sourcing Integration
- Store all events in event store
- Replay events for missed updates
- Audit trail for all real-time communications

### Progressive Web App (PWA) Features
- Background sync for offline trades
- Push notifications for important events
- Service worker for offline functionality

This resilience strategy ensures that WebSocket communication enhances the trading experience without compromising the core reliability and correctness of the financial system.