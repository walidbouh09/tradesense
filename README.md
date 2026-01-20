# 🚀 TradeSense AI - Plateforme de Trading Prop FinTech

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18.2+-blue.svg)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

## TradeSense AI - Professional Prop Trading Platform

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)
[![React](https://img.shields.io/badge/react-18.2+-blue.svg)](https://reactjs.org)
[![Flask](https://img.shields.io/badge/flask-3.0+-red.svg)](https://flask.palletsprojects.com)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

> 🚀 A comprehensive, production-ready proprietary trading platform built with modern technologies. Features real-time market data, risk management, challenge-based trading, and advanced analytics.

## ✨ Features

### 🎯 Core Trading Features
- **Real-time Trading**: Live market data integration with WebSocket support
- **Multi-Asset Support**: Forex, Stocks, Cryptocurrencies, Commodities
- **Advanced Order Types**: Market, Limit, Stop, Stop-Limit orders
- **Portfolio Management**: Multiple portfolios with performance tracking
- **Risk Management**: Real-time risk assessment and automated controls

### 🏆 Challenge System
- **Trading Challenges**: Skill-based evaluation system
- **Multiple Challenge Types**: Beginner, Intermediate, Professional levels
- **Real-time Leaderboards**: Competitive ranking system
- **Funding Opportunities**: Successful traders get funded accounts
- **Performance Analytics**: Detailed trading statistics and insights

### 🔒 Security & Compliance
- **JWT Authentication**: Secure token-based authentication
- **Role-based Access Control**: Admin, Trader, Manager roles
- **Rate Limiting**: API protection against abuse
- **Data Encryption**: Secure data storage and transmission
- **Audit Trails**: Comprehensive logging and monitoring

### 📊 Analytics & Reporting
- **Performance Metrics**: P&L, Sharpe ratio, drawdown analysis
- **Risk Analytics**: VaR, correlation analysis, exposure monitoring
- **Custom Dashboards**: Personalized trading interfaces
- **Export Capabilities**: PDF reports and CSV data exports
- **Historical Analysis**: Backtesting and performance history

### 🎨 Modern UI/UX
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark/Light Themes**: Customizable interface themes
- **Real-time Updates**: Live data without page refreshes
- **Interactive Charts**: Advanced charting with technical indicators
- **Intuitive Navigation**: Clean and professional design

## 🏗️ Technology Stack

### Backend
- **Framework**: Flask 3.0 with SQLAlchemy ORM
- **Database**: PostgreSQL with Redis caching
- **Authentication**: JWT with Flask-JWT-Extended
- **Real-time**: WebSocket support via Flask-SocketIO
- **Background Tasks**: Celery with Redis broker
- **Market Data**: yfinance, Alpha Vantage, custom APIs
- **Testing**: Pytest with comprehensive test coverage

### Frontend
- **Framework**: React 18 with TypeScript
- **UI Library**: Material-UI (MUI) v5
- **State Management**: Zustand for state, React Query for API
- **Charts**: Lightweight Charts, Recharts
- **WebSocket**: Socket.IO client for real-time updates
- **Build Tool**: Create React App with custom optimizations

### Infrastructure
- **Containerization**: Docker with docker-compose
- **Reverse Proxy**: Nginx for production
- **Monitoring**: Sentry for error tracking
- **Logging**: Structured logging with JSON format
- **Deployment**: Production-ready with health checks

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ (recommended 3.10+)
- Node.js 16+ and npm
- PostgreSQL 12+
- Redis 6+
- Git

### Automated Setup

1. **Clone the repository**:
```bash
git clone https://github.com/your-username/tradesense.git
cd tradesense
```

2. **Run the setup script**:
```bash
python setup.py
```

The setup script will automatically:
- Check system requirements
- Create Python virtual environment
- Install all dependencies (backend and frontend)
- Create configuration files
- Set up database tables
- Create demo users and data

### Manual Setup

If you prefer manual installation:

#### Backend Setup

1. **Create virtual environment**:
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Setup environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize database**:
```bash
python init_db.py
```

#### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

## 🏃‍♂️ Running the Application

### Development Mode

1. **Start the backend**:
```bash
# Activate virtual environment first
python run.py
```

2. **Start the frontend** (in a new terminal):
```bash
cd frontend
npm start
```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - API Documentation: http://localhost:5000/docs

### Production Mode

Use Docker for production deployment:

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d
```

## 🔑 Demo Credentials

After running the setup, you can use these demo accounts:

| Role | Email | Password | Description |
|------|--------|----------|-------------|
| Admin | admin@tradesense.ai | admin123456 | Full system access |
| Trader | demo.trader@tradesense.ai | demo123456 | Demo trading account |
| User | john.doe@example.com | demo123456 | Regular user account |
| User | jane.smith@example.com | demo123456 | Regular user account |

## 📖 API Documentation

### Authentication
```bash
# Login
POST /api/v1/auth/login
{
  "email": "demo.trader@tradesense.ai",
  "password": "demo123456"
}

# Register
POST /api/v1/auth/register
{
  "email": "new@example.com",
  "password": "securepassword",
  "first_name": "John",
  "last_name": "Doe",
  "terms_accepted": true
}
```

### Trading Operations
```bash
# Create trade
POST /api/v1/trades
Authorization: Bearer <token>
{
  "symbol": "EURUSD",
  "side": "buy",
  "quantity": 1000,
  "order_type": "market"
}

# Get portfolio
GET /api/v1/portfolios
Authorization: Bearer <token>
```

### WebSocket Events
```javascript
// Connect to WebSocket
const socket = io('ws://localhost:5000', {
  auth: { token: 'your-jwt-token' }
});

// Subscribe to market data
socket.emit('subscribe_symbol', { symbol: 'EURUSD' });

// Listen for price updates
socket.on('price_update', (data) => {
  console.log('New price:', data);
});
```

## 🧪 Testing

### Backend Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=app --cov-report=html

# Run specific test file
python -m pytest tests/test_auth.py
```

### Frontend Tests
```bash
cd frontend
npm test

# Run with coverage
npm test -- --coverage
```

## 📁 Project Structure

```
tradesense/
├── app/                    # Backend application
│   ├── api/               # API endpoints
│   ├── models/            # Database models
│   ├── services/          # Business logic
│   ├── utils/             # Utility functions
│   └── __init__.py        # App factory
├── frontend/              # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   ├── stores/        # State management
│   │   └── utils/         # Utility functions
│   └── package.json
├── tests/                 # Backend tests
├── docker/                # Docker configurations
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker services
├── .env.example          # Environment template
└── README.md             # This file
```

## 🔧 Configuration

### Environment Variables

Key environment variables to configure:

```bash
# Application
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost:5432/tradesense_db

# Authentication
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_HOURS=1
JWT_REFRESH_DAYS=30

# Market Data
ALPHA_VANTAGE_API_KEY=your-api-key
YAHOO_FINANCE_ENABLED=True

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Payment Processing
STRIPE_SECRET_KEY=sk_test_your_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key
```

## 🚀 Deployment

### Docker Deployment

1. **Production docker-compose**:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

2. **Environment setup**:
```bash
# Copy production environment
cp .env.example .env.production
# Edit with production values
```

3. **SSL/TLS Setup**:
Configure Nginx with SSL certificates for HTTPS.

### Cloud Deployment

The application is ready for deployment on:
- **AWS**: EC2, ECS, or Elastic Beanstalk
- **Google Cloud**: Cloud Run, Compute Engine
- **Azure**: Container Instances, App Service
- **DigitalOcean**: Droplets, App Platform
- **Heroku**: Ready with Procfile

## 📊 Performance

### Benchmarks
- **API Response Time**: < 100ms average
- **WebSocket Latency**: < 50ms
- **Database Queries**: Optimized with indexes
- **Frontend Loading**: < 3s initial load
- **Real-time Updates**: Sub-second delivery

### Scalability
- **Horizontal Scaling**: Load balancer ready
- **Database**: Connection pooling and read replicas
- **Caching**: Redis for high-performance caching
- **Background Tasks**: Celery with multiple workers

## 🛠️ Development

### Code Quality
```bash
# Format code
black app/ tests/
cd frontend && npm run format

# Lint code
flake8 app/
cd frontend && npm run lint

# Type checking
mypy app/
cd frontend && npm run type-check
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run quality checks
6. Submit a pull request

## 🔐 Security

### Security Features
- **Authentication**: JWT with refresh tokens
- **Authorization**: Role-based access control
- **Rate Limiting**: API endpoint protection
- **Input Validation**: Comprehensive data validation
- **SQL Injection Prevention**: Parameterized queries
- **XSS Protection**: Content Security Policy
- **CSRF Protection**: CSRF tokens and SameSite cookies

### Security Best Practices
- Regular dependency updates
- Security headers implementation
- Secure session management
- Input sanitization
- Error message sanitization
- Audit logging

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

### Getting Help
- **Documentation**: Check the `/docs` directory
- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **Email**: support@tradesense.ai

### Contributing
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🎯 Roadmap

### Version 2.0 (Planned)
- [ ] Mobile app (React Native)
- [ ] Advanced AI trading signals
- [ ] Social trading features
- [ ] Options and futures trading
- [ ] Multi-language support
- [ ] Advanced portfolio analytics

### Version 1.1 (In Progress)
- [ ] Improved charting tools
- [ ] Email notifications
- [ ] Advanced risk management
- [ ] API rate limiting enhancements
- [ ] Performance optimizations

## 📈 Screenshots

### Dashboard
![Dashboard](docs/images/dashboard.png)

### Trading Interface
![Trading](docs/images/trading.png)

### Analytics
![Analytics](docs/images/analytics.png)

## 🏆 Acknowledgments

- **Flask Community** for the excellent web framework
- **React Team** for the powerful frontend library
- **Material-UI** for beautiful React components
- **PostgreSQL** for reliable data storage
- **Redis** for high-performance caching
- **Socket.IO** for real-time communication

---

<div align="center">

**[Website](https://tradesense.ai) • [Documentation](docs/) • [API Reference](docs/api.md) • [Contributing](CONTRIBUTING.md)**

Made with ❤️ by the TradeSense AI Team

</div>