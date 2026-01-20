"""Tests for the Payment Domain."""

import pytest
from uuid import uuid4

from shared.utils.money import Money
from domains.payments.domain.entities import Payment, PaymentMethod, PaymentStatus
from domains.payments.domain.services import PaymentValidationService


class TestPaymentEntity:
    """Test the Payment entity."""

    def test_payment_creation(self):
        """Test creating a payment."""
        payment_id = uuid4()
        customer_id = uuid4()
        amount = Money(10000, "USD")  # $100.00

        payment = Payment(
            payment_id=payment_id,
            idempotency_key="test_key_123",
            amount=amount,
            customer_id=customer_id,
            payment_method=PaymentMethod(
                payment_method_id="pm_test",
                type="card",
                provider="stripe",
            ),
            description="Test payment",
        )

        assert payment.id == payment_id
        assert payment.amount == amount
        assert payment.customer_id == customer_id
        assert payment.status.value == "pending"
        assert payment.idempotency_key == "test_key_123"

    def test_payment_status_transitions(self):
        """Test payment status transitions."""
        payment = Payment(
            payment_id=uuid4(),
            idempotency_key="test_key",
            amount=Money(10000, "USD"),
            customer_id=uuid4(),
            payment_method=PaymentMethod(
                payment_method_id="pm_test",
                type="card",
                provider="stripe",
            ),
            description="Test payment",
        )

        # Initial state
        assert payment.status.value == "pending"

        # Valid transition: pending -> processing
        payment.mark_as_processing()
        assert payment.status.value == "processing"

        # Valid transition: processing -> succeeded
        payment.mark_as_succeeded(
            provider_payment_id="pi_test",
            fees=Money(290, "USD"),
            processed_at=payment.created_at,
        )
        assert payment.status.value == "succeeded"
        assert payment.fees == Money(290, "USD")
        assert payment.net_amount == Money(9710, "USD")

    def test_invalid_status_transitions(self):
        """Test invalid payment status transitions."""
        payment = Payment(
            payment_id=uuid4(),
            idempotency_key="test_key",
            amount=Money(10000, "USD"),
            customer_id=uuid4(),
            payment_method=PaymentMethod(
                payment_method_id="pm_test",
                type="card",
                provider="stripe",
            ),
            description="Test payment",
        )

        # Try invalid transition: pending -> succeeded (should fail)
        with pytest.raises(ValueError):
            payment.mark_as_succeeded(
                provider_payment_id="pi_test",
                fees=Money(290, "USD"),
                processed_at=payment.created_at,
            )


class TestPaymentMethodEntity:
    """Test the PaymentMethod entity."""

    def test_payment_method_creation(self):
        """Test creating a payment method."""
        pm = PaymentMethod(
            payment_method_id="pm_test_123",
            type="card",
            provider="stripe",
            is_default=True,
            metadata={"brand": "visa", "last4": "4242"},
        )

        assert pm.payment_method_id == "pm_test_123"
        assert pm.type == "card"
        assert pm.provider == "stripe"
        assert pm.is_default is True
        assert pm.metadata["brand"] == "visa"

    def test_payment_method_expiry(self):
        """Test payment method expiry."""
        from datetime import datetime

        # Non-expired method
        pm_valid = PaymentMethod(
            payment_method_id="pm_valid",
            type="card",
            provider="stripe",
        )
        assert not pm_valid.is_expired()

        # Expired method
        expired_date = datetime(2020, 1, 1)
        pm_expired = PaymentMethod(
            payment_method_id="pm_expired",
            type="card",
            provider="stripe",
            expires_at=expired_date,
        )
        assert pm_expired.is_expired()


class TestPaymentValidationService:
    """Test the PaymentValidationService."""

    def test_validate_payment_amount(self):
        """Test payment amount validation."""
        service = PaymentValidationService()

        # Valid amount
        service.validate_payment_amount(Money(10000, "USD"))

        # Invalid amounts
        with pytest.raises(ValueError):
            service.validate_payment_amount(Money(-100, "USD"))

        with pytest.raises(ValueError):
            service.validate_payment_amount(Money(0, "USD"))

    def test_validate_payment_method(self):
        """Test payment method validation."""
        service = PaymentValidationService()

        # Valid payment method
        pm_valid = PaymentMethod(
            payment_method_id="pm_valid",
            type="card",
            provider="stripe",
        )
        service.validate_payment_method(pm_valid)

        # Invalid type
        pm_invalid = PaymentMethod(
            payment_method_id="pm_invalid",
            type="invalid_type",
            provider="stripe",
        )
        with pytest.raises(ValueError):
            service.validate_payment_method(pm_invalid)

    def test_validate_refund_amount(self):
        """Test refund amount validation."""
        service = PaymentValidationService()

        payment = Payment(
            payment_id=uuid4(),
            idempotency_key="test",
            amount=Money(10000, "USD"),
            customer_id=uuid4(),
            payment_method=PaymentMethod("pm", "card", "stripe"),
            description="Test",
        )

        # Valid refund
        service.validate_refund_amount(payment, Money(5000, "USD"))

        # Invalid currency
        with pytest.raises(ValueError):
            service.validate_refund_amount(payment, Money(5000, "EUR"))

        # Refund too large
        payment.mark_as_succeeded("pi_test", Money(0, "USD"), payment.created_at)
        with pytest.raises(ValueError):
            service.validate_refund_amount(payment, Money(15000, "USD"))


class TestPaymentStatus:
    """Test the PaymentStatus value object."""

    def test_valid_statuses(self):
        """Test valid payment statuses."""
        for status in PaymentStatus.VALID_STATUSES:
            ps = PaymentStatus(status)
            assert ps.value == status

    def test_invalid_status(self):
        """Test invalid payment status."""
        with pytest.raises(ValueError):
            PaymentStatus("invalid_status")

    def test_terminal_statuses(self):
        """Test terminal status detection."""
        assert PaymentStatus("succeeded").is_terminal()
        assert PaymentStatus("failed").is_terminal()
        assert PaymentStatus("cancelled").is_terminal()
        assert not PaymentStatus("pending").is_terminal()
        assert not PaymentStatus("processing").is_terminal()

    def test_status_transitions(self):
        """Test status transition validation."""
        pending = PaymentStatus("pending")
        processing = PaymentStatus("processing")
        succeeded = PaymentStatus("succeeded")
        failed = PaymentStatus("failed")

        # Valid transitions
        assert pending.can_transition_to(processing)
        assert processing.can_transition_to(succeeded)
        assert processing.can_transition_to(failed)

        # Invalid transitions
        assert not pending.can_transition_to(succeeded)
        assert not succeeded.can_transition_to(processing)


# Integration test example (would need proper setup)
@pytest.mark.integration
class TestPaymentIntegration:
    """Integration tests for payment flows."""

    @pytest.mark.asyncio
    async def test_full_payment_flow(self):
        """Test complete payment flow."""
        # This would test the full payment flow with mocked providers
        # For now, just a placeholder
        assert True

    @pytest.mark.asyncio
    async def test_idempotency(self):
        """Test idempotency functionality."""
        # Test that same idempotency key returns same result
        assert True