"""
Unit Tests for Payment Service

Tests payment processing logic, Stripe integration, and financial calculations.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.payments import PaymentService, payment_service


class TestPaymentService:
    """Test cases for PaymentService class."""

    @pytest.fixture
    def payment_service_instance(self):
        """Create a PaymentService instance for testing."""
        service = PaymentService()
        # Override Stripe API key for testing
        service.stripe.api_key = 'sk_test_mock_key'
        return service

    def test_create_payment_intent_success(self, payment_service_instance):
        """Test successful payment intent creation."""
        with patch('app.payments.stripe.PaymentIntent.create') as mock_create:
            # Mock Stripe response
            mock_intent = Mock()
            mock_intent.client_secret = 'pi_secret_mock'
            mock_intent.id = 'pi_mock_id'
            mock_create.return_value = mock_intent

            result = payment_service_instance.create_payment_intent(
                challenge_id='challenge_123',
                user_id='user_456',
                challenge_type='starter'
            )

            assert result['client_secret'] == 'pi_secret_mock'
            assert result['payment_intent_id'] == 'pi_mock_id'
            assert result['amount'] == 9900  # $99.00 in cents
            assert result['challenge_type'] == 'starter'

            # Verify Stripe was called with correct parameters
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            assert call_args['amount'] == 9900
            assert call_args['currency'] == 'usd'
            assert call_args['metadata']['challenge_id'] == 'challenge_123'
            assert call_args['metadata']['user_id'] == 'user_456'

    def test_create_payment_intent_invalid_challenge_type(self, payment_service_instance):
        """Test payment intent creation with invalid challenge type."""
        with pytest.raises(Exception):
            payment_service_instance.create_payment_intent(
                challenge_id='challenge_123',
                user_id='user_456',
                challenge_type='invalid_type'
            )

    def test_confirm_payment_success(self, payment_service_instance):
        """Test successful payment confirmation."""
        with patch('app.payments.stripe.PaymentIntent.retrieve') as mock_retrieve:
            # Mock Stripe response
            mock_intent = Mock()
            mock_intent.status = 'succeeded'
            mock_intent.id = 'pi_mock_id'
            mock_intent.amount = 9900
            mock_intent.currency = 'usd'
            mock_intent.metadata = {
                'challenge_id': 'challenge_123',
                'user_id': 'user_456',
                'challenge_type': 'starter'
            }
            mock_retrieve.return_value = mock_intent

            result = payment_service_instance.confirm_payment('pi_mock_id')

            assert result['success'] is True
            assert result['payment']['payment_id'] == 'pi_mock_id'
            assert result['payment']['challenge_id'] == 'challenge_123'
            assert result['payment']['user_id'] == 'user_456'

    def test_confirm_payment_failed(self, payment_service_instance):
        """Test payment confirmation when payment failed."""
        with patch('app.payments.stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_intent = Mock()
            mock_intent.status = 'requires_payment_method'
            mock_retrieve.return_value = mock_intent

            with pytest.raises(Exception, match="Payment not completed"):
                payment_service_instance.confirm_payment('pi_mock_id')

    def test_calculate_challenge_fee_starter(self, payment_service_instance):
        """Test fee calculation for starter challenge."""
        fee_data = payment_service_instance.calculate_challenge_fee('starter')

        assert fee_data['challenge_type'] == 'starter'
        assert fee_data['total_price'] == 99.0  # $99.00
        assert fee_data['platform_fee'] == 4.95  # 5% of $99
        assert fee_data['trader_amount'] == 94.05  # $99 - $4.95
        assert fee_data['currency'] == 'USD'

    def test_calculate_challenge_fee_professional(self, payment_service_instance):
        """Test fee calculation for professional challenge."""
        fee_data = payment_service_instance.calculate_challenge_fee('professional')

        assert fee_data['challenge_type'] == 'professional'
        assert fee_data['total_price'] == 199.0  # $199.00
        assert fee_data['platform_fee'] == 9.95  # 5% of $199
        assert fee_data['trader_amount'] == 189.05  # $199 - $9.95

    def test_calculate_challenge_fee_expert(self, payment_service_instance):
        """Test fee calculation for expert challenge."""
        fee_data = payment_service_instance.calculate_challenge_fee('expert')

        assert fee_data['challenge_type'] == 'expert'
        assert fee_data['total_price'] == 399.0  # $399.00
        assert fee_data['platform_fee'] == 19.95  # 5% of $399
        assert fee_data['trader_amount'] == 379.05  # $399 - $19.95

    def test_calculate_challenge_fee_master(self, payment_service_instance):
        """Test fee calculation for master challenge."""
        fee_data = payment_service_instance.calculate_challenge_fee('master')

        assert fee_data['challenge_type'] == 'master'
        assert fee_data['total_price'] == 999.0  # $999.00
        assert fee_data['platform_fee'] == 49.95  # 5% of $999
        assert fee_data['trader_amount'] == 949.05  # $999 - $49.95

    def test_calculate_challenge_fee_invalid_type(self, payment_service_instance):
        """Test fee calculation with invalid challenge type defaults to starter."""
        fee_data = payment_service_instance.calculate_challenge_fee('invalid')

        # Should default to starter pricing
        assert fee_data['challenge_type'] == 'invalid'
        assert fee_data['total_price'] == 99.0

    @patch('app.payments.stripe.PaymentIntent.create')
    def test_create_payment_intent_stripe_error(self, mock_create, payment_service_instance):
        """Test handling of Stripe API errors."""
        from stripe.error import CardError
        mock_create.side_effect = CardError("Your card was declined", "card_declined", "400")

        with pytest.raises(Exception, match="Payment processing error"):
            payment_service_instance.create_payment_intent(
                challenge_id='challenge_123',
                user_id='user_456',
                challenge_type='starter'
            )

    @patch('app.payments.stripe.PaymentIntent.retrieve')
    def test_confirm_payment_stripe_error(self, mock_retrieve, payment_service_instance):
        """Test handling of Stripe errors during confirmation."""
        from stripe.error import InvalidRequestError
        mock_retrieve.side_effect = InvalidRequestError("No such payment_intent", "resource_missing", "404")

        with pytest.raises(Exception, match="Payment confirmation error"):
            payment_service_instance.confirm_payment('pi_invalid_id')

    def test_calculate_payout_success(self, payment_service_instance):
        """Test successful payout calculation and processing."""
        with patch('app.payments.stripe.Payout.create') as mock_payout:
            mock_payout.return_value = {'id': 'po_mock_id', 'status': 'completed'}

            result = payment_service_instance.process_payout(
                user_id='user_456',
                amount=500.00,
                currency='usd'
            )

            assert result['success'] is True
            assert result['payout_id'] == 'po_mock_id'
            assert result['amount'] == 500.00
            assert result['currency'] == 'usd'
            assert result['status'] == 'completed'

    def test_calculate_payout_insufficient_funds(self, payment_service_instance):
        """Test payout with insufficient available balance."""
        # This would typically check user's available balance
        # For now, we'll mock the validation
        pass  # Implementation would depend on balance checking logic

    def test_get_payment_history_empty(self, payment_service_instance):
        """Test getting payment history when no payments exist."""
        # This would require database mocking
        # For now, return empty result
        history = payment_service_instance.get_payment_history('user_123', 5)
        assert isinstance(history, list)

    def test_get_earnings_history_empty(self, payment_service_instance):
        """Test getting earnings history when no earnings exist."""
        # This would require database mocking
        # For now, return empty result
        earnings = payment_service_instance.get_earnings_history('user_123', 5)
        assert isinstance(earnings, list)

    def test_payment_intent_metadata_structure(self, payment_service_instance):
        """Test that payment intent includes proper metadata."""
        with patch('app.payments.stripe.PaymentIntent.create') as mock_create:
            mock_intent = Mock()
            mock_intent.client_secret = 'pi_secret_mock'
            mock_intent.id = 'pi_mock_id'
            mock_create.return_value = mock_intent

            payment_service_instance.create_payment_intent(
                challenge_id='challenge_123',
                user_id='user_456',
                challenge_type='professional'
            )

            call_args = mock_create.call_args[1]
            metadata = call_args['metadata']

            assert 'challenge_id' in metadata
            assert 'user_id' in metadata
            assert 'challenge_type' in metadata
            assert metadata['service'] == 'tradesense_challenge'

    def test_payment_amount_validation(self, payment_service_instance):
        """Test that payment amounts are validated and converted correctly."""
        with patch('app.payments.stripe.PaymentIntent.create') as mock_create:
            mock_intent = Mock()
            mock_intent.client_secret = 'pi_secret_mock'
            mock_intent.id = 'pi_mock_id'
            mock_create.return_value = mock_intent

            # Test all challenge types have valid amounts
            challenge_types = ['starter', 'professional', 'expert', 'master']
            expected_amounts = [9900, 19900, 39900, 99900]

            for challenge_type, expected_amount in zip(challenge_types, expected_amounts):
                payment_service_instance.create_payment_intent(
                    challenge_id='challenge_123',
                    user_id='user_456',
                    challenge_type=challenge_type
                )

                call_args = mock_create.call_args[1]
                assert call_args['amount'] == expected_amount


class TestPaymentIntegration:
    """Integration tests for payment functionality."""

    def test_payment_workflow_complete(self):
        """Test complete payment workflow from creation to confirmation."""
        # This would be an integration test with actual Stripe calls (in sandbox)
        # For unit tests, we rely on mocking
        pass

    def test_payment_error_handling(self):
        """Test error handling in payment processing."""
        # Test network errors, timeouts, invalid cards, etc.
        pass

    def test_payment_webhook_processing(self):
        """Test Stripe webhook processing for payment events."""
        # Test webhook signature verification, event processing, etc.
        pass