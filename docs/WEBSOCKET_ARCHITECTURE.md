# Real-Time WebSocket Architecture - TradeSense AI

## Why WebSocket?

Traditional HTTP polling creates poor user experience for trading platforms:

**Problems with Polling:**
- 2-5 second delays between updates
- Unnecessary server load (1000 users × 1 request/second = 1000 RPS)
- Battery drain on mobile devices
- No real-time feedback for trading decisions

**WebSocket Benefits:**
- **Sub-second latency** for equity updates
- **Zero polling overhead** - server pushes updates
- **Battery efficient** - persistent connection
- **Trading-grade UX** - instant feedback on P&L changes

**Business Impact:**
- Improved user engagement and retention
- Competitive advantage in prop trading space
- Professional trading experience expectations met

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Trade API     │───▶│ ChallengeEngine │───▶│   Event Bus     │
│                 │    │                 │    │                 │
│ Synchronous     │    │ Synchronous     │    │ Async Broadcast │
│ Business Logic  │    │ Domain Rules    │    │ WebSocket Push  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Database      │    │   Frontend      │
                       │   Transaction   │    │   React App     │
                       └─────────────────┘    └─────────────────┘
```

**Key Principles:**
1. **WebSocket is OUTPUT only** - no business logic in real-time layer
2. **Domain events drive updates** - UI reacts to business events
3. **Failure isolation** - WebSocket issues don't affect trading
4. **Room-based security** - users see only their own challenges

## Event Flow: Trade → UI Update

### Step 1: Trade Execution (Synchronous)
```python
# Domain layer - synchronous business logic
def handle_trade_executed(self, event, session):
    # 1. Update equity (synchronous)
    self._update_equity(event)

    # 2. Evaluate rules (synchronous)
    rule_result = self._evaluate_rules()

    # 3. Update status (synchronous)
    self._update_status(rule_result, event)

    # 4. Emit domain events (asynchronous)
    event_bus.emit('EQUITY_UPDATED', payload)
    event_bus.emit('CHALLENGE_STATUS_CHANGED', payload)

    # 5. Commit transaction
    session.commit()
```

### Step 2: Event Bus Forwarding
```python
# Event bus forwards to WebSocket
def websocket_forwarder(event_type, payload):
    challenge_id = payload['challenge_id']
    room_name = f"challenge_{challenge_id}"

    # Emit to challenge-specific room only
    socketio.emit(event_type, payload, room=room_name)
```

### Step 3: Client Reception
```javascript
// React hook receives updates
socket.on('equity_updated', (data) => {
  setEquityData(data);
  // UI updates instantly
});
```

### Complete Flow Timeline
```
0ms:  Trade API receives request
10ms: ChallengeEngine processes trade
15ms: Database transaction commits
20ms: Domain events emitted
25ms: WebSocket broadcasts to client
30ms: React UI updates
```

## Security Model

### Authentication

**JWT-Based Connection:**
```javascript
// Client connects with token
const socket = io('ws://localhost:5000', {
  query: { token: jwtToken }
});
```

**Server Validation:**
```python
@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    payload = validate_jwt_token(token)  # Full validation

    if not payload:
        disconnect()
        return False

    # Store user context
    request.sid_data = payload
    return True
```

### Authorization

**Room-Based Isolation:**
```python
# Each challenge has private room
room_name = f"challenge_{challenge_id}"

# User must own challenge to join
@socketio.on('join_challenge')
def handle_join_challenge(data):
    challenge_id = data['challenge_id']
    user_id = request.sid_data['user_id']

    # Verify ownership (business rule)
    if not user_owns_challenge(user_id, challenge_id):
        socketio.emit('error', {'message': 'Access denied'})
        return

    join_room(room_name)
```

**Security Properties:**
- **No cross-user data leakage** - room isolation
- **Authentication required** - no anonymous connections
- **Authorization enforced** - ownership verification
- **Connection limits** - prevent DoS attacks

## Scaling Roadmap

### Phase 1: Single Server (Current)
```
┌─────────────────┐
│   Flask App     │
│                 │
│ WebSocket       │ ← 1000 concurrent users
│ Challenge       │
│ Database        │
└─────────────────┘
```

**Limits:** 10,000 concurrent connections, single point of failure

### Phase 2: Load Balanced Workers
```
┌─────────────┐
│  Load       │  Sticky Sessions
│  Balancer   │
├─────────────┤
│ Worker 1    │  User A, Challenge X
│ Worker 2    │  User B, Challenge Y
│ Worker 3    │  User N, Challenge Z
└─────────────┘
```

**Benefits:** Horizontal scaling, fault tolerance
**Requirements:** Sticky sessions for WebSocket affinity

### Phase 3: Redis Adapter (Production)
```
┌─────────────┐      ┌─────────────┐
│  Workers    │◄────▶│    Redis    │
│  1,2,3,N    │      │   Cluster   │
└─────────────┘      └─────────────┘
         │
         ▼
    ┌─────────────┐
    │   Clients   │ Any worker can broadcast
    └─────────────┘
```

**Benefits:** No sticky sessions, cross-worker broadcasts, high availability
**Implementation:**
```python
socketio = SocketIO(
    app,
    message_queue='redis://cluster:6379',
    channel='tradesense_websocket'
)
```

## Client Implementation

### React Hook Usage
```javascript
function ChallengeDashboard({ challengeId, token }) {
  const {
    equityData,
    statusData,
    riskAlerts,
    isConnected,
    error,
    refresh,
    clearAlerts
  } = useLiveChallenge(challengeId, token);

  // Real-time updates
  useEffect(() => {
    if (equityData) {
      updateEquityDisplay(equityData);
    }
  }, [equityData]);

  return (
    <div>
      <ConnectionStatus connected={isConnected} />
      <EquityDisplay data={equityData} />
      <RiskAlerts alerts={riskAlerts} />
    </div>
  );
}
```

### Connection Management
```javascript
// Automatic reconnection with backoff
socket.on('connect_error', (error) => {
  setTimeout(() => socket.connect(), retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30000);
});

// Room management
socket.emit('join_challenge', { challenge_id: challengeId });
```

## Events Reference

### EQUITY_UPDATED
**Triggered:** After every trade execution
**Payload:**
```javascript
{
  challenge_id: "uuid",
  user_id: "uuid",
  previous_equity: "10000.00",
  current_equity: "10200.00",
  max_equity_ever: "10200.00",
  daily_start_equity: "10000.00",
  daily_max_equity: "10200.00",
  daily_min_equity: "10000.00",
  total_pnl: "200.00",
  total_trades: 2,
  last_trade_at: "2024-01-01T10:00:00Z",
  trade_pnl: "200.00",
  trade_symbol: "EURUSD",
  executed_at: "2024-01-01T10:00:00Z"
}
```

### CHALLENGE_STATUS_CHANGED
**Triggered:** When challenge status transitions
**Payload:**
```javascript
{
  challenge_id: "uuid",
  old_status: "ACTIVE",
  new_status: "FUNDED",
  reason: "PROFIT_TARGET",
  changed_at: "2024-01-01T14:30:00Z"
}
```

### RISK_ALERT
**Triggered:** When rule thresholds are approached
**Payload:**
```javascript
{
  challenge_id: "uuid",
  user_id: "uuid",
  alert_type: "HIGH_DAILY_DRAWDOWN",
  severity: "MEDIUM",
  title: "High Daily Drawdown Warning",
  message: "Daily drawdown at 4.50% (limit: 5.00%)",
  current_equity: "9550.00",
  daily_start_equity: "10000.00",
  drawdown_percentage: "4.50",
  threshold_percentage: "5.00",
  alert_timestamp: "2024-01-01T12:00:00Z"
}
```

## Monitoring & Observability

### Key Metrics
- **Connection Health:** Success rate, reconnection time, concurrent connections
- **Event Delivery:** Messages/second, delivery latency, failure rate
- **Resource Usage:** Memory per connection, CPU overhead
- **User Experience:** Update latency, connection stability

### Alerting Rules
```python
alerts = {
    'websocket_connections_low': 'avg < 100',
    'event_delivery_failure_high': 'rate > 5%',
    'reconnection_time_high': 'p95 > 30s',
    'memory_usage_high': 'usage > 80%'
}
```

## Deployment Checklist

### Pre-Deployment
- [ ] WebSocket server configured with proper CORS
- [ ] JWT secret configured in environment
- [ ] Redis adapter configured (Phase 3)
- [ ] Load balancer sticky sessions configured
- [ ] Connection limits set per user
- [ ] Monitoring dashboards configured

### Testing
- [ ] Unit tests for event emission
- [ ] Integration tests for WebSocket connections
- [ ] Load tests with 1000 concurrent connections
- [ ] Chaos testing (server restarts, network partitions)
- [ ] Security testing (unauthorized access attempts)

### Production
- [ ] SSL/TLS certificates for WSS
- [ ] Rate limiting configured
- [ ] Health checks implemented
- [ ] Log aggregation configured
- [ ] Backup and recovery procedures documented

## Troubleshooting

### Common Issues

**Clients not receiving updates:**
1. Check JWT token validity
2. Verify room membership (`join_challenge` event)
3. Check server logs for emission errors
4. Confirm challenge ownership

**High latency:**
1. Check database query performance
2. Monitor Redis queue depth (if using adapter)
3. Verify network connectivity
4. Check client-side processing

**Connection drops:**
1. Verify JWT token expiration
2. Check server resource limits
3. Monitor network stability
4. Review reconnection logic

**Memory leaks:**
1. Monitor connection count vs memory usage
2. Check for unclosed event listeners
3. Verify room cleanup on disconnect
4. Monitor event queue sizes

## Future Enhancements

### Performance Optimizations
- Binary message formats for reduced bandwidth
- Event compression and batching
- Client-side caching and deduplication
- Progressive enhancement for slow connections

### Advanced Features
- Push notifications for mobile apps
- Offline queue for missed events
- Event replay for late-joining clients
- Real-time collaboration features

### Operational Improvements
- Circuit breakers for upstream failures
- Graceful degradation strategies
- Advanced monitoring and tracing
- Automated scaling policies

This WebSocket architecture delivers the real-time trading experience users expect while maintaining the security, reliability, and scalability required for financial applications.