"""
Payment Simulation Module - TradeSense AI

Simulates payment processing for development and testing.
NO REAL MONEY PROCESSING - Deterministic behavior for testing.

Supports:
- CMI (Moroccan payment gateway)
- Crypto (Bitcoin, Ethereum)
- PayPal (optional via env variables)

Pricing Tiers (MAD - Moroccan Dirham):
- Starter: 200 DH
- Pro: 500 DH
- Elite: 1000 DH
"""

import os
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentProvider(str, Enum):
    """Supported payment providers."""
    CMI = "CMI"
    CRYPTO = "CRYPTO"
    PAYPAL = "PAYPAL"


class CryptoType(str, Enum):
    """Supported cryptocurrencies."""
    BITCOIN = "BTC"
    ETHEREUM = "ETH"
    USDT = "USDT"


class PricingTier(str, Enum):
    """Challenge pricing tiers."""
    STARTER = "STARTER"
    PRO = "PRO"
    ELITE = "ELITE"


class PaymentStatus(str, Enum):
    """Payment processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Pricing configuration (in Moroccan Dirham)
PRICING_CONFIG = {
    PricingTier.STARTER: {
        "price_mad": Decimal("200.00"),
        "price_usd": Decimal("20.00"),  # Approximate conversion
        "initial_balance": Decimal("10000.00"),
        "max_daily_drawdown": Decimal("0.05"),  # 5%
        "max_total_drawdown": Decimal("0.10"),  # 10%
        "profit_target": Decimal("0.08"),  # 8%
        "description": "Perfect for beginners - Start your trading journey"
    },
    PricingTier.PRO: {
        "price_mad": Decimal("500.00"),
        "price_usd": Decimal("50.00"),
        "initial_balance": Decimal("25000.00"),
        "max_daily_drawdown": Decimal("0.05"),
        "max_total_drawdown": Decimal("0.10"),
        "profit_target": Decimal("0.08"),
        "description": "For serious traders - Scale your trading"
    },
    PricingTier.ELITE: {
        "price_mad": Decimal("1000.00"),
        "price_usd": Decimal("100.00"),
        "initial_balance": Decimal("50000.00"),
        "max_daily_drawdown": Decimal("0.05"),
        "max_total_drawdown": Decimal("0.10"),
        "profit_target": Decimal("0.08"),
        "description": "Elite traders - Maximum capital allocation"
    }
}


class PaymentSimulator:
    """
    Simulates payment processing without real money transactions.
    
    Provides deterministic behavior for testing and development.
    """
    
    def __init__(self):
        """Initialize payment simulator with configuration."""
        self.cmi_merchant_id = os.getenv('CMI_MERCHANT_ID', 'TEST_MERCHANT_001')
        self.cmi_secret_key = os.getenv('CMI_SECRET_KEY', 'test_secret_key_12345')
        
        # PayPal configuration (optional)
        self.paypal_enabled = os.getenv('PAYPAL_ENABLED', 'false').lower() == 'true'
        self.paypal_client_id = os.getenv('PAYPAL_CLIENT_ID', '')
        self.paypal_secret = os.getenv('PAYPAL_SECRET', '')
        
        # Crypto wallet addresses (simulated)
        self.crypto_wallets = {
            CryptoType.BITCOIN: os.getenv('BTC_WALLET', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'),
            CryptoType.ETHEREUM: os.getenv('ETH_WALLET', '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb'),
            CryptoType.USDT: os.getenv('USDT_WALLET', '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb')
        }
        
        # Conversion rates (simulated - would be fetched from API in production)
        self.crypto_rates = {
            CryptoType.BITCOIN: Decimal("43000.00"),  # 1 BTC = $43,000
            CryptoType.ETHEREUM: Decimal("2300.00"),   # 1 ETH = $2,300
            CryptoType.USDT: Decimal("1.00")           # 1 USDT = $1
        }
        
        # MAD to USD conversion rate
        self.mad_to_usd = Decimal("0.10")  # 1 MAD ≈ 0.10 USD
        
        logger.info("Payment simulator initialized (NO REAL MONEY PROCESSING)")
    
    def get_pricing(self, tier: PricingTier) -> Dict:
        """
        Get pricing information for a tier.
        
        Args:
            tier: Pricing tier
            
        Returns:
            Pricing details including all currencies
        """
        config = PRICING_CONFIG[tier]
        
        return {
            "tier": tier.value,
            "price_mad": float(config["price_mad"]),
            "price_usd": float(config["price_usd"]),
            "currency": "MAD",
            "description": config["description"],
            "challenge_config": {
                "initial_balance": float(config["initial_balance"]),
                "max_daily_drawdown_percent": float(config["max_daily_drawdown"] * 100),
                "max_total_drawdown_percent": float(config["max_total_drawdown"] * 100),
                "profit_target_percent": float(config["profit_target"] * 100)
            }
        }
    
    def get_all_pricing(self) -> Dict:
        """Get pricing for all tiers."""
        return {
            tier.value: self.get_pricing(tier)
            for tier in PricingTier
        }
    
    def initiate_cmi_payment(
        self,
        user_id: str,
        tier: PricingTier,
        return_url: str
    ) -> Dict:
        """
        Initiate CMI payment (Moroccan payment gateway).
        
        Simulates CMI payment flow with deterministic behavior.
        
        Args:
            user_id: User making the payment
            tier: Pricing tier
            return_url: URL to return after payment
            
        Returns:
            Payment initiation data with redirect URL
        """
        config = PRICING_CONFIG[tier]
        payment_id = f"CMI_{uuid.uuid4().hex[:16].upper()}"
        
        # Generate deterministic transaction reference
        transaction_ref = self._generate_transaction_ref(payment_id, user_id)
        
        # Calculate signature (simulated CMI signature)
        signature = self._generate_cmi_signature(
            payment_id,
            config["price_mad"],
            transaction_ref
        )
        
        payment_data = {
            "payment_id": payment_id,
            "provider": PaymentProvider.CMI.value,
            "status": PaymentStatus.PENDING.value,
            "amount": float(config["price_mad"]),
            "currency": "MAD",
            "tier": tier.value,
            "user_id": user_id,
            "transaction_ref": transaction_ref,
            "signature": signature,
            "redirect_url": f"https://testpayment.cmi.co.ma/payment?ref={transaction_ref}",
            "return_url": return_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "simulation_note": "This is a SIMULATED payment - no real money will be processed"
        }
        
        logger.info(f"CMI payment initiated: {payment_id} for {config['price_mad']} MAD")
        
        return payment_data
    
    def simulate_cmi_callback(
        self,
        payment_id: str,
        transaction_ref: str,
        success: bool = True
    ) -> Dict:
        """
        Simulate CMI payment callback.
        
        In production, this would be called by CMI's servers.
        For simulation, we provide deterministic success/failure.
        
        Args:
            payment_id: Payment identifier
            transaction_ref: Transaction reference
            success: Whether payment succeeded (default: True for testing)
            
        Returns:
            Payment result data
        """
        if success:
            status = PaymentStatus.SUCCESS
            message = "Payment processed successfully"
            cmi_response_code = "00"  # Success code
        else:
            status = PaymentStatus.FAILED
            message = "Payment declined by bank"
            cmi_response_code = "05"  # Declined code
        
        result = {
            "payment_id": payment_id,
            "transaction_ref": transaction_ref,
            "status": status.value,
            "provider": PaymentProvider.CMI.value,
            "cmi_response_code": cmi_response_code,
            "message": message,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "simulation": True
        }
        
        logger.info(f"CMI callback simulated: {payment_id} - {status.value}")
        
        return result
    
    def initiate_crypto_payment(
        self,
        user_id: str,
        tier: PricingTier,
        crypto_type: CryptoType
    ) -> Dict:
        """
        Initiate cryptocurrency payment.
        
        Simulates crypto payment with wallet address and amount.
        
        Args:
            user_id: User making the payment
            tier: Pricing tier
            crypto_type: Type of cryptocurrency
            
        Returns:
            Crypto payment data with wallet address and amount
        """
        config = PRICING_CONFIG[tier]
        payment_id = f"CRYPTO_{uuid.uuid4().hex[:16].upper()}"
        
        # Convert MAD to USD, then to crypto
        amount_usd = config["price_mad"] * self.mad_to_usd
        crypto_rate = self.crypto_rates[crypto_type]
        crypto_amount = amount_usd / crypto_rate
        
        wallet_address = self.crypto_wallets[crypto_type]
        
        payment_data = {
            "payment_id": payment_id,
            "provider": PaymentProvider.CRYPTO.value,
            "crypto_type": crypto_type.value,
            "status": PaymentStatus.PENDING.value,
            "amount_mad": float(config["price_mad"]),
            "amount_usd": float(amount_usd),
            "crypto_amount": float(crypto_amount),
            "crypto_rate": float(crypto_rate),
            "wallet_address": wallet_address,
            "tier": tier.value,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?data={wallet_address}&size=300x300",
            "instructions": f"Send exactly {crypto_amount:.8f} {crypto_type.value} to the wallet address above",
            "simulation_note": "This is a SIMULATED payment - no real crypto will be transferred"
        }
        
        logger.info(f"Crypto payment initiated: {payment_id} - {crypto_amount:.8f} {crypto_type.value}")
        
        return payment_data
    
    def simulate_crypto_confirmation(
        self,
        payment_id: str,
        transaction_hash: Optional[str] = None,
        confirmations: int = 6
    ) -> Dict:
        """
        Simulate cryptocurrency payment confirmation.
        
        In production, this would monitor blockchain for transactions.
        
        Args:
            payment_id: Payment identifier
            transaction_hash: Blockchain transaction hash (generated if not provided)
            confirmations: Number of blockchain confirmations
            
        Returns:
            Confirmation data
        """
        if not transaction_hash:
            transaction_hash = f"0x{uuid.uuid4().hex}"
        
        result = {
            "payment_id": payment_id,
            "status": PaymentStatus.SUCCESS.value,
            "provider": PaymentProvider.CRYPTO.value,
            "transaction_hash": transaction_hash,
            "confirmations": confirmations,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "blockchain_explorer_url": f"https://blockchain.info/tx/{transaction_hash}",
            "message": "Crypto payment confirmed",
            "simulation": True
        }
        
        logger.info(f"Crypto payment confirmed: {payment_id} - {transaction_hash}")
        
        return result
    
    def initiate_paypal_payment(
        self,
        user_id: str,
        tier: PricingTier,
        return_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Initiate PayPal payment (optional - requires env configuration).
        
        Args:
            user_id: User making the payment
            tier: Pricing tier
            return_url: Success return URL
            cancel_url: Cancel return URL
            
        Returns:
            PayPal payment data
        """
        if not self.paypal_enabled:
            raise ValueError("PayPal is not enabled. Set PAYPAL_ENABLED=true in environment")
        
        config = PRICING_CONFIG[tier]
        payment_id = f"PAYPAL_{uuid.uuid4().hex[:16].upper()}"
        
        # Convert MAD to USD for PayPal
        amount_usd = config["price_mad"] * self.mad_to_usd
        
        payment_data = {
            "payment_id": payment_id,
            "provider": PaymentProvider.PAYPAL.value,
            "status": PaymentStatus.PENDING.value,
            "amount_mad": float(config["price_mad"]),
            "amount_usd": float(amount_usd),
            "currency": "USD",
            "tier": tier.value,
            "user_id": user_id,
            "paypal_order_id": f"ORDER_{uuid.uuid4().hex[:12].upper()}",
            "approval_url": f"https://www.sandbox.paypal.com/checkoutnow?token={payment_id}",
            "return_url": return_url,
            "cancel_url": cancel_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            "simulation_note": "This is a SIMULATED PayPal payment - no real money will be processed"
        }
        
        logger.info(f"PayPal payment initiated: {payment_id} for ${amount_usd} USD")
        
        return payment_data
    
    def simulate_paypal_capture(
        self,
        payment_id: str,
        paypal_order_id: str,
        success: bool = True
    ) -> Dict:
        """
        Simulate PayPal payment capture.
        
        Args:
            payment_id: Payment identifier
            paypal_order_id: PayPal order ID
            success: Whether capture succeeded
            
        Returns:
            Capture result
        """
        if success:
            status = PaymentStatus.SUCCESS
            message = "PayPal payment captured successfully"
            payer_email = "buyer@example.com"
        else:
            status = PaymentStatus.FAILED
            message = "PayPal payment capture failed"
            payer_email = None
        
        result = {
            "payment_id": payment_id,
            "paypal_order_id": paypal_order_id,
            "status": status.value,
            "provider": PaymentProvider.PAYPAL.value,
            "payer_email": payer_email,
            "message": message,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "simulation": True
        }
        
        logger.info(f"PayPal capture simulated: {payment_id} - {status.value}")
        
        return result
    
    def _generate_transaction_ref(self, payment_id: str, user_id: str) -> str:
        """Generate deterministic transaction reference."""
        data = f"{payment_id}:{user_id}:{datetime.now(timezone.utc).date()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16].upper()
    
    def _generate_cmi_signature(
        self,
        payment_id: str,
        amount: Decimal,
        transaction_ref: str
    ) -> str:
        """Generate CMI payment signature (simulated)."""
        data = f"{self.cmi_merchant_id}:{payment_id}:{amount}:{transaction_ref}:{self.cmi_secret_key}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_payment_signature(
        self,
        payment_id: str,
        amount: Decimal,
        transaction_ref: str,
        signature: str
    ) -> bool:
        """
        Verify payment signature for security.
        
        Args:
            payment_id: Payment identifier
            amount: Payment amount
            transaction_ref: Transaction reference
            signature: Signature to verify
            
        Returns:
            True if signature is valid
        """
        expected_signature = self._generate_cmi_signature(payment_id, amount, transaction_ref)
        return signature == expected_signature


# Global payment simulator instance
payment_simulator = PaymentSimulator()
