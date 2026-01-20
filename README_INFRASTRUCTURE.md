# TradeSense AI - Core Infrastructure Layer

## Overview

The TradeSense AI infrastructure layer provides production-grade, financial-compliant foundation components for the entire platform. Built with async-first architecture, comprehensive audit trails, and financial regulatory requirements in mind.

## Architecture Principles

### 1. Financial Compliance by Design
- Immutable audit logs with integrity protection
- Comprehensive permission system with fine-grained controls
- Regulatory-compliant data retention and encryption
- Tamper-evident logging with hash chains

### 2. Async-First Architecture
- All I/O operations are asynchronous
- Non-blocking database connections with pooling
- Event-driven communication between components
- Background workers for heavy processing

### 3. Security-First Approach
- JWT authentication with refresh token rotation
- Role-based access control (RBAC) with caching
- Cryptographic hashing with salt and pepper
- PII encryption with key rotation support

### 4. Observability & Monitoring
- Structured logging with correlation tracking
- Performance monitoring with slow query detection
- Health checks for all critical components
- Business and technical metrics collection

## Core Components

### Configuration Management (`config/`)

Environment-aware configuration with validation and secrets management.

```python
from src.infrastructure import get_settings

settings = get_settings()
print(f"Database URL: {settings.database.connection_url}")
print(f"JWT Algorithm: {settings.security.jwt_algorithm}")
```

**Features:**
- Type-safe configuration with Pydantic
- Environment-specific overrides
- Financial compliance validation
- Secrets masking for logs

### Database Layer (`database/`)

Robust database management with connection pooling, health monitoring, and transaction safety.

```python
from src.infrastructure import DatabaseConnectionManager, TransactionManager

# Initialize database
db_manager = DatabaseConnectionManager(settings.database)
await db_manager.initialize()

# Use transactions
transaction_manager = TransactionManager(session_manager)
async with transaction_manager.transaction() as session:
    # Database operations here
    pass
```

**Features:**
- Connection pooling with circuit breakers
- Health monitoring with automatic failover
- Transaction boundary management
- Session lifecycle with proper cleanup

### Security Layer (`security/`)

Financial-grade security with JWT, encryption, and RBAC.

```python
from src.infrastructure import JWTManager, RoleBasedAccessControl, SecureHasher

# JWT Management
jwt_manager = JWTManager(settings.security)
token = await jwt_manager.create_access_token(user_id, permissions, context)

# Role-Based Access Control
rbac = RoleBasedAccessControl()
await rbac.require_permission(user_id, ResourceType.ORDER, Action.CREATE)

# Secure Hashing
hasher = SecureHasher(settings.security)
password_hash = hasher.hash_password("password123")
```

**Features:**
- JWT with refresh token rotation and blacklisting
- Fine-grained RBAC with permission caching
- Cryptographic hashing with context-specific keys
- Password strength validation for financial security

### Event Bus (`messaging/`)

Reliable event-driven communication with pluggable implementations.

```python
from src.infrastructure import InMemoryEventBus, EventHandler

# Initialize event bus
event_bus = InMemoryEventBus()
await event_bus.start()

# Subscribe to events
await event_bus.subscribe("OrderPlaced", my_handler)

# Publish events
await event_bus.publish(domain_event, context=execution_context)
```

**Features:**
- Pluggable implementations (in-memory, Redis, etc.)
- Automatic retry with exponential backoff
- Dead letter queue for failed events
- Event replay for recovery scenarios

### Logging & Audit (`logging/`)

Financial-grade logging with structured format and audit trails.

```python
from src.infrastructure import configure_logging, AuditLogger, AuditEventType

# Configure structured logging
configure_logging(settings.logging)
logger = get_logger("my_service")

# Audit logging
audit_logger = AuditLogger(encryption_key)
await audit_logger.log_business_event(
    event_type=AuditEventType.ORDER_PLACED,
    user_id=user_id,
    resource_type="order",
    resource_id=order_id,
    action="place_order",
    details=order_details,
)
```

**Features:**
- Structured logging with correlation IDs
- Immutable audit logs with integrity protection
- Sensitive data masking and encryption
- Compliance reporting and export

### Common Utilities (`common/`)

Cross-cutting concerns and utility functions.

```python
from src.infrastructure import ExecutionContext, AuditContext
from src.infrastructure import with_execution_context, with_audit_context, with_retry

# Context management
context = ExecutionContext.create_for_request(request, user_id)

# Decorators for cross-cutting concerns
@with_execution_context("place_order")
@with_audit_context("order", "place")
@with_retry(max_attempts=3)
async def place_order(user_id, symbol, quantity):
    # Business logic here
    pass
```

**Features:**
- Request correlation and tracing
- Audit context for compliance tracking
- Decorators for common patterns
- Exception hierarchy with context

## Usage Examples

### Complete Service Integration

```python
from src.infrastructure import *

class TradingService:
    def __init__(self, db_manager, jwt_manager, rbac, event_bus, audit_logger):
        self.db_manager = db_manager
        self.jwt_manager = jwt_manager
        self.rbac = rbac
        self.event_bus = event_bus
        self.audit_logger = audit_logger
    
    @with_execution_context("place_order")
    @with_audit_context("order", "place", "User requested order placement")
    @with_performance_monitoring(slow_threshold_ms=500)
    @require_permission(ResourceType.ORDER, Action.CREATE)
    async def place_order(self, user_id, symbol, quantity, price):
        # Check permissions (handled by decorator)
        
        # Execute in transaction
        async with self.transaction_manager.transaction() as session:
            # Save order to database
            order_id = await self.save_order(session, user_id, symbol, quantity, price)
            
            # Publish domain event
            event = OrderPlacedEvent(order_id, user_id, symbol, quantity)
            await self.event_bus.publish(event)
            
            return order_id
```

### Authentication Flow

```python
async def authenticate_user(username, password, ip_address):
    # Create execution context
    context = ExecutionContext.create_for_system("authenticate_user")
    
    # Verify password
    hasher = SecureHasher(settings.security)
    if not hasher.verify_password(password, stored_hash):
        # Log failed attempt
        await audit_logger.log_authentication_event(
            AuditEventType.LOGIN_FAILED,
            user_id=None,
            success=False,
            ip_address=ip_address,
            failure_reason="Invalid password",
        )
        raise AuthenticationError("Invalid credentials")
    
    # Create tokens
    access_token = await jwt_manager.create_access_token(
        user_id=user_id,
        permissions=user_permissions,
        execution_context=context,
    )
    
    # Log successful login
    await audit_logger.log_authentication_event(
        AuditEventType.USER_LOGIN,
        user_id=user_id,
        success=True,
        ip_address=ip_address,
    )
    
    return access_token
```

## Configuration

### Environment Variables

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=tradesense
DB_PASSWORD=secure_password
DB_DATABASE=tradesense

# Security
SECURITY_JWT_SECRET_KEY=your-256-bit-secret-key
SECURITY_PASSWORD_PEPPER=your-pepper-value
SECURITY_ENCRYPTION_KEY=your-32-byte-encryption-key

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_AUDIT_RETENTION_DAYS=2555

# Messaging
MESSAGING_EVENT_BUS_TYPE=in_memory
MESSAGING_OUTBOX_ENABLED=true
```

### Financial Compliance Settings

The infrastructure automatically validates configuration for financial compliance:

- Audit retention must be at least 7 years (2555 days)
- Database SSL must be enabled in production
- Password salt rounds must be at least 12
- Access token expiry must be ≤ 60 minutes in production
- Audit log encryption must be enabled

## Monitoring & Health Checks

### Health Check Endpoints

```python
# Database health
health_status = await db_manager.get_health_status()
# Returns: {"healthy": true, "response_time_ms": 15.2, "pool_status": {...}}

# Event bus health
bus_health = await event_bus.health_check()
# Returns: EventBusHealth.HEALTHY

# Overall system health
system_health = {
    "database": await db_manager.get_health_status(),
    "event_bus": await event_bus.health_check(),
    "cache": await cache_manager.health_check(),
}
```

### Metrics Collection

```python
# Event bus metrics
metrics = event_bus.get_metrics()
print(f"Events published: {metrics.events_published}")
print(f"Events processed: {metrics.events_processed}")
print(f"Average processing time: {metrics.average_processing_time_ms}ms")

# Database metrics
db_health = await db_manager.get_health_status()
print(f"Pool size: {db_health['pool_status']['pool_size']}")
print(f"Active connections: {db_health['pool_status']['checked_out']}")
```

## Security Considerations

### Production Deployment

1. **Secrets Management**
   - Use environment variables or secret management systems
   - Never commit secrets to version control
   - Rotate keys regularly (every 90 days recommended)

2. **Database Security**
   - Enable SSL/TLS for all database connections
   - Use connection pooling with proper limits
   - Implement database-level audit logging

3. **API Security**
   - Implement rate limiting
   - Use HTTPS only in production
   - Set appropriate CORS policies
   - Enable request/response logging

4. **Audit Compliance**
   - Ensure audit logs are immutable
   - Implement log integrity verification
   - Set up automated compliance reporting
   - Regular audit log backups

## Performance Optimization

### Database Optimization

- Connection pooling with appropriate pool sizes
- Query performance monitoring
- Automatic connection recycling
- Circuit breaker for database failures

### Event Processing

- Batch event processing for high throughput
- Dead letter queue for failed events
- Event replay for recovery scenarios
- Metrics collection for monitoring

### Caching Strategy

- Permission caching with TTL
- Configuration caching with hot-reload
- Token blacklist caching
- Health status caching

## Troubleshooting

### Common Issues

1. **Database Connection Failures**
   - Check connection pool settings
   - Verify database credentials
   - Review SSL configuration
   - Monitor connection health

2. **Authentication Issues**
   - Verify JWT secret key configuration
   - Check token expiration settings
   - Review permission assignments
   - Monitor failed login attempts

3. **Event Processing Failures**
   - Check dead letter queue
   - Review event handler logs
   - Verify event bus health
   - Monitor processing metrics

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
settings = get_settings()
settings.debug = True
settings.logging.level = "DEBUG"
configure_logging(settings.logging)
```

## Contributing

When extending the infrastructure layer:

1. Follow async-first patterns
2. Add comprehensive logging
3. Include audit trail support
4. Write unit and integration tests
5. Update documentation
6. Consider financial compliance requirements

## License

Proprietary - TradeSense AI