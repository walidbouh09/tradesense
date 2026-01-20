# Quick Start - Payment Simulation & Access Control

## 🚀 Get Started in 5 Minutes

### Step 1: Environment Setup (30 seconds)

```bash
# Set database URL
export DATABASE_URL="postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense"

# Optional: Enable PayPal
export PAYPAL_ENABLED=false
```

### Step 2: Start Application (10 seconds)

```bash
python app/main.py
```

### Step 3: Test Payment Flow (2 minutes)

```bash
# Run automated test
bash test_payment_flow.sh
```

## 📋 Manual Testing (5 commands)

```bash
# 1. Get pricing
curl http://localhost:5000/api/payment-simulation/pricing

# 2. Initiate payment
curl -X POST http://localhost:5000/api/payment-simulation/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "tier": "STARTER",
    "provider": "CMI"
  }'

# 3. Confirm payment (use payment_id from step 2)
curl -X POST http://localhost:5000/api/payment-simulation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "CMI_ABC123",
    "success": true
  }'

# 4. Check trading access
curl http://localhost:5000/api/access/can-trade/550e8400-e29b-41d4-a716-446655440000

# 5. Get active challenge
curl http://localhost:5000/api/access/active-challenge/550e8400-e29b-41d4-a716-446655440000
```

## 🎯 Expected Results

### Before Payment
```json
{
  "allowed": false,
  "reason": "no_active_challenge",
  "message": "No active challenge found"
}
```

### After Payment
```json
{
  "allowed": true,
  "challenge": {
    "id": "uuid",
    "status": "ACTIVE",
    "initial_balance": 10000.0
  },
  "message": "Trading access granted"
}
```

## 💡 Key Concepts

1. **Payment creates challenge** (PENDING state)
2. **Success activates challenge** (ACTIVE state)
3. **Active challenge enables trading**
4. **No real money processed**

## 📚 Next Steps

- Read `PAYMENT_SIMULATION_README.md` for complete docs
- Check `PAYMENT_INTEGRATION_EXAMPLE.py` for code examples
- Review `DELIVERY_PAYMENT_SYSTEM.md` for full details

## 🆘 Troubleshooting

**Issue**: "No active challenge"  
**Solution**: Complete payment flow first

**Issue**: "Payment not found"  
**Solution**: Use correct payment_id from initiate response

**Issue**: "Database connection error"  
**Solution**: Check DATABASE_URL environment variable

---

**Ready to integrate!** 🎉
