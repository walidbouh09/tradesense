# 🚀 TradeSense Pro

**Professional Proprietary Trading Platform**

A modern, scalable prop trading platform built with FastAPI, Next.js, and cutting-edge technologies. TradeSense Pro enables traders to prove their skills through structured challenges and get funded with real capital.

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/tradesense/tradesense-pro)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)](https://nodejs.org)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://docker.com)

## ✨ Features

### 🎯 **Core Trading Platform**
- **Multi-Phase Challenges**: Phase 1 → Phase 2 → Funded Account progression
- **Real-Time Risk Management**: Instant rule evaluation and position monitoring
- **Advanced Order Management**: Market, limit, stop orders with smart routing
- **Multi-Asset Support**: Stocks, Forex, Crypto, Commodities
- **Performance Analytics**: Comprehensive trading metrics and reporting

### 💻 **Modern Tech Stack**
- **Backend**: FastAPI with async/await, PostgreSQL, Redis
- **Frontend**: Next.js 14 with TypeScript, Tailwind CSS
- **Real-Time**: WebSocket for live updates
- **Background Tasks**: Celery for async processing
- **Monitoring**: Prometheus, Grafana, structured logging
- **Infrastructure**: Docker, Kubernetes, CI/CD pipelines

### 🔒 **Enterprise Security**
- JWT authentication with refresh tokens
- Role-based access control (RBAC)
- Data encryption at rest and in transit
- Rate limiting and DDoS protection
- Comprehensive audit logging
- GDPR & compliance ready

### 📊 **Business Intelligence**
- Real-time trader performance metrics
- Risk analytics and reporting
- Revenue and conversion tracking
- Admin dashboard with KPIs
- Automated compliance reporting

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js App   │    │   FastAPI API   │    │  PostgreSQL DB  │
│   (Frontend)    │◄──►│   (Backend)     │◄──►│   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │      Redis      │              │
         │              │ (Cache/Broker)  │              │
         │              └─────────────────┘              │
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │  Celery Worker  │    │   Monitoring    │
│ (Load Balancer) │    │ (Background)    │    │ (Prometheus)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **Node.js 18+**
- **Docker & Docker Compose**
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/tradesense/tradesense-pro.git
cd tradesense-pro
```

### 2. Run Setup Script

```bash
# Make setup script executable
chmod +x setup.sh

# Run automated setup
./setup.sh
```

The setup script will:
- ✅ Check system requirements
- ✅ Create directory structure
- ✅ Set up Python virtual environment
- ✅ Install dependencies
- ✅ Configure database and Redis
- ✅ Create environment files
- ✅ Set up development tools

### 3. Start Development Environment

```bash
# Option 1: Use helper script
./scripts/start-dev.sh

# Option 2: Start with Docker Compose
docker-compose up -d

# Option 3: Start services manually
source venv/bin/activate
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:3000/admin

## 📁 Project Structure

```
tradesense-pro/
├── backend/                  # FastAPI Backend
│   ├── app/
│   │   ├── core/            # Configuration & database
│   │   ├── api/v1/          # API endpoints
│   │   ├── models/          # Database models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── workers/         # Background tasks
│   │   └── utils/           # Utilities
│   └── requirements.txt     # Python dependencies
│
├── frontend/                 # Next.js Frontend
│   ├── src/
│   │   ├── app/            # App Router pages
│   │   ├── components/      # React components
│   │   ├── lib/            # Utilities
│   │   ├── hooks/          # Custom hooks
│   │   ├── store/          # State management
│   │   └── types/          # TypeScript types
│   └── package.json        # Node.js dependencies
│
├── infrastructure/          # DevOps & Infrastructure
│   ├── docker/             # Docker configurations
│   ├── k8s/               # Kubernetes manifests
│   └── terraform/         # Infrastructure as Code
│
├── docs/                   # Documentation
├── scripts/               # Utility scripts
└── docker-compose.yml     # Development environment
```

## 🛠️ Development

### Backend Development

```bash
# Activate virtual environment
source venv/bin/activate

# Start development server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Format code
black app/
isort app/

# Type checking
mypy app/
```

### Frontend Development

```bash
# Start development server
cd frontend
npm run dev

# Run tests
npm test

# Build for production
npm run build

# Format code
npm run format

# Type checking
npm run type-check
```

### Database Management

```bash
# Create migration
cd backend
alembic revision --autogenerate -m "Add new table"

# Run migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Reset database (development only)
alembic downgrade base
alembic upgrade head
```

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_challenges.py

# Run tests with verbose output
pytest -v
```

### Frontend Tests

```bash
# Run unit tests
npm test

# Run tests in watch mode
npm run test:watch

# Run e2e tests
npm run e2e

# Generate coverage report
npm run test:coverage
```

## 📦 Deployment

### Development Deployment

```bash
# Start all services
docker-compose up -d

# Start with monitoring
docker-compose --profile monitoring up -d

# View logs
docker-compose logs -f backend
```

### Production Deployment

```bash
# Build production images
./scripts/build-prod.sh

# Deploy with production compose file
docker-compose -f docker-compose.prod.yml up -d

# Or use Kubernetes
kubectl apply -f infrastructure/k8s/
```

### Environment Variables

#### Backend (.env)
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# External APIs
ALPHA_VANTAGE_API_KEY=your-api-key
STRIPE_SECRET_KEY=your-stripe-key

# Features
FEATURE_ADVANCED_ANALYTICS=true
```

#### Frontend (.env.local)
```env
# API
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Application
NEXT_PUBLIC_APP_NAME="TradeSense Pro"
NEXT_PUBLIC_ENVIRONMENT=development
```

## 🔧 Configuration

### Customize Challenge Rules

Edit `backend/app/services/challenge_engine.py`:

```python
# Challenge configuration
DEFAULT_RULES = {
    'max_daily_drawdown': 0.05,    # 5%
    'max_total_drawdown': 0.10,    # 10%
    'profit_target': 0.10,         # 10%
    'min_trading_days': 5,
    'max_position_size': 0.10,     # 10% of account
}
```

### Customize UI Theme

Edit `frontend/tailwind.config.js`:

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
      },
    },
  },
}
```

## 📊 Monitoring & Observability

### Metrics Dashboard

Access Grafana at http://localhost:3001 (admin/admin123)

Key metrics monitored:
- API response times
- Database connection pool
- Active trading sessions
- Challenge success rates
- Revenue metrics

### Logs

```bash
# View application logs
docker-compose logs -f backend frontend

# View structured logs
tail -f logs/app.log | jq

# Search logs
grep "ERROR" logs/app.log
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Database health
docker exec tradesense-postgres pg_isready

# Redis health
docker exec tradesense-redis redis-cli ping
```

## 🔐 Security

### Authentication Flow

1. User registers/logs in → JWT tokens issued
2. Access token (short-lived) for API requests
3. Refresh token (long-lived) for token renewal
4. Automatic token refresh in frontend

### API Security

- Rate limiting: 100 requests/minute per IP
- CORS configured for frontend origins only
- SQL injection protection via SQLAlchemy ORM
- Input validation with Pydantic schemas
- Password hashing with bcrypt

### Data Protection

- Database connections encrypted (SSL)
- Sensitive data encrypted at rest
- PII anonymization for analytics
- GDPR compliance tools included

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push branch: `git push origin feature/amazing-feature`
5. Open Pull Request

### Code Standards

- **Backend**: PEP 8, type hints, docstrings
- **Frontend**: ESLint, Prettier, TypeScript strict mode
- **Commits**: Conventional Commits format
- **Tests**: Minimum 80% coverage required

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## 📚 API Documentation

### Authentication

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Use token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/challenges"
```

### Core Endpoints

```bash
# Create challenge
POST /api/v1/challenges

# Execute trade
POST /api/v1/trades

# Get analytics
GET /api/v1/analytics/performance

# Admin functions
GET /api/v1/admin/users
```

Full API documentation: http://localhost:8000/docs

## 🎯 Roadmap

### Phase 1 - Core Platform ✅
- [x] User authentication
- [x] Challenge management
- [x] Trading execution
- [x] Risk management
- [x] Basic analytics

### Phase 2 - Advanced Features 🚧
- [ ] Social trading
- [ ] Copy trading
- [ ] Advanced analytics
- [ ] Mobile app
- [ ] Multi-language support

### Phase 3 - Scale & Enterprise 📋
- [ ] Kubernetes deployment
- [ ] Advanced monitoring
- [ ] A/B testing framework
- [ ] White-label solutions
- [ ] Regulatory compliance

## 🆘 Support

### Getting Help

1. **Documentation**: Check the `/docs` folder
2. **Issues**: Open a GitHub issue
3. **Discussions**: Use GitHub Discussions
4. **Email**: support@tradesense.ma

### Common Issues

**Database Connection Error**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Reset database
docker-compose down -v postgres
docker-compose up -d postgres
```

**Frontend Build Issues**
```bash
# Clear cache
rm -rf frontend/.next frontend/node_modules
cd frontend && npm install
```

**Import Errors**
```bash
# Check virtual environment
source venv/bin/activate
which python  # Should point to venv/bin/python
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FastAPI**: Modern Python web framework
- **Next.js**: React framework for production
- **PostgreSQL**: Reliable database system
- **Redis**: Fast in-memory data store
- **Tailwind CSS**: Utility-first CSS framework

---

**Built with ❤️ by the TradeSense team**

For more information, visit our [website](https://tradesense.ma) or follow us on [Twitter](https://twitter.com/tradesense).