"""
Payment API Endpoints

Stripe payment processing for challenge purchases and payouts.
"""

from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

from . import api_bp
from app.payments import payment_service
import time
import uuid


def get_db_session():
    """Get database session."""
    database_url = current_app.config.get('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
    engine = create_engine(database_url, echo=False)
    return Session(engine)


@api_bp.route('/payments/create-intent', methods=['POST'])
def create_payment_intent():
    """
    Create a Stripe PaymentIntent for challenge purchase.

    Expects:
    {
        "challenge_id": "string",
        "user_id": "string",
        "challenge_type": "starter|professional|expert|master"
    }

    Returns PaymentIntent client_secret for frontend Stripe Elements.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required_fields = ['challenge_id', 'user_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        challenge_id = data['challenge_id']
        user_id = data['user_id']
        challenge_type = data.get('challenge_type', 'starter')

        # Validate challenge type
        valid_types = ['starter', 'professional', 'expert', 'master']
        if challenge_type not in valid_types:
            return jsonify({'error': f'Invalid challenge type. Must be one of: {", ".join(valid_types)}'}), 400

        # Check if user already has an active payment for this challenge
        session = get_db_session()
        existing_payment = session.execute(text("""
            SELECT id FROM payments
            WHERE user_id = :user_id AND challenge_id = :challenge_id
            AND status IN ('pending', 'processing', 'completed')
        """), {'user_id': user_id, 'challenge_id': challenge_id}).fetchone()

        if existing_payment:
            return jsonify({'error': 'Payment already exists for this challenge'}), 409

        session.close()

        # Create PaymentIntent
        payment_data = payment_service.create_payment_intent(
            challenge_id=challenge_id,
            user_id=user_id,
            challenge_type=challenge_type
        )

        return jsonify({
            'success': True,
            'payment_intent': payment_data,
            'message': 'Payment intent created successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error creating payment intent: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payments/confirm', methods=['POST'])
def confirm_payment():
    """
    Confirm a completed payment.

    Expects:
    {
        "payment_intent_id": "pi_..."
    }

    Called by frontend after Stripe payment completion.
    """
    try:
        data = request.get_json()

        if not data or 'payment_intent_id' not in data:
            return jsonify({'error': 'payment_intent_id is required'}), 400

        payment_intent_id = data['payment_intent_id']

        # Confirm payment with Stripe
        confirmation = payment_service.confirm_payment(payment_intent_id)

        # Here you would typically:
        # 1. Update the challenge status to 'active'
        # 2. Send confirmation email
        # 3. Update user account

        return jsonify({
            'success': True,
            'payment': confirmation,
            'message': 'Payment confirmed successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error confirming payment: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payments/webhook', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhooks for payment events.

    This endpoint receives events from Stripe about payment status changes.
    """
    try:
        # In a real implementation, you'd verify the webhook signature
        # and handle different event types (payment_intent.succeeded, etc.)

        payload = request.get_json()

        if not payload:
            return jsonify({'error': 'Invalid webhook payload'}), 400

        event_type = payload.get('type')
        current_app.logger.info(f"Received Stripe webhook: {event_type}")

        # Handle different webhook events
        if event_type == 'payment_intent.succeeded':
            payment_intent = payload.get('data', {}).get('object', {})
            payment_intent_id = payment_intent.get('id')

            # Confirm the payment
            try:
                confirmation = payment_service.confirm_payment(payment_intent_id)
                current_app.logger.info(f"Payment confirmed via webhook: {payment_intent_id}")
            except Exception as e:
                current_app.logger.error(f"Error confirming payment via webhook: {e}")

        elif event_type == 'payment_intent.payment_failed':
            # Handle failed payments
            payment_intent = payload.get('data', {}).get('object', {})
            payment_intent_id = payment_intent.get('id')
            current_app.logger.warning(f"Payment failed: {payment_intent_id}")

        return jsonify({'received': True}), 200

    except Exception as e:
        current_app.logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500


@api_bp.route('/payments/pricing', methods=['GET'])
def get_pricing():
    """
    Get pricing information for all challenge types.
    """
    try:
        pricing = {}
        for challenge_type in ['starter', 'professional', 'expert', 'master']:
            pricing[challenge_type] = payment_service.calculate_challenge_fee(challenge_type)

        return jsonify({
            'pricing': pricing,
            'currency': 'USD',
            'last_updated': datetime.now(timezone.utc).isoformat()
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting pricing: {e}")
        return jsonify({'error': 'Failed to get pricing information'}), 500


@api_bp.route('/payments/history', methods=['GET'])
def get_payment_history():
    """
    Get payment history for the authenticated user.

    Returns both payments made and earnings received.
    """
    try:
        # In a real implementation, get user_id from JWT token
        # For demo purposes, use a fixed user ID
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        payments = payment_service.get_payment_history(user_id)
        earnings = payment_service.get_earnings_history(user_id)

        return jsonify({
            'payments': payments,
            'earnings': earnings,
            'user_id': user_id,
            'total_paid': sum(p['amount'] for p in payments),
            'total_earned': sum(e['amount'] for e in earnings)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting payment history: {e}")
        return jsonify({'error': 'Failed to get payment history'}), 500


@api_bp.route('/payments/payout', methods=['POST'])
def request_payout():
    """
    Request a payout for earned profits.

    This would be called when a trader wants to withdraw their earnings.
    """
    try:
        # In a real implementation, get user_id from JWT token
        # and validate that the user has available balance
        user_id = '550e8400-e29b-41d4-a716-446655440000'

        data = request.get_json()
        amount = data.get('amount', 0)

        if amount <= 0:
            return jsonify({'error': 'Invalid payout amount'}), 400

        # Check available balance (mock implementation)
        available_balance = 125.50  # Would be queried from database

        if amount > available_balance:
            return jsonify({'error': f'Insufficient balance. Available: ${available_balance}'}), 400

        # Process payout (mock implementation)
        payout_result = payment_service.process_payout(user_id, amount)

        return jsonify({
            'success': True,
            'payout': payout_result,
            'message': f'Payout of ${amount} requested successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error requesting payout: {e}")
        return jsonify({'error': 'Failed to request payout'}), 500


@api_bp.route('/payments/mock', methods=['POST'])
def mock_payment():
    """
    Simule un paiement sans intégration réelle.

    Comportement:
      - Attend 2 secondes pour simuler le traitement
      - Retourne SUCCESS
      - Renvoie un objet 'challenge' simulé avec statut 'ACTIVE' et solde initial

    Expects payload:
      { "user_id": "<uuid>", "challenge_type": "PHASE_1", "initial_balance": 100000 }

    Note: Aucune écriture en base n'est effectuée.
    """
    try:
        data = request.get_json() or {}

        user_id = data.get('user_id', str(uuid.uuid4()))
        challenge_type = data.get('challenge_type', 'PHASE_1')
        initial_balance = data.get('initial_balance', 100000.0)

        # Simulate processing time
        time.sleep(2)

        # Create simulated challenge object (no DB side effects)
        challenge = {
            'challenge_id': str(uuid.uuid4()),
            'user_id': user_id,
            'challenge_type': challenge_type,
            'initial_balance': float(initial_balance),
            'current_equity': float(initial_balance),
            'status': 'ACTIVE',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'message': 'Mock payment succeeded and challenge activated (simulated)'
        }

        return jsonify({
            'success': True,
            'payment_status': 'SUCCESS',
            'challenge': challenge
        }), 201

    except Exception as e:
        current_app.logger.error(f"Mock payment error: {e}")
        return jsonify({'error': 'Mock payment failed', 'details': str(e)}), 500