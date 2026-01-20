"""
Payment Simulation & Access Control - Integration Examples

This file demonstrates how to integrate payment simulation and access control
into your trading endpoints.
"""

from flask import jsonify, request
from app.api import api_bp
from app.access_control import require_active_challenge, access_control, Permission
from app.payment_simulation import payment_simulator, PricingTier


# ============================================================================
# EXAMPLE 1: Protected Trading Endpoint
# ============================================================================

@api_bp.route('/trades/execute-protected', methods=['POST'])
@require_active_challenge  # This decorator enforces access control
def execute_trade_protected():
    """
    Execute a trade (PROTECTED - requires active challenge).
    
    The @require_active_challenge decorator automatically:
    1. Checks if user has an active challenge
    2. Verifies payment is completed
    3. Ensures challenge is started
    4. Returns 403 if any check fails
    5. Adds challenge info to request.active_challenge
    """
    # If we reach here, user has an active challenge
    challenge = request.active_challenge
    
    data = request.get_json()
    
    # Execute trade logic
    trade_result = {
        'trade_id': 'TRADE_001',
        'challenge_id': challenge['id'],
        'symbol': data['symbol'],
        'side': data['side'],
        'quantity': data['quantity'],
        'price': data['price'],
        'status': 'EXECUTED',
        'message': 'Trade executed successfully'
    }
    
    return jsonify(trade_result), 200


# ============================================================================
# EXAMPLE 2: Manual Access Check
# ============================================================================

@api_bp.route('/trades/execute-manual', methods=['POST'])
def execute_trade_manual():
    """
    Execute a trade with manual access check.
    
    Use this approach when you need more control over the access check logic.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Manual access check
    can_trade, denial_reason, message = access_control.can_trade(user_id)
    
    if not can_trade:
        return jsonify({
            'error': message,
            'reason': denial_reason.value,
            'action_required': access_control._get_action_required(denial_reason)
        }), 403
    
    # Get active challenge
    challenge = access_control.get_active_challenge(user_id)
    
    # Execute trade logic
    trade_result = {
        'trade_id': 'TRADE_002',
        'challenge_id': challenge['id'],
        'symbol': data['symbol'],
        'status': 'EXECUTED'
    }
    
    return jsonify(trade_result), 200


# ============================================================================
# EXAMPLE 3: Complete Payment Flow
# ============================================================================

@api_bp.route('/example/complete-payment-flow', methods=['POST'])
def complete_payment_flow_example():
    """
    Example of complete payment flow from initiation to trading.
    
    This demonstrates the full lifecycle:
    1. User selects tier
    2. Payment initiated
    3. Payment confirmed
    4. Challenge activated
    5. Trading enabled
    """
    data = request.get_json()
    user_id = data.get('user_id')
    tier = data.get('tier', 'STARTER')
    
    # Step 1: Check if user already has active challenge
    active_challenge = access_control.get_active_challenge(user_id)
    if active_challenge:
        return jsonify({
            'error': 'You already have an active challenge',
            'active_challenge': active_challenge
        }), 409
    
    # Step 2: Get pricing for selected tier
    pricing = payment_simulator.get_pricing(PricingTier[tier])
    
    # Step 3: Initiate payment (example with CMI)
    payment_data = payment_simulator.initiate_cmi_payment(
        user_id=user_id,
        tier=PricingTier[tier],
        return_url='http://localhost:3000/payment/success'
    )
    
    # In a real application:
    # - Save payment to database
    # - Create challenge in PENDING state
    # - Redirect user to payment gateway
    # - Wait for payment callback
    # - Activate challenge on success
    
    return jsonify({
        'step': 'payment_initiated',
        'pricing': pricing,
        'payment': payment_data,
        'next_steps': [
            'User completes payment at payment gateway',
            'Payment gateway calls webhook/callback',
            'System confirms payment',
            'Challenge activated',
            'User can start trading'
        ]
    }), 200


# ============================================================================
# EXAMPLE 4: Check Trading Access Before Operation
# ============================================================================

@api_bp.route('/example/check-access', methods=['POST'])
def check_trading_access_example():
    """
    Example of checking trading access before performing an operation.
    
    Use this pattern when you want to check access without executing a trade.
    """
    data = request.get_json()
    user_id = data.get('user_id')
    
    # Get detailed access status
    access_status = access_control.enforce_trading_access(user_id)
    
    if not access_status['allowed']:
        return jsonify({
            'can_trade': False,
            'reason': access_status['reason'],
            'message': access_status['message'],
            'action_required': access_status['action_required']
        }), 200
    
    # Access granted
    return jsonify({
        'can_trade': True,
        'challenge': access_status['challenge'],
        'message': 'User can trade',
        'available_balance': access_status['challenge']['current_equity']
    }), 200


# ============================================================================
# EXAMPLE 5: Permission-Based Access Control
# ============================================================================

from app.access_control import require_permission

@api_bp.route('/example/admin-only', methods=['GET'])
@require_permission(Permission.ADMIN_ACCESS)
def admin_only_endpoint():
    """
    Example of endpoint that requires admin permission.
    
    Only users with ADMIN or SUPERADMIN role can access this.
    """
    return jsonify({
        'message': 'Admin access granted',
        'data': 'Sensitive admin data'
    }), 200


# ============================================================================
# EXAMPLE 6: Simulating Payment Success/Failure
# ============================================================================

@api_bp.route('/example/simulate-payment', methods=['POST'])
def simulate_payment_example():
    """
    Example of simulating payment success or failure for testing.
    
    This is useful for testing different payment scenarios.
    """
    data = request.get_json()
    payment_id = data.get('payment_id')
    simulate_success = data.get('success', True)
    
    # Simulate payment confirmation
    if simulate_success:
        result = payment_simulator.simulate_cmi_callback(
            payment_id=payment_id,
            transaction_ref='TEST_REF_123',
            success=True
        )
        
        # In real application, this would:
        # 1. Update payment status to SUCCESS
        # 2. Update challenge status to ACTIVE
        # 3. Set challenge started_at timestamp
        # 4. Send confirmation email
        
        return jsonify({
            'simulation': 'success',
            'result': result,
            'next_step': 'Challenge is now ACTIVE - user can trade'
        }), 200
    else:
        result = payment_simulator.simulate_cmi_callback(
            payment_id=payment_id,
            transaction_ref='TEST_REF_123',
            success=False
        )
        
        return jsonify({
            'simulation': 'failure',
            'result': result,
            'next_step': 'Challenge remains PENDING - user cannot trade'
        }), 200


# ============================================================================
# EXAMPLE 7: Getting User's Payment History
# ============================================================================

@api_bp.route('/example/payment-history/<user_id>', methods=['GET'])
def get_payment_history_example(user_id: str):
    """
    Example of getting user's payment history.
    
    Shows all payments and their associated challenges.
    """
    # In real application, query database for user's payments
    # This is a simplified example
    
    payments = [
        {
            'payment_id': 'CMI_ABC123',
            'status': 'SUCCESS',
            'amount': 200.0,
            'currency': 'MAD',
            'tier': 'STARTER',
            'challenge_id': 'uuid-1',
            'challenge_status': 'ACTIVE',
            'created_at': '2024-01-19T10:00:00Z'
        },
        {
            'payment_id': 'CRYPTO_DEF456',
            'status': 'SUCCESS',
            'amount': 500.0,
            'currency': 'MAD',
            'tier': 'PRO',
            'challenge_id': 'uuid-2',
            'challenge_status': 'FUNDED',
            'created_at': '2024-01-15T14:30:00Z'
        }
    ]
    
    return jsonify({
        'user_id': user_id,
        'payments': payments,
        'total_spent': sum(p['amount'] for p in payments),
        'successful_payments': len([p for p in payments if p['status'] == 'SUCCESS'])
    }), 200


# ============================================================================
# EXAMPLE 8: Crypto Payment Flow
# ============================================================================

@api_bp.route('/example/crypto-payment', methods=['POST'])
def crypto_payment_example():
    """
    Example of cryptocurrency payment flow.
    
    Shows how to handle Bitcoin/Ethereum/USDT payments.
    """
    from app.payment_simulation import CryptoType
    
    data = request.get_json()
    user_id = data.get('user_id')
    tier = data.get('tier', 'PRO')
    crypto_type = data.get('crypto_type', 'BTC')
    
    # Initiate crypto payment
    payment_data = payment_simulator.initiate_crypto_payment(
        user_id=user_id,
        tier=PricingTier[tier],
        crypto_type=CryptoType[crypto_type]
    )
    
    return jsonify({
        'payment_initiated': True,
        'payment_details': payment_data,
        'instructions': [
            f"1. Send exactly {payment_data['crypto_amount']} {crypto_type} to the wallet address",
            "2. Wait for blockchain confirmations (typically 6 confirmations)",
            "3. System will automatically detect payment and activate challenge",
            "4. You will receive email confirmation when challenge is active"
        ],
        'qr_code': payment_data['qr_code_url'],
        'wallet_address': payment_data['wallet_address']
    }), 200


# ============================================================================
# USAGE NOTES
# ============================================================================

"""
IMPORTANT NOTES FOR DEVELOPERS:

1. ALWAYS use @require_active_challenge decorator for trading endpoints
2. Payment simulation is for TESTING ONLY - no real money is processed
3. All payment amounts are in Moroccan Dirham (MAD)
4. Users can only have ONE active challenge at a time
5. Challenge must be ACTIVE and PAID before trading is allowed
6. Access control checks are performed on EVERY trading operation

TESTING WORKFLOW:

1. Get pricing:
   GET /api/payment-simulation/pricing

2. Initiate payment:
   POST /api/payment-simulation/initiate
   {
     "user_id": "uuid",
     "tier": "STARTER",
     "provider": "CMI"
   }

3. Simulate payment success:
   POST /api/payment-simulation/confirm
   {
     "payment_id": "CMI_xxx",
     "success": true
   }

4. Check trading access:
   GET /api/access/can-trade/{user_id}

5. Execute trade (now allowed):
   POST /api/trades/execute-protected
   {
     "user_id": "uuid",
     "symbol": "EURUSD",
     "side": "BUY",
     "quantity": 1000,
     "price": 1.0850
   }

ENVIRONMENT SETUP:

# Required
DATABASE_URL=postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense

# Optional (PayPal)
PAYPAL_ENABLED=true
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_SECRET=your_secret

# Optional (Crypto wallets)
BTC_WALLET=your_btc_wallet
ETH_WALLET=your_eth_wallet
USDT_WALLET=your_usdt_wallet
"""
