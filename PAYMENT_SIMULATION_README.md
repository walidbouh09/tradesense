# Payment Simulation & Access Control - TradeSense AI

## Overview

This document describes the **payment simulation** and **access control** system for TradeSense AI. The system provides a complete payment flow simulation **without processing real money**, ensuring deterministic behavior for development and testing.

## 🎯 Key Features

### Payment Simulation
- ✅ **NO REAL MONEY PROCESSING** - All payments are simulated
- ✅ **Deterministic Behavior** - Predictable outcomes for testing
- ✅ **Multiple Payment Providers**:
  - CMI (Moroccan payment gateway)
  - Crypto (Bitcoin, Ethereum, USDT)
  - PayPal (optional via environment variables)

### Access Control
- ✅ **Trading Restrictions** - Users CANNOT trade without an active challenge
- ✅ **Challenge Lifecycle** - Automatic activation after successful payment
- ✅ **Permission System** - Role-based access control (USER, ADMIN, SUPERADMIN)

## 💰 Pricing Tiers

| Tier | Price (MAD) | Price (USD) | Initial Balance | Max Daily Drawdown | Max Total Drawdown | Profit Target |
|------|-------------|-------------|-----------------|--------------------|--------------------|---------------|
| **Starter** | 200 DH | $20 | $10,000 | 5% | 10% | 8% |
| **Pro** | 500 DH | $50 | $25,000 | 5% | 10% | 8% |
| **Elite** | 1000 DH | $100 | $50,000 | 5% | 10% | 8% |

## 🔧 Environment Configuration

### Required (All Providers)
```bash
# Database
DATABASE_URL=postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense

# CMI Configuration (Simulated)
CMI_MERCHANT_ID=TEST_MERCHANT_001
CMI_SECRET_KEY=test_secret_key_12345
```

### Optional (PayPal)
```bash
# Enable PayPal
PAYPAL_ENABLED=true
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_SECRET=your_paypal_secret
```

### Optional (Crypto Wallets)
```bash
# Crypto wallet addresses (simulated)
BTC_WALLET=1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
ETH_WALLET=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
USDT_WALLET=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

## 📡 API Endpoints

### Payment Simulation

#### 1. Get Pricing
```http
GET /api/payment-simulation/pricing
```

**Response:**
```json
{
  "success": true,
  "pricing": {
    "STARTER": {
      "tier": "STARTER",
      "price_mad": 200.0,
      "price_usd": 20.0,
      "currency": "MAD",
      "description": "Perfect for beginners - Start your trading journey",
      "challenge_config": {
        "initial_balance": 10000.0,
        "max_daily_drawdown_percent": 5.0,
        "max_total_drawdown_percent": 10.0,
        "profit_target_percent": 8.0
      }
    },
    "PRO": { ... },
    "ELITE": { ... }
  },
  "currency": "MAD",
  "note": "Simulated pricing - no real money will be charged",
  "providers": [
    {
      "name": "CMI",
      "description": "Moroccan payment gateway",
      "supported": true
    },
    {
      "name": "Crypto",
      "description": "Bitcoin, Ethereum, USDT",
      "supported": true
    },
    {
      "name": "PayPal",
      "description": "PayPal payments",
      "supported": false
    }
  ]
}
```

#### 2. Initiate Payment
```http
POST /api/payment-simulation/initiate
Content-Type: application/json

{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "tier": "STARTER",
  "provider": "CMI",
  "return_url": "http://localhost:3000/payment/success"
}
```

**Response (CMI):**
```json
{
  "success": true,
  "challenge_id": "uuid",
  "payment": {
    "payment_id": "CMI_ABC123DEF456",
    "provider": "CMI",
    "status": "PENDING",
    "amount": 200.0,
    "currency": "MAD",
    "tier": "STARTER",
    "user_id": "uuid",
    "transaction_ref": "A1B2C3D4E5F6",
    "signature": "sha256_hash",
    "redirect_url": "https://testpayment.cmi.co.ma/payment?ref=A1B2C3D4E5F6",
    "return_url": "http://localhost:3000/payment/success",
    "created_at": "2024-01-19T10:00:00Z",
    "expires_at": "2024-01-19T10:15:00Z",
    "simulation_note": "This is a SIMULATED payment - no real money will be processed"
  },
  "message": "Payment initiated successfully"
}
```

**For Crypto:**
```json
{
  "user_id": "uuid",
  "tier": "PRO",
  "provider": "CRYPTO",
  "crypto_type": "BTC"
}
```

**Response (Crypto):**
```json
{
  "success": true,
  "challenge_id": "uuid",
  "payment": {
    "payment_id": "CRYPTO_ABC123DEF456",
    "provider": "CRYPTO",
    "crypto_type": "BTC",
    "status": "PENDING",
    "amount_mad": 500.0,
    "amount_usd": 50.0,
    "crypto_amount": 0.00116279,
    "crypto_rate": 43000.0,
    "wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "tier": "PRO",
    "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=...",
    "instructions": "Send exactly 0.00116279 BTC to the wallet address above",
    "expires_at": "2024-01-19T11:00:00Z",
    "simulation_note": "This is a SIMULATED payment - no real crypto will be transferred"
  }
}
```

#### 3. Confirm Payment (Simulate Success)
```http
POST /api/payment-simulation/confirm
Content-Type: application/json

{
  "payment_id": "CMI_ABC123DEF456",
  "success": true
}
```

**Response:**
```json
{
  "success": true,
  "payment_result": {
    "payment_id": "CMI_ABC123DEF456",
    "transaction_ref": "A1B2C3D4E5F6",
    "status": "SUCCESS",
    "provider": "CMI",
    "cmi_response_code": "00",
    "message": "Payment processed successfully",
    "processed_at": "2024-01-19T10:05:00Z",
    "simulation": true
  },
  "challenge_id": "uuid",
  "challenge_status": "ACTIVE",
  "message": "Payment confirmed successfully"
}
```

#### 4. Get Payment Status
```http
GET /api/payment-simulation/status/{payment_id}
```

**Response:**
```json
{
  "payment_id": "CMI_ABC123DEF456",
  "status": "SUCCESS",
  "provider": "CMI",
  "amount": 200.0,
  "currency": "MAD",
  "challenge_id": "uuid",
  "challenge_status": "ACTIVE",
  "initiated_at": "2024-01-19T10:00:00Z",
  "processed_at": "2024-01-19T10:05:00Z"
}
```

#### 5. Get User Payments
```http
GET /api/payment-simulation/user-payments/{user_id}
```

**Response:**
```json
{
  "user_id": "uuid",
  "payments": [
    {
      "payment_id": "CMI_ABC123DEF456",
      "status": "SUCCESS",
      "provider": "CMI",
      "amount": 200.0,
      "currency": "MAD",
      "challenge_id": "uuid",
      "challenge_type": "STARTER",
      "challenge_status": "ACTIVE",
      "initiated_at": "2024-01-19T10:00:00Z",
      "processed_at": "2024-01-19T10:05:00Z"
    }
  ],
  "total_payments": 1
}
```

### Access Control

#### 1. Check Trading Access
```http
GET /api/access/can-trade/{user_id}
```

**Response (Allowed):**
```json
{
  "allowed": true,
  "challenge": {
    "id": "uuid",
    "status": "ACTIVE",
    "challenge_type": "STARTER",
    "initial_balance": 10000.0,
    "current_equity": 10000.0,
    "started_at": "2024-01-19T10:05:00Z",
    "payment_status": "SUCCESS"
  },
  "message": "Trading access granted"
}
```

**Response (Denied):**
```json
{
  "allowed": false,
  "reason": "no_active_challenge",
  "message": "No active challenge found. Please purchase a challenge to start trading.",
  "action_required": "Purchase a challenge to start trading"
}
```

#### 2. Get Active Challenge
```http
GET /api/access/active-challenge/{user_id}
```

**Response:**
```json
{
  "active_challenge": {
    "id": "uuid",
    "status": "ACTIVE",
    "challenge_type": "STARTER",
    "initial_balance": 10000.0,
    "current_equity": 10000.0,
    "started_at": "2024-01-19T10:05:00Z",
    "payment_status": "SUCCESS",
    "payment_provider": "CMI"
  },
  "message": "Active challenge found"
}
```

#### 3. Get User Permissions
```http
GET /api/access/permissions/{user_role}
```

**Response:**
```json
{
  "role": "USER",
  "permissions": [
    "view_challenges",
    "create_challenge",
    "trade",
    "view_analytics"
  ]
}
```

#### 4. Check Specific Permission
```http
POST /api/access/check-permission
Content-Type: application/json

{
  "user_role": "USER",
  "permission": "trade"
}
```

**Response:**
```json
{
  "role": "USER",
  "permission": "trade",
  "has_permission": true
}
```

#### 5. Check Account Status
```http
GET /api/access/account-status/{user_id}
```

**Response:**
```json
{
  "user_id": "uuid",
  "is_active": true,
  "reason": null,
  "message": "Account is active"
}
```

## 🔒 Access Control Rules

### Trading Access Requirements

Users **CANNOT** trade unless ALL of the following are true:

1. ✅ User account is ACTIVE
2. ✅ User has an ACTIVE challenge
3. ✅ Challenge payment is SUCCESS
4. ✅ Challenge has been started (started_at is not null)
5. ✅ Challenge has not ended (ended_at is null)

### Access Denial Reasons

| Reason | Description | Action Required |
|--------|-------------|-----------------|
| `no_active_challenge` | No active challenge found | Purchase a challenge |
| `payment_required` | Payment not completed | Complete payment |
| `challenge_not_started` | Challenge not started | Start challenge |
| `challenge_ended` | Challenge has ended | Purchase new challenge |
| `challenge_failed` | Challenge failed | Purchase new challenge |
| `account_suspended` | Account suspended | Contact support |

## 🔐 Using Access Control in Code

### Decorator for Trading Endpoints

```python
from app.access_control import require_active_challenge

@api_bp.route('/trades/execute', methods=['POST'])
@require_active_challenge
def execute_trade():
    """
    Execute a trade (requires active challenge).
    
    The decorator automatically checks trading access.
    If access is denied, returns 403 with details.
    """
    # Access granted - challenge info available in request.active_challenge
    challenge = request.active_challenge
    
    # Execute trade logic
    return jsonify({'success': True})
```

### Manual Access Check

```python
from app.access_control import access_control

def my_trading_function(user_id: str):
    # Check if user can trade
    can_trade, denial_reason, message = access_control.can_trade(user_id)
    
    if not can_trade:
        return {
            'error': message,
            'reason': denial_reason.value
        }, 403
    
    # Proceed with trading logic
    pass
```

### Permission Check

```python
from app.access_control import access_control, Permission

def admin_function(user_role: str):
    if not access_control.has_permission(user_role, Permission.ADMIN_ACCESS):
        return {'error': 'Insufficient permissions'}, 403
    
    # Admin logic
    pass
```

## 🧪 Testing Payment Flow

### Test Scenario 1: CMI Payment (Success)

```bash
# 1. Get pricing
curl http://localhost:5000/api/payment-simulation/pricing

# 2. Initiate CMI payment
curl -X POST http://localhost:5000/api/payment-simulation/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "tier": "STARTER",
    "provider": "CMI",
    "return_url": "http://localhost:3000/payment/success"
  }'

# 3. Simulate successful payment
curl -X POST http://localhost:5000/api/payment-simulation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "CMI_ABC123DEF456",
    "success": true
  }'

# 4. Check trading access (should be allowed now)
curl http://localhost:5000/api/access/can-trade/550e8400-e29b-41d4-a716-446655440000
```

### Test Scenario 2: Crypto Payment (Bitcoin)

```bash
# 1. Initiate crypto payment
curl -X POST http://localhost:5000/api/payment-simulation/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "tier": "PRO",
    "provider": "CRYPTO",
    "crypto_type": "BTC"
  }'

# 2. Simulate crypto confirmation
curl -X POST http://localhost:5000/api/payment-simulation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "CRYPTO_ABC123DEF456",
    "transaction_hash": "0xabc123def456...",
    "confirmations": 6
  }'
```

### Test Scenario 3: Payment Failure

```bash
# Simulate failed payment
curl -X POST http://localhost:5000/api/payment-simulation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "CMI_ABC123DEF456",
    "success": false
  }'

# Check trading access (should be denied)
curl http://localhost:5000/api/access/can-trade/550e8400-e29b-41d4-a716-446655440000
```

## 📊 Payment Flow Diagram

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       │ 1. Select Tier & Provider
       ▼
┌─────────────────────────┐
│  Initiate Payment       │
│  POST /initiate         │
└──────┬──────────────────┘
       │
       │ 2. Creates PENDING Challenge
       │    Creates PENDING Payment
       ▼
┌─────────────────────────┐
│  Payment Provider       │
│  (CMI/Crypto/PayPal)    │
└──────┬──────────────────┘
       │
       │ 3. User Completes Payment
       │    (Simulated)
       ▼
┌─────────────────────────┐
│  Confirm Payment        │
│  POST /confirm          │
└──────┬──────────────────┘
       │
       │ 4. Updates Payment → SUCCESS
       │    Updates Challenge → ACTIVE
       │    Sets started_at timestamp
       ▼
┌─────────────────────────┐
│  Trading Enabled        │
│  User Can Trade         │
└─────────────────────────┘
```

## 🚨 Important Notes

### Security
- ✅ All payments are **SIMULATED** - no real money is processed
- ✅ Payment signatures are generated for testing purposes only
- ✅ In production, implement proper webhook signature verification
- ✅ Use HTTPS for all payment-related endpoints

### Database
- ✅ Challenges are created in PENDING state
- ✅ Successful payment activates challenge (PENDING → ACTIVE)
- ✅ Failed payment keeps challenge in PENDING state
- ✅ Users can only have ONE active challenge at a time

### Access Control
- ✅ Trading endpoints MUST check access before execution
- ✅ Use `@require_active_challenge` decorator for protection
- ✅ Access checks are performed on every trading operation
- ✅ Challenge status is verified in real-time

## 🔄 Challenge Lifecycle

```
PENDING → ACTIVE → FAILED/FUNDED
   ↑         ↑
   │         │
   │         └─ Payment SUCCESS + started_at set
   │
   └─ Challenge created after payment initiation
```

## 📝 Environment Variables Summary

```bash
# Required
DATABASE_URL=postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense
CMI_MERCHANT_ID=TEST_MERCHANT_001
CMI_SECRET_KEY=test_secret_key_12345

# Optional (PayPal)
PAYPAL_ENABLED=false
PAYPAL_CLIENT_ID=
PAYPAL_SECRET=

# Optional (Crypto)
BTC_WALLET=1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
ETH_WALLET=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
USDT_WALLET=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

## 🎓 Best Practices

1. **Always check trading access** before executing trades
2. **Use decorators** for consistent access control
3. **Handle payment failures** gracefully
4. **Provide clear error messages** to users
5. **Log all payment operations** for audit trail
6. **Test all payment scenarios** (success, failure, timeout)
7. **Verify challenge status** before allowing trading
8. **Implement proper error handling** for all endpoints

---

**Version**: 1.0  
**Last Updated**: January 19, 2024  
**Status**: ✅ Production Ready (Simulation Mode)
