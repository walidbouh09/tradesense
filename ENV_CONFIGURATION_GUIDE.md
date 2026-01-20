# Environment Configuration Guide

## Quick Setup

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Update critical values** in `.env`:
   - Database credentials
   - Secret keys
   - Admin password

3. **Start the application**:
   ```bash
   python app/main.py
   ```

---

## Critical Variables (Must Change in Production)

### Security Keys
```bash
SECRET_KEY=your-super-secret-key-min-32-chars
SECURITY_SECRET_KEY=your-super-secret-key-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars
CMI_SECRET_KEY=your-cmi-secret-key
```

**How to generate secure keys**:
```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

### Database
```bash
DATABASE_URL=postgresql://user:password@host:port/database
DB_USERNAME=tradesense_user
DB_PASSWORD=strong_password_here
```

### Admin Account
```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong_admin_password
ADMIN_EMAIL=admin@yourdomain.com
```

---

## Configuration by Feature

### 1. Payment Simulation

**Required for payment processing**:
```bash
# CMI (Moroccan Gateway)
CMI_MERCHANT_ID=TEST_MERCHANT_001
CMI_SECRET_KEY=test_secret_key_12345
CMI_API_URL=https://testpayment.cmi.co.ma

# Currency conversion
MAD_TO_USD_RATE=0.10

# Simulation mode (ALWAYS true for development)
PAYMENT_SIMULATION_MODE=true
```

**Optional - Crypto payments**:
```bash
BTC_WALLET=your_btc_wallet_address
ETH_WALLET=your_eth_wallet_address
USDT_WALLET=your_usdt_wallet_address

# Exchange rates (update periodically)
BTC_USD_RATE=43000.00
ETH_USD_RATE=2300.00
USDT_USD_RATE=1.00
```

**Optional - PayPal**:
```bash
PAYPAL_ENABLED=true
PAYPAL_MODE=sandbox  # or 'live' for production
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_SECRET=your_paypal_secret
```

### 2. Market Data (Morocco Integration)

**Casablanca Stock Exchange scraping**:
```bash
CASABLANCA_SCRAPING_ENABLED=true
CASABLANCA_BASE_URL=https://www.casablanca-bourse.com
CASABLANCA_RATE_LIMIT_SECONDS=1
CASABLANCA_CACHE_TTL_SECONDS=300
```

**Yahoo Finance**:
```bash
YFINANCE_ENABLED=true
YFINANCE_TIMEOUT=10
```

**Market data caching**:
```bash
MARKET_DATA_CACHE_ENABLED=true
MARKET_DATA_CACHE_TTL=300
MARKET_DATA_RETRY_ATTEMPTS=3
```

### 3. Challenge Configuration

**Pricing tiers (MAD)**:
```bash
STARTER_PRICE_MAD=200.00
PRO_PRICE_MAD=500.00
ELITE_PRICE_MAD=1000.00
```

**Initial balances**:
```bash
STARTER_INITIAL_BALANCE=10000.00
PRO_INITIAL_BALANCE=25000.00
ELITE_INITIAL_BALANCE=50000.00
```

**Risk parameters**:
```bash
MAX_DAILY_DRAWDOWN=5.0      # 5%
MAX_TOTAL_DRAWDOWN=10.0     # 10%
PROFIT_TARGET=8.0           # 8%
```

### 4. Database Configuration

**PostgreSQL (Production)**:
```bash
DATABASE_URL=postgresql://user:pass@host:5432/database
DB_HOST=localhost
DB_PORT=5432
DB_USERNAME=tradesense_user
DB_PASSWORD=your_password
DB_DATABASE=tradesense
```

**SQLite (Development)**:
```bash
DATABASE_URL=sqlite:///./tradesense.db
```

**Connection pooling**:
```bash
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
```

### 5. Redis Configuration

**Basic setup**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0
```

### 6. CORS Configuration

**Development**:
```bash
CORS_ENABLED=true
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
CORS_ALLOW_CREDENTIALS=true
```

**Production**:
```bash
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### 7. Logging

**Basic logging**:
```bash
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json             # json or text
LOG_FILE=logs/tradesense.log
LOG_TO_CONSOLE=true
LOG_TO_FILE=true
```

### 8. Notifications (Optional)

**Email (SMTP)**:
```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@tradesense.ai
```

**SMS (Twilio)**:
```bash
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### 9. Background Workers

**Celery configuration**:
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
WORKER_CONCURRENCY=4
```

### 10. Monitoring (Optional)

**Sentry (Error tracking)**:
```bash
SENTRY_ENABLED=true
SENTRY_DSN=your_sentry_dsn
SENTRY_ENVIRONMENT=production
```

---

## Environment-Specific Configurations

### Development Environment

```bash
APP_ENV=development
APP_DEBUG=true
FLASK_DEBUG=true
LOG_LEVEL=DEBUG
TESTING=false
USE_MOCK_DATA=false
PAYMENT_SIMULATION_MODE=true
DATABASE_URL=sqlite:///./tradesense.db
```

### Testing Environment

```bash
APP_ENV=testing
APP_DEBUG=true
TESTING=true
USE_MOCK_DATA=true
PAYMENT_SIMULATION_MODE=true
DATABASE_URL=sqlite:///./test_tradesense.db
LOG_LEVEL=WARNING
```

### Production Environment

```bash
APP_ENV=production
APP_DEBUG=false
FLASK_DEBUG=false
LOG_LEVEL=INFO
TESTING=false
USE_MOCK_DATA=false
PAYMENT_SIMULATION_MODE=false  # Only if using real payments
DATABASE_URL=postgresql://user:pass@prod-host:5432/tradesense
SENTRY_ENABLED=true
CORS_ORIGINS=https://yourdomain.com
```

---

## Feature Flags

Enable/disable features without code changes:

```bash
FEATURE_SOCIAL_TRADING=false
FEATURE_COPY_TRADING=false
FEATURE_LEADERBOARD=true
FEATURE_REWARDS=true
FEATURE_REFERRALS=false
FEATURE_ANALYTICS=true
FEATURE_BACKTESTING=true
```

---

## Common Configurations

### Minimal Setup (Quick Start)

```bash
# Application
APP_DEBUG=true
APP_PORT=5000

# Database (SQLite for quick start)
DATABASE_URL=sqlite:///./tradesense.db

# Security
SECRET_KEY=change-this-to-random-string

# Payment (Simulation)
PAYMENT_SIMULATION_MODE=true
CMI_MERCHANT_ID=TEST_MERCHANT_001
CMI_SECRET_KEY=test_secret_key

# Market Data
YFINANCE_ENABLED=true
CASABLANCA_SCRAPING_ENABLED=true
```

### Full Development Setup

```bash
# Application
APP_DEBUG=true
APP_PORT=5000
FLASK_DEBUG=true

# Database (PostgreSQL)
DATABASE_URL=postgresql://tradesense_user:tradesense_pass@localhost:5432/tradesense

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-key-change-in-production

# Payment Simulation
PAYMENT_SIMULATION_MODE=true
CMI_MERCHANT_ID=TEST_MERCHANT_001
CMI_SECRET_KEY=test_secret_key
PAYPAL_ENABLED=false

# Market Data
YFINANCE_ENABLED=true
CASABLANCA_SCRAPING_ENABLED=true
MARKET_DATA_CACHE_ENABLED=true

# CORS
CORS_ENABLED=true
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=DEBUG
LOG_TO_CONSOLE=true

# Features
FEATURE_LEADERBOARD=true
FEATURE_REWARDS=true
FEATURE_ANALYTICS=true
```

### Production Setup

```bash
# Application
APP_ENV=production
APP_DEBUG=false
APP_PORT=5000

# Database (PostgreSQL with SSL)
DATABASE_URL=postgresql://user:pass@prod-db.example.com:5432/tradesense?sslmode=require

# Redis (with password)
REDIS_URL=redis://:password@prod-redis.example.com:6379/0

# Security (STRONG KEYS!)
SECRET_KEY=<generate-with-openssl-rand-base64-32>
JWT_SECRET_KEY=<generate-with-openssl-rand-base64-32>
CMI_SECRET_KEY=<your-real-cmi-secret>

# Payment (Real or Simulation)
PAYMENT_SIMULATION_MODE=false  # Set to true if still testing
CMI_MERCHANT_ID=<your-real-merchant-id>
PAYPAL_ENABLED=true
PAYPAL_MODE=live
PAYPAL_CLIENT_ID=<your-real-client-id>
PAYPAL_SECRET=<your-real-secret>

# Market Data
YFINANCE_ENABLED=true
CASABLANCA_SCRAPING_ENABLED=true
MARKET_DATA_CACHE_ENABLED=true

# CORS (Your domains only)
CORS_ENABLED=true
CORS_ORIGINS=https://tradesense.ai,https://app.tradesense.ai

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE=/var/log/tradesense/app.log

# Monitoring
SENTRY_ENABLED=true
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=production

# Email
SMTP_ENABLED=true
SMTP_HOST=smtp.sendgrid.net
SMTP_USERNAME=apikey
SMTP_PASSWORD=<your-sendgrid-api-key>

# Admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
ADMIN_EMAIL=admin@tradesense.ai
```

---

## Validation Checklist

Before deploying, verify:

### Security ✓
- [ ] All SECRET_KEY values changed from defaults
- [ ] Strong database password set
- [ ] Strong admin password set
- [ ] JWT keys are unique and secure
- [ ] CMI secret key is production key (if using real payments)

### Database ✓
- [ ] DATABASE_URL points to correct database
- [ ] Database credentials are correct
- [ ] Database is accessible from application
- [ ] Connection pooling configured appropriately

### Payment ✓
- [ ] PAYMENT_SIMULATION_MODE set correctly
- [ ] CMI credentials configured (if using CMI)
- [ ] PayPal credentials configured (if using PayPal)
- [ ] Crypto wallets configured (if using crypto)
- [ ] Currency conversion rates updated

### Market Data ✓
- [ ] YFINANCE_ENABLED=true
- [ ] CASABLANCA_SCRAPING_ENABLED=true
- [ ] Rate limiting configured
- [ ] Caching enabled

### CORS ✓
- [ ] CORS_ORIGINS includes all frontend domains
- [ ] No wildcard (*) in production
- [ ] HTTPS URLs in production

### Logging ✓
- [ ] LOG_LEVEL appropriate for environment
- [ ] Log file path is writable
- [ ] Log rotation configured

### Monitoring ✓
- [ ] Sentry configured (production)
- [ ] Error tracking tested
- [ ] Alerts configured

---

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
psql -h localhost -U tradesense_user -d tradesense

# Test connection string
python -c "from sqlalchemy import create_engine; engine = create_engine('your_database_url'); print(engine.connect())"
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Should return: PONG
```

### Payment Simulation Not Working

```bash
# Verify simulation mode is enabled
echo $PAYMENT_SIMULATION_MODE  # Should be 'true'

# Check CMI configuration
echo $CMI_MERCHANT_ID
echo $CMI_SECRET_KEY
```

### Market Data Issues

```bash
# Test Yahoo Finance
python -c "import yfinance as yf; print(yf.Ticker('AAPL').info['regularMarketPrice'])"

# Test Casablanca scraping
curl http://localhost:5000/api/market/morocco/IAM
```

### CORS Issues

```bash
# Check CORS configuration
echo $CORS_ORIGINS

# Test CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS http://localhost:5000/api/market/status
```

---

## Security Best Practices

1. **Never commit `.env` to version control**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use environment-specific files**
   - `.env.development`
   - `.env.testing`
   - `.env.production`

3. **Rotate secrets regularly**
   - Change SECRET_KEY every 90 days
   - Update JWT keys periodically
   - Rotate database passwords

4. **Use secret management in production**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault
   - Google Secret Manager

5. **Limit access to `.env` file**
   ```bash
   chmod 600 .env
   ```

---

## Quick Reference

### Generate Secure Keys
```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32

# UUID
python -c "import uuid; print(str(uuid.uuid4()))"
```

### Check Configuration
```bash
# View all environment variables
env | grep -E "APP_|DB_|REDIS_|CMI_"

# Test database connection
python -c "from app.main import app; print('DB OK')"

# Test Redis connection
redis-cli ping
```

### Backup Configuration
```bash
# Backup .env file (encrypted)
gpg -c .env

# Restore
gpg .env.gpg
```

---

## Support

For configuration issues:
1. Check this guide
2. Review `.env.example`
3. Check application logs: `logs/tradesense.log`
4. Verify environment variables are loaded: `env | grep APP_`

---

**Last Updated**: January 19, 2026  
**Version**: 1.0.0
