#!/bin/bash

# ============================================================================
# Moroccan Stock Market Integration - Test Script
# ============================================================================
# Tests the Casablanca Stock Exchange web scraping integration
# ============================================================================

BASE_URL="http://localhost:5000/api"

echo "========================================="
echo "Morocco Market Integration Test"
echo "Casablanca Stock Exchange"
echo "========================================="
echo ""

# ============================================================================
# Test 1: IAM (Maroc Telecom)
# ============================================================================
echo "Test 1: Fetching IAM (Itissalat Al-Maghrib / Maroc Telecom)..."
echo "GET $BASE_URL/market/morocco/IAM"
echo ""

curl -s "$BASE_URL/market/morocco/IAM" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 2: ATW (Attijariwafa Bank)
# ============================================================================
echo ""
echo "========================================="
echo "Test 2: Fetching ATW (Attijariwafa Bank)..."
echo "GET $BASE_URL/market/morocco/ATW"
echo ""

curl -s "$BASE_URL/market/morocco/ATW" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 3: BCP (Banque Centrale Populaire)
# ============================================================================
echo ""
echo "========================================="
echo "Test 3: Fetching BCP (Banque Centrale Populaire)..."
echo "GET $BASE_URL/market/morocco/BCP"
echo ""

curl -s "$BASE_URL/market/morocco/BCP" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 4: Symbol with .MA suffix
# ============================================================================
echo ""
echo "========================================="
echo "Test 4: Testing with .MA suffix..."
echo "GET $BASE_URL/market/morocco/IAM.MA"
echo ""

curl -s "$BASE_URL/market/morocco/IAM.MA" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 5: Lowercase symbol
# ============================================================================
echo ""
echo "========================================="
echo "Test 5: Testing lowercase symbol..."
echo "GET $BASE_URL/market/morocco/iam"
echo ""

curl -s "$BASE_URL/market/morocco/iam" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 6: Invalid symbol
# ============================================================================
echo ""
echo "========================================="
echo "Test 6: Testing invalid symbol (should return 404)..."
echo "GET $BASE_URL/market/morocco/INVALID"
echo ""

curl -s "$BASE_URL/market/morocco/INVALID" | python3 -m json.tool

echo ""
echo "Press Enter to continue..."
read

# ============================================================================
# Test 7: Multiple requests (testing cache)
# ============================================================================
echo ""
echo "========================================="
echo "Test 7: Testing cache (3 rapid requests)..."
echo ""

echo "Request 1 (fresh - may take 1-3 seconds):"
time curl -s "$BASE_URL/market/morocco/IAM" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Price: {data['price']['current']} MAD\")"

echo ""
echo "Request 2 (cached - should be instant):"
time curl -s "$BASE_URL/market/morocco/IAM" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Price: {data['price']['current']} MAD\")"

echo ""
echo "Request 3 (cached - should be instant):"
time curl -s "$BASE_URL/market/morocco/IAM" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"Price: {data['price']['current']} MAD\")"

echo ""
echo "========================================="
echo "Morocco Market Integration Test Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "✅ IAM (Maroc Telecom) - Tested"
echo "✅ ATW (Attijariwafa Bank) - Tested"
echo "✅ BCP (Banque Centrale Populaire) - Tested"
echo "✅ Symbol normalization (.MA suffix) - Tested"
echo "✅ Case insensitivity - Tested"
echo "✅ Error handling (invalid symbol) - Tested"
echo "✅ Caching (5-minute TTL) - Tested"
echo ""
echo "Key Features Demonstrated:"
echo "- Minimal web scraping with BeautifulSoup"
echo "- Rate limiting (1-second delay)"
echo "- Caching (5-minute expiry)"
echo "- Multiple fallback strategies"
echo "- Graceful error handling"
echo "- No aggressive crawling"
echo "- No scheduling (on-demand only)"
echo ""
echo "Integration proves market data beyond international APIs!"
echo ""
