"""
Comprehensive tests for Payment Simulation System

Tests all payment providers (CMI, Crypto, PayPal) and access control.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.payment_simulation import (
    payment_simulator,
    PaymentProvider,
    PricingTier,
    CryptoType,
    PaymentStatus
)


class TestPricingConfiguration:
    """Test pricing tier configuration."""
    
    def test_get_starter_pricing(self):
        """Test STARTER tier pricing."""
        pricing = payment_simulator.get_pricing(PricingTier.STARTER)
        
        assert pricing['tier'] == 'STARTER'
        assert pricing['price_mad'] == 200.0
        assert pricing['price_usd'] == 20.0
        assert pricing['challenge_config']['initial_balance'] == 10000.0
        assert pricing['challenge_config']['max_daily_drawdown_percent'] == 5.0
        assert pricing['challenge_config']['max_total_drawdown_percent'] == 10.0
        assert pricing['challenge_config']['profit_target_percent'] == 8.0
    
    def test_get_pro_pricing(self):
        """Test PRO tier pricing."""
        pricing = payment_simulator.get_pricing(PricingTier.PRO)
        
        assert pricing['tier'] == 'PRO'
        assert pricing['price_mad'] == 500.0
        assert pricing['price_usd'] == 50.0
        assert pricing['challenge_config']['initial_balance'] == 25000.0
    
    def test_get_elite_pricing(self):
        """Test ELITE tier pricing."""
        pricing = payment_simulator.get_pricing(PricingTier.ELITE)
        
        assert pricing['tier'] == 'ELITE'
        assert pricing['price_mad'] == 1000.0
        assert pricing['price_usd'] == 100.0
        assert pricing['challenge_config']['initial_balance'] == 50000.0
    
    def test_get_all_pricing(self):
        """Test getting all pricing tiers."""
        all_pricing = payment_simulator.get_all_pricing()
        
        assert len(all_pricing) == 3
        assert 'STARTER' in all_pricing
        assert 'PRO' in all_pricing
        assert 'ELITE' in all_pricing


class TestCMIPayment:
    """Test CMI (Moroccan Payment Gateway) simulation."""
    
    def test_initiate_cmi_payment(self):
        """Test CMI payment initiation."""
        payment_data = payment_simulator.initiate_cmi_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            return_url="http://localhost:3000/success"
        )
        
        assert payment_data['provider'] == PaymentProvider.CMI.value
        assert payment_data['status'] == PaymentStatus.PENDING.value
        assert payment_data['amount'] == 200.0
        assert payment_data['currency'] == 'MAD'
        assert payment_data['tier'] == 'STARTER'
        assert payment_data['user_id'] == "test-user-123"
        assert 'payment_id' in payment_data
        assert payment_data['payment_id'].startswith('CMI_')
        assert 'transaction_ref' in payment_data
        assert 'signature' in payment_data
        assert 'redirect_url' in payment_data
        assert 'simulation_note' in payment_data
    
    def test_cmi_payment_success(self):
        """Test successful CMI payment callback."""
        # Initiate payment
        payment_data = payment_simulator.initiate_cmi_payment(
            user_id="test-user-123",
            tier=PricingTier.PRO,
            return_url="http://localhost:3000/success"
        )
        
        # Simulate success callback
        result = payment_simulator.simulate_cmi_callback(
            payment_id=payment_data['payment_id'],
            transaction_ref=payment_data['transaction_ref'],
            success=True
        )
        
        assert result['status'] == PaymentStatus.SUCCESS.value
        assert result['provider'] == PaymentProvider.CMI.value
        assert result['cmi_response_code'] == '00'
        assert result['message'] == 'Payment processed successfully'
        assert result['simulation'] is True
    
    def test_cmi_payment_failure(self):
        """Test failed CMI payment callback."""
        payment_data = payment_simulator.initiate_cmi_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            return_url="http://localhost:3000/success"
        )
        
        result = payment_simulator.simulate_cmi_callback(
            payment_id=payment_data['payment_id'],
            transaction_ref=payment_data['transaction_ref'],
            success=False
        )
        
        assert result['status'] == PaymentStatus.FAILED.value
        assert result['cmi_response_code'] == '05'
        assert result['message'] == 'Payment declined by bank'
    
    def test_cmi_signature_verification(self):
        """Test CMI signature verification."""
        payment_data = payment_simulator.initiate_cmi_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            return_url="http://localhost:3000/success"
        )
        
        # Verify signature
        is_valid = payment_simulator.verify_payment_signature(
            payment_id=payment_data['payment_id'],
            amount=Decimal('200.00'),
            transaction_ref=payment_data['transaction_ref'],
            signature=payment_data['signature']
        )
        
        assert is_valid is True
        
        # Test invalid signature
        is_valid = payment_simulator.verify_payment_signature(
            payment_id=payment_data['payment_id'],
            amount=Decimal('200.00'),
            transaction_ref=payment_data['transaction_ref'],
            signature='invalid_signature'
        )
        
        assert is_valid is False


class TestCryptoPayment:
    """Test cryptocurrency payment simulation."""
    
    def test_initiate_bitcoin_payment(self):
        """Test Bitcoin payment initiation."""
        payment_data = payment_simulator.initiate_crypto_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            crypto_type=CryptoType.BITCOIN
        )
        
        assert payment_data['provider'] == PaymentProvider.CRYPTO.value
        assert payment_data['crypto_type'] == 'BTC'
        assert payment_data['status'] == PaymentStatus.PENDING.value
        assert payment_data['amount_mad'] == 200.0
        assert 'crypto_amount' in payment_data
        assert 'wallet_address' in payment_data
        assert 'qr_code_url' in payment_data
        assert 'simulation_note' in payment_data
    
    def test_initiate_ethereum_payment(self):
        """Test Ethereum payment initiation."""
        payment_data = payment_simulator.initiate_crypto_payment(
            user_id="test-user-123",
            tier=PricingTier.PRO,
            crypto_type=CryptoType.ETHEREUM
        )
        
        assert payment_data['crypto_type'] == 'ETH'
        assert payment_data['amount_mad'] == 500.0
    
    def test_initiate_usdt_payment(self):
        """Test USDT payment initiation."""
        payment_data = payment_simulator.initiate_crypto_payment(
            user_id="test-user-123",
            tier=PricingTier.ELITE,
            crypto_type=CryptoType.USDT
        )
        
        assert payment_data['crypto_type'] == 'USDT'
        assert payment_data['amount_mad'] == 1000.0
    
    def test_crypto_payment_confirmation(self):
        """Test cryptocurrency payment confirmation."""
        payment_data = payment_simulator.initiate_crypto_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            crypto_type=CryptoType.BITCOIN
        )
        
        result = payment_simulator.simulate_crypto_confirmation(
            payment_id=payment_data['payment_id'],
            confirmations=6
        )
        
        assert result['status'] == PaymentStatus.SUCCESS.value
        assert result['provider'] == PaymentProvider.CRYPTO.value
        assert result['confirmations'] == 6
        assert 'transaction_hash' in result
        assert 'blockchain_explorer_url' in result
        assert result['simulation'] is True
    
    def test_crypto_exchange_rate_conversion(self):
        """Test crypto exchange rate conversion."""
        payment_data = payment_simulator.initiate_crypto_payment(
            user_id="test-user-123",
            tier=PricingTier.STARTER,
            crypto_type=CryptoType.BITCOIN
        )
        
        # Verify conversion calculation
        mad_amount = Decimal('200.00')
        usd_amount = mad_amount * payment_simulator.mad_to_usd
        btc_rate = payment_simulator.crypto_rates[CryptoType.BITCOIN]
        expected_btc = usd_amount / btc_rate
        
        assert abs(payment_data['crypto_amount'] - float(expected_btc)) < 0.00000001


class TestPayPalPayment:
    """Test PayPal payment simulation."""
    
    def test_paypal_disabled_by_default(self):
        """Test that PayPal is disabled by default."""
        with pytest.raises(ValueError, match="PayPal is not enabled"):
            payment_simulator.initiate_paypal_payment(
                user_id="test-user-123",
                tier=PricingTier.STARTER,
                return_url="http://localhost:3000/success",
                cancel_url="http://localhost:3000/cancel"
            )
    
    def test_paypal_payment_capture_success(self):
        """Test successful PayPal payment capture."""
        result = payment_simulator.simulate_paypal_capture(
            payment_id="PAYPAL_TEST123",
            paypal_order_id="ORDER_TEST123",
            success=True
        )
        
        assert result['status'] == PaymentStatus.SUCCESS.value
        assert result['provider'] == PaymentProvider.PAYPAL.value
        assert result['message'] == 'PayPal payment captured successfully'
        assert 'payer_email' in result
        assert result['simulation'] is True
    
    def test_paypal_payment_capture_failure(self):
        """Test failed PayPal payment capture."""
        result = payment_simulator.simulate_paypal_capture(
            payment_id="PAYPAL_TEST123",
            paypal_order_id="ORDER_TEST123",
            success=False
        )
        
        assert result['status'] == PaymentStatus.FAILED.value
        assert result['message'] == 'PayPal payment capture failed'


class TestPaymentSimulationSafety:
    """Test payment simulation safety features."""
    
    def test_no_real_money_processing(self):
        """Verify all payments are simulated."""
        # CMI
        cmi_payment = payment_simulator.initiate_cmi_payment(
            user_id="test-user",
            tier=PricingTier.STARTER,
            return_url="http://test.com"
        )
        assert 'simulation_note' in cmi_payment
        assert 'SIMULATED' in cmi_payment['simulation_note']
        
        # Crypto
        crypto_payment = payment_simulator.initiate_crypto_payment(
            user_id="test-user",
            tier=PricingTier.STARTER,
            crypto_type=CryptoType.BITCOIN
        )
        assert 'simulation_note' in crypto_payment
        assert 'SIMULATED' in crypto_payment['simulation_note']
    
    def test_deterministic_behavior(self):
        """Test that payment simulation is deterministic."""
        # Same inputs should produce consistent results
        payment1 = payment_simulator.initiate_cmi_payment(
            user_id="test-user",
            tier=PricingTier.STARTER,
            return_url="http://test.com"
        )
        
        payment2 = payment_simulator.initiate_cmi_payment(
            user_id="test-user",
            tier=PricingTier.STARTER,
            return_url="http://test.com"
        )
        
        # Payment IDs will be different (unique)
        assert payment1['payment_id'] != payment2['payment_id']
        
        # But amounts and structure should be the same
        assert payment1['amount'] == payment2['amount']
        assert payment1['currency'] == payment2['currency']
        assert payment1['tier'] == payment2['tier']
    
    def test_payment_expiry(self):
        """Test payment expiry times."""
        payment = payment_simulator.initiate_cmi_payment(
            user_id="test-user",
            tier=PricingTier.STARTER,
            return_url="http://test.com"
        )
        
        created_at = datetime.fromisoformat(payment['created_at'].replace('Z', '+00:00'))
        expires_at = datetime.fromisoformat(payment['expires_at'].replace('Z', '+00:00'))
        
        # CMI payments expire in 15 minutes
        time_diff = (expires_at - created_at).total_seconds()
        assert time_diff == 900  # 15 minutes


class TestPaymentIntegration:
    """Test payment system integration scenarios."""
    
    def test_complete_payment_flow(self):
        """Test complete payment flow from initiation to confirmation."""
        # 1. Initiate payment
        payment = payment_simulator.initiate_cmi_payment(
            user_id="test-user-123",
            tier=PricingTier.PRO,
            return_url="http://localhost:3000/success"
        )
        
        assert payment['status'] == PaymentStatus.PENDING.value
        
        # 2. User completes payment (simulated)
        # In real scenario, user would be redirected to CMI gateway
        
        # 3. Receive callback
        result = payment_simulator.simulate_cmi_callback(
            payment_id=payment['payment_id'],
            transaction_ref=payment['transaction_ref'],
            success=True
        )
        
        assert result['status'] == PaymentStatus.SUCCESS.value
        
        # 4. At this point, challenge would be created/activated
        # (This is handled by the API layer, not the simulator)
    
    def test_multiple_payment_providers(self):
        """Test that all payment providers work correctly."""
        user_id = "test-user-123"
        tier = PricingTier.STARTER
        
        # CMI
        cmi_payment = payment_simulator.initiate_cmi_payment(
            user_id=user_id,
            tier=tier,
            return_url="http://test.com"
        )
        assert cmi_payment['provider'] == 'CMI'
        
        # Crypto
        crypto_payment = payment_simulator.initiate_crypto_payment(
            user_id=user_id,
            tier=tier,
            crypto_type=CryptoType.BITCOIN
        )
        assert crypto_payment['provider'] == 'CRYPTO'
        
        # All payments for same tier should have same MAD amount
        assert cmi_payment['amount'] == crypto_payment['amount_mad']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
