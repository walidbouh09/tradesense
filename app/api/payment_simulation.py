"""
Payment Simulation API Endpoints

Simulated payment processing for development and testing.
NO REAL MONEY - Deterministic behavior for testing.
"""

import uuid
from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from datetime import datetime, timezone

from . import api_bp
from app.payment_simulation import (
    payment_simulator,
    PaymentProvider,
    PricingTier,
    CryptoType,
    PaymentStatus,
    PRICING_CONFIG
)
from app.access_control import access_control, require_permission, Permission


def get_db_session():
    """Get database session."""
    database_url = current_app.config.get(
        'DATABASE_URL',
        'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense'
    )
    engine = create_engine(database_url, echo=False)
    return Session(engine)


@api_bp.route('/payment-simulation/pricing', methods=['GET'])
def get_pricing():
    """
    Get pricing information for all tiers.
    
    Returns:
        Pricing details for Starter, Pro, and Elite tiers
    """
    try:
        pricing = payment_simulator.get_all_pricing()
        
        return jsonify({
            'success': True,
            'pricing': pricing,
            'currency': 'MAD',
            'note': 'Simulated pricing - no real money will be charged',
            'providers': [
                {
                    'name': 'CMI',
                    'description': 'Moroccan payment gateway',
                    'supported': True
                },
                {
                    'name': 'Crypto',
                    'description': 'Bitcoin, Ethereum, USDT',
                    'supported': True
                },
                {
                    'name': 'PayPal',
                    'description': 'PayPal payments',
                    'supported': payment_simulator.paypal_enabled
                }
            ]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting pricing: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payment-simulation/initiate', methods=['POST'])
def initiate_payment():
    """
    Initiate a simulated payment.
    
    Request body:
    {
        "user_id": "uuid",
        "tier": "STARTER|PRO|ELITE",
        "provider": "CMI|CRYPTO|PAYPAL",
        "crypto_type": "BTC|ETH|USDT" (if provider is CRYPTO),
        "return_url": "https://..." (optional)
    }
    
    Returns:
        Payment initiation data with provider-specific details
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['user_id', 'tier', 'provider']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        user_id = data['user_id']
        tier = data['tier'].upper()
        provider = data['provider'].upper()
        
        # Validate tier
        try:
            tier_enum = PricingTier[tier]
        except KeyError:
            return jsonify({
                'error': f'Invalid tier. Must be one of: {", ".join([t.value for t in PricingTier])}'
            }), 400
        
        # Validate provider
        try:
            provider_enum = PaymentProvider[provider]
        except KeyError:
            return jsonify({
                'error': f'Invalid provider. Must be one of: {", ".join([p.value for p in PaymentProvider])}'
            }), 400
        
        # Check if user already has an active challenge
        active_challenge = access_control.get_active_challenge(user_id)
        if active_challenge:
            return jsonify({
                'error': 'You already have an active challenge',
                'active_challenge_id': active_challenge['id'],
                'message': 'Complete or end your current challenge before purchasing a new one'
            }), 409
        
        # Create challenge first (in PENDING state)
        session = get_db_session()
        challenge_id = str(uuid.uuid4())
        config = PRICING_CONFIG[tier_enum]
        now = datetime.now(timezone.utc)
        
        session.execute(text("""
            INSERT INTO challenges (
                id, user_id, challenge_type, initial_balance,
                max_daily_drawdown_percent, max_total_drawdown_percent,
                profit_target_percent, current_equity, max_equity_ever,
                daily_start_equity, daily_max_equity, daily_min_equity,
                status, created_at, updated_at
            ) VALUES (
                :id, :user_id, :challenge_type, :initial_balance,
                :max_daily_drawdown, :max_total_drawdown,
                :profit_target, :current_equity, :max_equity_ever,
                :daily_start_equity, :daily_max_equity, :daily_min_equity,
                'PENDING', :created_at, :updated_at
            )
        """), {
            'id': challenge_id,
            'user_id': user_id,
            'challenge_type': tier,
            'initial_balance': config['initial_balance'],
            'max_daily_drawdown': config['max_daily_drawdown'],
            'max_total_drawdown': config['max_total_drawdown'],
            'profit_target': config['profit_target'],
            'current_equity': config['initial_balance'],
            'max_equity_ever': config['initial_balance'],
            'daily_start_equity': config['initial_balance'],
            'daily_max_equity': config['initial_balance'],
            'daily_min_equity': config['initial_balance'],
            'created_at': now,
            'updated_at': now
        })
        
        session.commit()
        
        # Initiate payment based on provider
        return_url = data.get('return_url', 'http://localhost:3000/payment/success')
        cancel_url = data.get('cancel_url', 'http://localhost:3000/payment/cancel')
        
        if provider_enum == PaymentProvider.CMI:
            payment_data = payment_simulator.initiate_cmi_payment(
                user_id=user_id,
                tier=tier_enum,
                return_url=return_url
            )
        
        elif provider_enum == PaymentProvider.CRYPTO:
            crypto_type = data.get('crypto_type', 'BTC').upper()
            try:
                crypto_enum = CryptoType[crypto_type]
            except KeyError:
                session.rollback()
                session.close()
                return jsonify({
                    'error': f'Invalid crypto type. Must be one of: {", ".join([c.value for c in CryptoType])}'
                }), 400
            
            payment_data = payment_simulator.initiate_crypto_payment(
                user_id=user_id,
                tier=tier_enum,
                crypto_type=crypto_enum
            )
        
        elif provider_enum == PaymentProvider.PAYPAL:
            if not payment_simulator.paypal_enabled:
                session.rollback()
                session.close()
                return jsonify({
                    'error': 'PayPal is not enabled',
                    'message': 'Set PAYPAL_ENABLED=true in environment to enable PayPal'
                }), 400
            
            payment_data = payment_simulator.initiate_paypal_payment(
                user_id=user_id,
                tier=tier_enum,
                return_url=return_url,
                cancel_url=cancel_url
            )
        
        # Store payment in database
        session.execute(text("""
            INSERT INTO payments (
                id, user_id, challenge_id, provider, provider_payment_id,
                amount, currency, status, initiated_at, created_at, updated_at
            ) VALUES (
                :id, :user_id, :challenge_id, :provider, :provider_payment_id,
                :amount, :currency, :status, :initiated_at, :created_at, :updated_at
            )
        """), {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'challenge_id': challenge_id,
            'provider': provider,
            'provider_payment_id': payment_data['payment_id'],
            'amount': payment_data.get('amount', payment_data.get('amount_mad')),
            'currency': payment_data.get('currency', 'MAD'),
            'status': PaymentStatus.PENDING.value,
            'initiated_at': now,
            'created_at': now,
            'updated_at': now
        })
        
        session.commit()
        session.close()
        
        return jsonify({
            'success': True,
            'challenge_id': challenge_id,
            'payment': payment_data,
            'message': 'Payment initiated successfully'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error initiating payment: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payment-simulation/confirm', methods=['POST'])
def confirm_payment():
    """
    Confirm a simulated payment (simulate successful payment).
    
    Request body:
    {
        "payment_id": "CMI_xxx or CRYPTO_xxx or PAYPAL_xxx",
        "success": true (optional, default: true)
    }
    
    This simulates the payment callback/confirmation.
    In production, this would be called by the payment provider.
    """
    try:
        data = request.get_json()
        
        if not data or 'payment_id' not in data:
            return jsonify({'error': 'payment_id is required'}), 400
        
        payment_id = data['payment_id']
        success = data.get('success', True)
        
        session = get_db_session()
        
        # Get payment from database
        payment = session.execute(text("""
            SELECT p.*, c.id as challenge_id, c.user_id
            FROM payments p
            JOIN challenges c ON p.challenge_id = c.id
            WHERE p.provider_payment_id = :payment_id
        """), {'payment_id': payment_id}).fetchone()
        
        if not payment:
            session.close()
            return jsonify({'error': 'Payment not found'}), 404
        
        # Simulate payment confirmation based on provider
        provider = payment.provider
        
        if provider == PaymentProvider.CMI.value:
            result = payment_simulator.simulate_cmi_callback(
                payment_id=payment_id,
                transaction_ref=data.get('transaction_ref', 'TEST_REF'),
                success=success
            )
        
        elif provider == PaymentProvider.CRYPTO.value:
            result = payment_simulator.simulate_crypto_confirmation(
                payment_id=payment_id,
                transaction_hash=data.get('transaction_hash'),
                confirmations=data.get('confirmations', 6)
            )
        
        elif provider == PaymentProvider.PAYPAL.value:
            result = payment_simulator.simulate_paypal_capture(
                payment_id=payment_id,
                paypal_order_id=data.get('paypal_order_id', 'ORDER_TEST'),
                success=success
            )
        
        # Update payment status
        new_status = PaymentStatus.SUCCESS.value if success else PaymentStatus.FAILED.value
        now = datetime.now(timezone.utc)
        
        session.execute(text("""
            UPDATE payments
            SET status = :status,
                processed_at = :processed_at,
                updated_at = :updated_at,
                provider_response = :provider_response
            WHERE provider_payment_id = :payment_id
        """), {
            'status': new_status,
            'processed_at': now,
            'updated_at': now,
            'provider_response': str(result),
            'payment_id': payment_id
        })
        
        # If payment successful, activate challenge
        if success:
            session.execute(text("""
                UPDATE challenges
                SET status = 'ACTIVE',
                    started_at = :started_at,
                    updated_at = :updated_at
                WHERE id = :challenge_id
            """), {
                'started_at': now,
                'updated_at': now,
                'challenge_id': payment.challenge_id
            })
            
            # Insert challenge event
            session.execute(text("""
                INSERT INTO challenge_events (
                    id, challenge_id, event_type, sequence_number,
                    event_data, description, occurred_at, recorded_at
                ) VALUES (
                    :id, :challenge_id, :event_type, :sequence_number,
                    :event_data, :description, :occurred_at, :recorded_at
                )
            """), {
                'id': str(uuid.uuid4()),
                'challenge_id': payment.challenge_id,
                'event_type': 'CHALLENGE_STARTED',
                'sequence_number': 1,
                'event_data': '{"payment_id": "' + payment_id + '", "provider": "' + provider + '"}',
                'description': f'Challenge started after successful {provider} payment',
                'occurred_at': now,
                'recorded_at': now
            })
        
        session.commit()
        session.close()
        
        return jsonify({
            'success': True,
            'payment_result': result,
            'challenge_id': str(payment.challenge_id),
            'challenge_status': 'ACTIVE' if success else 'PENDING',
            'message': 'Payment confirmed successfully' if success else 'Payment failed'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error confirming payment: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payment-simulation/status/<payment_id>', methods=['GET'])
def get_payment_status(payment_id: str):
    """
    Get payment status.
    
    Args:
        payment_id: Payment identifier
        
    Returns:
        Payment status and details
    """
    try:
        session = get_db_session()
        
        payment = session.execute(text("""
            SELECT p.*, c.status as challenge_status
            FROM payments p
            LEFT JOIN challenges c ON p.challenge_id = c.id
            WHERE p.provider_payment_id = :payment_id
        """), {'payment_id': payment_id}).fetchone()
        
        session.close()
        
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        return jsonify({
            'payment_id': payment_id,
            'status': payment.status,
            'provider': payment.provider,
            'amount': float(payment.amount),
            'currency': payment.currency,
            'challenge_id': str(payment.challenge_id) if payment.challenge_id else None,
            'challenge_status': payment.challenge_status,
            'initiated_at': payment.initiated_at.isoformat() if payment.initiated_at else None,
            'processed_at': payment.processed_at.isoformat() if payment.processed_at else None
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting payment status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/payment-simulation/user-payments/<user_id>', methods=['GET'])
def get_user_payments(user_id: str):
    """
    Get all payments for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of user's payments
    """
    try:
        session = get_db_session()
        
        payments = session.execute(text("""
            SELECT p.*, c.challenge_type, c.status as challenge_status
            FROM payments p
            LEFT JOIN challenges c ON p.challenge_id = c.id
            WHERE p.user_id = :user_id
            ORDER BY p.created_at DESC
        """), {'user_id': user_id}).fetchall()
        
        session.close()
        
        return jsonify({
            'user_id': user_id,
            'payments': [
                {
                    'payment_id': p.provider_payment_id,
                    'status': p.status,
                    'provider': p.provider,
                    'amount': float(p.amount),
                    'currency': p.currency,
                    'challenge_id': str(p.challenge_id) if p.challenge_id else None,
                    'challenge_type': p.challenge_type,
                    'challenge_status': p.challenge_status,
                    'initiated_at': p.initiated_at.isoformat() if p.initiated_at else None,
                    'processed_at': p.processed_at.isoformat() if p.processed_at else None
                }
                for p in payments
            ],
            'total_payments': len(payments)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting user payments: {e}")
        return jsonify({'error': str(e)}), 500
