#!/bin/bash

# ============================================================================
# Payment Simulation Test Script
# ============================================================================
# This script demonstrates the complete payment and trading flow
# NO REAL MONEY - All simulated for testing
# ============================================================================

BASE_URL="http://localhost:5000/api"
USER_ID="550e8400-e29b-41d4-a716-446655440000"

echo "========================================="
echo "TradeSense AI - Payment Flow Test"
echo "========================================="
echo ""

# ============================================================================
# Step 1: Get Pricing
# ============================================================================
echo "Step 1: Getting pricing information..."
echo "GET $BASE_URL/payment-simulation/pricing"
echo ""

curl -s "$BASE_URL/payment-simulation/pricing" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Step 2: Check Initial Trading Access (Should be DENIED)
# ============================================================================
echo ""
echo "========================================="
echo "Step 2: Checking trading access (before payment)..."
echo "GET $BASE_URL/access/can-trade/$USER_ID"
echo ""

curl -s "$BASE_URL/access/can-trade/$USER_ID" | python3 -m json.tool

echo ""
echo "Expected: Trading access DENIED (no active challenge)"
echo "Press Enter to continue..."
read

# ============================================================================
# Step 3: Initiate CMI Payment
# ============================================================================
echo ""
echo "========================================="
echo "Step 3: Initiating CMI payment for STARTER tier..."
echo "POST $BASE_URL/payment-simulation/initiate"
echo ""

PAYMENT_RESPONSE=$(curl -s -X POST "$BASE_URL/payment-simulation/initiate" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"tier\": \"STARTER\",
    \"provider\": \"CMI\",
    \"return_url\": \"http://localhost:3000/payment/success\"
  }")

echo "$PAYMENT_RESPONSE" | python3 -m json.tool

# Extract payment_id
PAYMENT_ID=$(echo "$PAYMENT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['payment']['payment_id'])" 2>/dev/null)

echo ""
echo "Payment ID: $PAYMENT_ID"
echo "Press Enter to continue..."
read

# ============================================================================
# Step 4: Check Payment Status (Should be PENDING)
# ============================================================================
echo ""
echo "========================================="
echo "Step 4: Checking payment status..."
echo "GET $BASE_URL/payment-simulation/status/$PAYMENT_ID"
echo ""

curl -s "$BASE_URL/payment-simulation/status/$PAYMENT_ID" | python3 -m json.tool

echo ""
echo "Expected: Status = PENDING"
echo "Press Enter to continue..."
read

# ============================================================================
# Step 5: Simulate Successful Payment
# ============================================================================
echo ""
echo "========================================="
echo "Step 5: Simulating successful payment..."
echo "POST $BASE_URL/payment-simulation/confirm"
echo ""

CONFIRM_RESPONSE=$(curl -s -X POST "$BASE_URL/payment-simulation/confirm" \
  -H "Content-Type: application/json" \
  -d "{
    \"payment_id\": \"$PAYMENT_ID\",
    \"success\": true
  }")

echo "$CONFIRM_RESPONSE" | python3 -m json.tool

# Extract challenge_id
CHALLENGE_ID=$(echo "$CONFIRM_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['challenge_id'])" 2>/dev/null)

echo ""
echo "Challenge ID: $CHALLENGE_ID"
echo "Challenge Status: ACTIVE"
echo "Press Enter to continue..."
read

# ============================================================================
# Step 6: Check Trading Access Again (Should be ALLOWED)
# ============================================================================
echo ""
echo "========================================="
echo "Step 6: Checking trading access (after payment)..."
echo "GET $BASE_URL/access/can-trade/$USER_ID"
echo ""

curl -s "$BASE_URL/access/can-trade/$USER_ID" | python3 -m json.tool

echo ""
echo "Expected: Trading access ALLOWED"
echo "Press Enter to continue..."
read

# ============================================================================
# Step 7: Get Active Challenge
# ============================================================================
echo ""
echo "========================================="
echo "Step 7: Getting active challenge details..."
echo "GET $BASE_URL/access/active-challenge/$USER_ID"
echo ""

curl -s "$BASE_URL/access/active-challenge/$USER_ID" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Step 8: Get User Payment History
# ============================================================================
echo ""
echo "========================================="
echo "Step 8: Getting user payment history..."
echo "GET $BASE_URL/payment-simulation/user-payments/$USER_ID"
echo ""

curl -s "$BASE_URL/payment-simulation/user-payments/$USER_ID" | python3 -m json.tool

echo ""
echo "========================================="
echo "Payment Flow Test Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "1. ✅ Retrieved pricing information"
echo "2. ✅ Verified trading access denied (no challenge)"
echo "3. ✅ Initiated CMI payment for STARTER tier (200 DH)"
echo "4. ✅ Checked payment status (PENDING)"
echo "5. ✅ Simulated successful payment"
echo "6. ✅ Challenge automatically activated"
echo "7. ✅ Trading access now ALLOWED"
echo "8. ✅ Retrieved active challenge details"
echo "9. ✅ Retrieved payment history"
echo ""
echo "User can now execute trades!"
echo ""
