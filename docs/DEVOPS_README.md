# TradeSense AI - DevOps Guide

## Architecture Overview

TradeSense AI is a containerized, microservices-based prop trading platform designed for high availability and scalability.

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Backend API   │    │   Async Worker  │    │   Frontend      │
│                 │    │                 │    │   (Optional)    │
│ Flask + SocketIO│    │ Risk Monitoring │    │   React        │
│   Port: 8000    │    │   Background    │    │   Port: 3000   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                       │                       │
          └───────────┬───────────┼───────────┬───────────┘
                      │           │           │
           ┌─────────────────┐    ┌─────────────────┐
           │   PostgreSQL    │    │     Redis       │
           │   Port: 5432    │    │   Port: 6379    │
           │   Persistent    │    │   Cache/Queue   │
           └─────────────────┘    └─────────────────┘
```

### Service Responsibilities

**Backend API:**
- RESTful HTTP endpoints for challenge management
- Real-time WebSocket connections for live updates
- Synchronous business logic execution
- Authentication and authorization

**Async Worker:**
- Background risk monitoring and alerting
- Non-critical data processing
- Periodic maintenance tasks
- Event-driven background jobs

**PostgreSQL:**
- Primary data store for all business entities
- ACID-compliant transactions
- Complex queries and reporting
- Audit trail storage

**Redis:**
- High-performance caching layer
- Message broker for background tasks
- WebSocket session storage (future)
- Rate limiting and session management

## Local Development Setup

### Prerequisites

- Docker and Docker Compose
- Git
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### Quick Start with Docker Compose

1. **Clone and setup:**
```bash
git clone <repository>
cd tradesense
cp env.example .env
# Edit .env with your local configuration
```

2. **Start all services:**
```bash
docker-compose up -d
```

3. **Check service health:**
```bash
# Backend API
curl http://localhost:8000/health

# Database connection
docker-compose exec postgres pg_isready -U tradesense_user

# Redis connection
docker-compose exec redis redis-cli ping
```

4. **View logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
```

5. **Stop services:**
```bash
docker-compose down
```

### Development Workflow

**API Development:**
```bash
# Run backend only
docker-compose up backend

# With live reload (mount source)
docker-compose -f docker-compose.dev.yml up backend
```

**Worker Development:**
```bash
# Run worker only
docker-compose up worker

# Debug worker logs
docker-compose logs -f worker
```

**Frontend Development:**
```bash
# Run with frontend profile
docker-compose --profile frontend up

# Access at http://localhost:3000
```

### Database Management

**Access PostgreSQL:**
```bash
docker-compose exec postgres psql -U tradesense_user -d tradesense
```

**Reset database:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d postgres
```

**Run migrations:**
```bash
# If using Alembic
docker-compose exec backend alembic upgrade head
```

## Why Workers Exist

### Separation of Concerns

**Synchronous vs Asynchronous Processing:**

**Backend API (Synchronous):**
- User-facing operations requiring immediate response
- Critical business decisions (challenge acceptance/rejection)
- Real-time trading operations
- WebSocket event emission

**Worker (Asynchronous):**
- Background monitoring and alerting
- Non-critical data analysis
- Periodic maintenance tasks
- Batch processing operations

### Business Requirements

**Real-time Trading Cannot Wait:**
```python
# This MUST be synchronous - traders need immediate feedback
@challenge_engine.handle_trade_executed(trade_event, session)
    # Evaluate rules immediately
    # Update equity instantly
    # Emit WebSocket events
    # Return success/failure
```

**Risk Monitoring Can Wait:**
```python
# This CAN be asynchronous - monitoring is supplementary
@worker.perform_monitoring_cycle()
    # Check for inactive challenges
    # Generate risk alerts
    # Update analytics data
    # No user waiting for response
```

### Operational Benefits

**Performance Isolation:**
- Trading performance unaffected by monitoring workload
- Background tasks can be resource-intensive without impacting users
- Independent scaling of real-time vs batch processing

**Reliability:**
- Worker failures don't affect trading operations
- Background processing can be paused/restarted safely
- Graceful degradation when workers are unavailable

**Maintainability:**
- Clear separation of real-time vs background logic
- Different deployment and scaling strategies
- Independent testing and monitoring

## Scaling Strategy

### Horizontal Scaling Tiers

**Tier 1: Single Instance (0-100 users)**
```
1 Backend Instance + 1 Worker Instance
PostgreSQL + Redis (shared)
Cost: ~$50/month
```

**Tier 2: Load Balanced (100-1000 users)**
```
3 Backend Instances + 2 Worker Instances
PostgreSQL with read replicas
Redis cluster
Cost: ~$200/month
```

**Tier 3: High Availability (1000+ users)**
```
5+ Backend Instances + 3+ Worker Instances
PostgreSQL cluster
Redis cluster with persistence
Cost: ~$1000+/month
```

### Service-Specific Scaling

#### Backend API Scaling

**Scaling Triggers:**
- CPU usage > 70%
- Memory usage > 80%
- Response time > 500ms (p95)
- WebSocket connections > 1000 per instance

**Scaling Strategy:**
```yaml
# Kubernetes HPA example
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

#### Worker Scaling

**Scaling Triggers:**
- Queue depth > 1000 messages
- Processing lag > 5 minutes
- CPU usage > 60% (workers can be CPU-intensive)

**Scaling Strategy:**
- Start with 1 worker instance
- Scale based on monitoring backlog
- Use Redis queues for distributed processing

#### Database Scaling

**Read Replicas:**
```sql
-- Application load balancing
CREATE EXTENSION pgpool;

-- Read replica configuration
ALTER SYSTEM SET synchronous_standby_names = 'replica1,replica2';
```

**Connection Pooling:**
```python
# SQLAlchemy configuration
engine = create_engine(
    database_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)
```

### Performance Monitoring

**Key Metrics:**
- API response time (p50, p95, p99)
- WebSocket connection count
- Database query latency
- Redis cache hit rate
- Worker queue depth

**Monitoring Stack:**
```yaml
# Prometheus metrics
api_response_duration_seconds{quantile="0.95"} < 0.5
websocket_connections_active < 5000
database_connection_pool_usage < 0.8
redis_memory_usage_bytes < 256MB
worker_queue_length < 1000
```

## Deployment Roadmap

### Phase 1: Development Environment (Current)

**Goals:**
- Local development with hot reload
- Full-stack testing capabilities
- Database seeding and reset
- Development tooling integration

**Infrastructure:**
- Docker Compose with development overrides
- Local PostgreSQL and Redis
- Hot reload for Python and Node.js
- Development logging and debugging

### Phase 2: Staging Environment (Next 3 months)

**Goals:**
- Production-like deployment testing
- Performance and load testing
- Integration testing across services
- Security testing and penetration testing

**Infrastructure:**
- Cloud deployment (Render/Railway/AWS)
- Managed PostgreSQL and Redis
- SSL certificates and custom domains
- Monitoring and alerting setup
- Backup and recovery procedures

### Phase 3: Production Environment (3-6 months)

**Goals:**
- High availability and fault tolerance
- Auto-scaling based on load
- Advanced monitoring and observability
- Disaster recovery capabilities

**Infrastructure:**
- Kubernetes or container orchestration
- Multi-region deployment
- CDN integration
- Advanced security (WAF, DDoS protection)
- 24/7 on-call support

### Phase 4: Enterprise Scale (6+ months)

**Goals:**
- Global distribution
- Advanced analytics and reporting
- API rate limiting and abuse protection
- Compliance automation (SOC 2, GDPR)

**Infrastructure:**
- Multi-cloud deployment
- Global CDN with edge computing
- Advanced AI/ML for risk detection
- Enterprise integration APIs

## Operational Procedures

### Daily Operations

**Health Checks:**
```bash
# Automated health checks
curl -f https://api.tradesense.ai/health
docker-compose ps  # Local development
kubectl get pods  # Kubernetes
```

**Log Monitoring:**
```bash
# Application logs
docker-compose logs -f --tail=100

# Database logs
docker-compose exec postgres tail -f /var/log/postgresql/postgresql-*.log

# Worker logs
docker-compose logs -f worker
```

### Incident Response

**Service Down:**
1. Check service health: `docker-compose ps`
2. Review recent logs: `docker-compose logs --tail=50 <service>`
3. Check resource usage: `docker stats`
4. Restart if needed: `docker-compose restart <service>`
5. Escalate if persistent

**Database Issues:**
1. Check connections: `docker-compose exec postgres pg_stat_activity;`
2. Verify disk space: `docker-compose exec postgres df -h`
3. Check for long-running queries
4. Consider connection pool restart

**Performance Degradation:**
1. Monitor key metrics
2. Check for memory leaks
3. Analyze slow queries
4. Scale services as needed

### Backup and Recovery

**Database Backups:**
```bash
# Automated daily backups
0 2 * * * docker-compose exec postgres pg_dump -U tradesense_user tradesense > backup.sql

# Restore procedure
docker-compose exec -T postgres psql -U tradesense_user -d tradesense < backup.sql
```

**Application Backups:**
- Docker images stored in registry
- Configuration version controlled
- Environment variables encrypted

### Security Procedures

**Secret Management:**
```bash
# Never commit secrets
echo ".env" >> .gitignore

# Use platform secret management
# AWS Secrets Manager, Render Environment, Railway Variables
```

**Access Control:**
- Principle of least privilege
- SSH key-based access only
- Multi-factor authentication required
- Regular access review and rotation

## Troubleshooting Guide

### Common Issues

**Backend won't start:**
```bash
# Check environment variables
docker-compose exec backend env | grep -E "(DATABASE|REDIS|SECRET)"

# Check database connectivity
docker-compose exec backend python -c "import psycopg2; psycopg2.connect(os.getenv('DATABASE_URL'))"
```

**Worker not processing:**
```bash
# Check worker logs
docker-compose logs -f worker

# Check Redis connectivity
docker-compose exec worker redis-cli -h redis ping

# Check database connectivity
docker-compose exec worker python -c "from app.infrastructure.redis_client import redis_client; print(redis_client.is_available())"
```

**WebSocket connections failing:**
```bash
# Check CORS configuration
curl -H "Origin: http://localhost:3000" http://localhost:8000/health

# Check SocketIO logs
docker-compose logs -f backend | grep socketio
```

**Database connection issues:**
```bash
# Check connection pool
docker-compose exec postgres psql -U tradesense_user -c "SELECT count(*) FROM pg_stat_activity;"

# Check for connection leaks
docker-compose exec postgres psql -U tradesense_user -c "SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction';"
```

### Performance Tuning

**Database Optimization:**
```sql
-- Query performance monitoring
CREATE EXTENSION pg_stat_statements;

-- Index usage analysis
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public';
```

**Application Profiling:**
```python
# Add profiling middleware
from werkzeug.middleware.profiler import ProfilerMiddleware
app.wsgi_app = ProfilerMiddleware(app.wsgi_app, profile_dir='/tmp/profiles')
```

**Redis Optimization:**
```bash
# Monitor Redis performance
docker-compose exec redis redis-cli info stats
docker-compose exec redis redis-cli info memory
```

## Cost Optimization

### Resource Allocation

**Development:**
- Minimal resource allocation
- Shared databases acceptable
- Cost: ~$10/month

**Staging:**
- Production-like resources
- Separate databases
- Cost: ~$50/month

**Production:**
- Right-sized for load
- Auto-scaling enabled
- Cost: Variable based on usage

### Usage-Based Optimization

**Database:**
- Right-size PostgreSQL instance
- Use read replicas for reporting
- Optimize query performance

**Redis:**
- Choose appropriate instance size
- Monitor memory usage
- Configure appropriate TTL

**Compute:**
- Use spot instances where possible
- Implement auto-scaling
- Monitor and optimize resource usage

## Conclusion

TradeSense AI's containerized architecture provides a solid foundation for scaling from development to enterprise-level production. The separation of concerns between synchronous API operations and asynchronous background processing enables independent scaling and optimization of each component.

Key success factors:
- **Monitoring First**: Implement comprehensive monitoring from day one
- **Incremental Scaling**: Scale components based on actual usage patterns
- **Security by Design**: Build security into infrastructure from the start
- **Automation**: Automate as much as possible (deployments, monitoring, backups)

The Docker-based architecture ensures consistency across development, staging, and production environments while providing the flexibility needed to adapt to changing business requirements.