"""
Payment Processing Module

Handles payment processing with Stripe integration for challenge purchases.
"""

import os
import stripe
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging

from app.market_data import market_data

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Payment service for processing challenge purchases and payouts.

    Integrates with Stripe for secure payment processing.
    """

    def __init__(self):
        # Stripe configuration
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_...')

        # Pricing (in cents for Stripe)
        self.challenge_prices = {
            'starter': 9900,      # $99.00
            'professional': 19900, # $199.00
            'expert': 39900,      # $399.00
            'master': 99900       # $999.00
        }

        # Profit sharing (when traders succeed)
        self.profit_sharing_rate = Decimal('0.10')  # 10% of profits

    def create_payment_intent(self, challenge_id: str, user_id: str, challenge_type: str = 'starter') -> Dict:
        """
        Create a Stripe PaymentIntent for challenge purchase.

        Args:
            challenge_id: Unique challenge identifier
            user_id: User making the purchase
            challenge_type: Type of challenge (starter/professional/expert/master)

        Returns:
            PaymentIntent data for frontend
        """
        try:
            amount = self.challenge_prices.get(challenge_type, self.challenge_prices['starter'])

            # Create PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                metadata={
                    'challenge_id': challenge_id,
                    'user_id': user_id,
                    'challenge_type': challenge_type,
                    'service': 'tradesense_challenge'
                },
                description=f'TradeSense AI {challenge_type.title()} Challenge',
                receipt_email=None,  # Will be set from user data
                automatic_payment_methods={
                    'enabled': True,
                }
            )

            logger.info(f"PaymentIntent created for challenge {challenge_id}: ${amount/100}")

            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': amount,
                'currency': 'usd',
                'challenge_type': challenge_type
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating PaymentIntent: {e}")
            raise Exception(f"Payment processing error: {e.user_message if hasattr(e, 'user_message') else str(e)}")
        except Exception as e:
            logger.error(f"Error creating PaymentIntent: {e}")
            raise Exception("Failed to create payment intent")

    def confirm_payment(self, payment_intent_id: str) -> Dict:
        """
        Confirm and process a successful payment.

        Args:
            payment_intent_id: Stripe PaymentIntent ID

        Returns:
            Payment confirmation details
        """
        try:
            # Retrieve the PaymentIntent
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status != 'succeeded':
                raise Exception(f"Payment not completed. Status: {intent.status}")

            # Extract metadata
            metadata = intent.metadata
            challenge_id = metadata.get('challenge_id')
            user_id = metadata.get('user_id')
            challenge_type = metadata.get('challenge_type', 'starter')

            # Record payment in database (would be implemented)
            payment_record = {
                'payment_id': intent.id,
                'challenge_id': challenge_id,
                'user_id': user_id,
                'amount': intent.amount,
                'currency': intent.currency,
                'status': 'completed',
                'challenge_type': challenge_type,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Payment confirmed: {payment_intent_id} for challenge {challenge_id}")

            return {
                'success': True,
                'payment': payment_record,
                'challenge_id': challenge_id,
                'message': 'Payment processed successfully'
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {e}")
            raise Exception(f"Payment confirmation error: {e.user_message if hasattr(e, 'user_message') else str(e)}")
        except Exception as e:
            logger.error(f"Error confirming payment: {e}")
            raise Exception("Failed to confirm payment")

    def process_payout(self, user_id: str, amount: float, currency: str = 'usd') -> Dict:
        """
        Process payout to successful trader.

        This would be called when a trader completes a challenge successfully.
        """
        try:
            # In a real implementation, you'd need the trader's Stripe account
            # For now, this is a placeholder

            logger.info(f"Payout processed for user {user_id}: ${amount} {currency}")

            return {
                'success': True,
                'payout_id': f'po_{user_id}_{int(datetime.now(timezone.utc).timestamp())}',
                'amount': amount,
                'currency': currency,
                'status': 'completed'
            }

        except Exception as e:
            logger.error(f"Error processing payout for user {user_id}: {e}")
            raise Exception("Failed to process payout")

    def calculate_challenge_fee(self, challenge_type: str) -> Dict:
        """
        Calculate fees and pricing for different challenge types.

        Returns pricing breakdown including any platform fees.
        """
        base_price = self.challenge_prices.get(challenge_type, self.challenge_prices['starter'])
        platform_fee = int(base_price * 0.05)  # 5% platform fee
        trader_amount = base_price - platform_fee

        return {
            'challenge_type': challenge_type,
            'total_price': base_price / 100,  # Convert cents to dollars
            'platform_fee': platform_fee / 100,
            'trader_amount': trader_amount / 100,
            'currency': 'USD'
        }

    def get_payment_history(self, user_id: str, limit: int = 10) -> list:
        """
        Get payment history for a user.

        Returns list of payments made by the user.
        """
        # In a real implementation, this would query the database
        # For now, return mock data
        return [
            {
                'id': f'pay_{i}',
                'amount': 99.00,
                'currency': 'USD',
                'status': 'completed',
                'challenge_type': 'starter',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
            }
            for i in range(min(limit, 5))
        ]

    def get_earnings_history(self, user_id: str, limit: int = 10) -> list:
        """
        Get earnings/payout history for a trader.

        Returns list of payouts earned by the trader.
        """
        # In a real implementation, this would query the database
        # For now, return mock data
        return [
            {
                'id': f'earn_{i}',
                'amount': 45.50,
                'currency': 'USD',
                'type': 'profit_share',
                'status': 'completed',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=i*7)).isoformat()
            }
            for i in range(min(limit, 3))
        ]


# Global payment service instance
payment_service = PaymentService()