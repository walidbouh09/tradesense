"""Example usage of the Payment Domain in TradeSense AI."""

import asyncio
from uuid import uuid4

from shared.utils.money import Money
from domains.payments.application.services import PaymentApplicationService
from domains.payments.infrastructure.repositories import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyPaymentMethodRepository,
    SqlAlchemyTransactionRepository,
    RedisIdempotencyRepository,
)
from domains.payments.domain.services import (
    PaymentValidationService,
    IdempotencyService,
    WebhookProcessingService,
)
from domains.payments.infrastructure.providers.stripe_provider import StripeProvider


async def example_payment_flow():
    """Example of creating and managing a payment."""

    # This is a simplified example - in production you'd use proper dependency injection

    print("=== TradeSense AI Payment Domain Example ===\n")

    # 1. Create a payment
    print("1. Creating a payment...")

    payment_data = {
        "idempotency_key": str(uuid4()),
        "amount": Money(10000, "USD"),  # $100.00
        "customer_id": uuid4(),
        "payment_method_id": "pm_card_visa",  # Example payment method ID
        "description": "TradeSense Pro Monthly Subscription",
        "metadata": {
            "subscription_id": "sub_monthly_pro",
            "billing_cycle": "monthly",
        },
    }

    # In a real application, these would be injected
    # For this example, we'll show the API usage

    print("✓ Payment creation request prepared")
    print(f"  Amount: {payment_data['amount']}")
    print(f"  Description: {payment_data['description']}")
    print(f"  Idempotency Key: {payment_data['idempotency_key'][:8]}...")

    # 2. Simulate API call (would be done via FastAPI in real usage)
    print("\n2. API Request (simulated):")
    print("POST /payments")
    print("""
{
  "idempotency_key": "123e4567-e89b-12d3-a456-426614174000",
  "amount": {
    "amount": "100.00",
    "currency": "USD"
  },
  "customer_id": "456e7890-e89b-12d3-a456-426614174001",
  "payment_method_id": "pm_card_visa",
  "description": "TradeSense Pro Monthly Subscription",
  "provider": "stripe",
  "metadata": {
    "subscription_id": "sub_monthly_pro"
  },
  "capture": true
}
""")

    # 3. Show domain events that would be emitted
    print("3. Domain Events Emitted:")
    print("✓ PaymentCreated")
    print("  ├── aggregate_id: payment_uuid")
    print("  ├── customer_id: customer_uuid")
    print("  ├── amount: 100.00 USD")
    print("  └── provider: stripe")

    print("\n✓ PaymentStatusChanged (PENDING → PROCESSING)")
    print("  ├── old_status: pending")
    print("  └── new_status: processing")

    print("\n✓ PaymentSucceeded (if payment succeeds)")
    print("  ├── net_amount: 97.10 USD (after 2.9% fee)")
    print("  ├── fees: 2.90 USD")
    print("  └── provider_payment_id: pi_stripe_123")

    # 4. Show payment method management
    print("\n4. Payment Method Management:")
    print("POST /payment-methods")
    print("""
{
  "type": "card",
  "provider": "stripe",
  "payment_method_data": {
    "type": "card",
    "card": {
      "number": "4242424242424242",
      "exp_month": 12,
      "exp_year": 2025,
      "cvc": "123"
    }
  }
}
""")

    # 5. Show refund process
    print("\n5. Refund Process:")
    print("POST /payments/{payment_id}/refund")
    print("""
{
  "amount": {
    "amount": "50.00",
    "currency": "USD"
  },
  "reason": "Customer requested refund"
}
""")

    print("✓ Refund Transaction Created")
    print("✓ PaymentRefunded Event Emitted")

    # 6. Show webhook processing
    print("\n6. Webhook Processing:")
    print("POST /payments/webhooks/stripe")
    print("Headers: stripe-signature: t=123,v1=signature...")
    print("""
{
  "id": "evt_webhook_123",
  "type": "payment_intent.succeeded",
  "data": {
    "object": {
      "id": "pi_stripe_123",
      "status": "succeeded"
    }
  }
}
""")

    print("✓ Webhook Signature Verified")
    print("✓ Payment Status Updated")
    print("✓ WebhookProcessed Event Emitted")

    print("\n=== Payment Flow Complete ===")


async def example_idempotency():
    """Example of idempotency in action."""

    print("\n=== Idempotency Example ===\n")

    # Same idempotency key used multiple times
    idempotency_key = "idem_test_123"

    print(f"Using idempotency key: {idempotency_key}")
    print("1. First request - payment created")
    print("2. Second request with same key - returns cached result")
    print("3. Third request with same key - returns same cached result")

    print("\n✓ Prevents duplicate charges")
    print("✓ Safe retry mechanism")
    print("✓ 24-hour idempotency window")


async def example_error_handling():
    """Example of error handling."""

    print("\n=== Error Handling Examples ===\n")

    print("1. Invalid Payment Amount:")
    print("   Amount: -100 USD")
    print("   → ValueError: Payment amount must be positive")

    print("\n2. Expired Payment Method:")
    print("   Expiry: 2020-01-01")
    print("   → ValueError: Payment method is expired")

    print("\n3. Insufficient Funds (Provider Error):")
    print("   → PaymentFailed: card_declined")
    print("   → Automatic retry with different payment method")

    print("\n4. Network Timeout:")
    print("   → Automatic retry with exponential backoff")
    print("   → Circuit breaker prevents cascade failures")


def main():
    """Run the examples."""
    print("TradeSense AI - Payment Domain Examples")
    print("=" * 50)

    # Run async examples
    asyncio.run(example_payment_flow())
    asyncio.run(example_idempotency())
    asyncio.run(example_error_handling())

    print("\n" + "=" * 50)
    print("Examples completed successfully!")
    print("\nNext steps:")
    print("1. Configure payment provider API keys")
    print("2. Set up webhook endpoints")
    print("3. Configure database and Redis")
    print("4. Test with real payment providers (use test mode)")
    print("5. Implement monitoring and alerting")


if __name__ == "__main__":
    main()