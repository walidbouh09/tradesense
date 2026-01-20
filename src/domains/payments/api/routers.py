"""Payment API FastAPI routers."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.messaging.event_bus import EventBus
import redis.asyncio as redis

from ..application.services import PaymentApplicationService
from ..infrastructure.repositories import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyPaymentMethodRepository,
    SqlAlchemyTransactionRepository,
    RedisIdempotencyRepository,
)
from ..domain.services import (
    PaymentValidationService,
    IdempotencyService,
    WebhookProcessingService,
)
from .schemas import (
    CreatePaymentRequest,
    PaymentResponse,
    ListPaymentsResponse,
    ConfirmPaymentRequest,
    CancelPaymentRequest,
    RefundPaymentRequest,
    CreatePaymentMethodRequest,
    PaymentMethodSchema,
    ListPaymentMethodsResponse,
    SetDefaultPaymentMethodRequest,
    ListTransactionsResponse,
    WebhookResponse,
    ErrorResponse,
)


# Create router
router = APIRouter(prefix="/payments", tags=["payments"])


# Dependencies
async def get_db_session() -> AsyncSession:
    """Get database session."""
    from shared.infrastructure.database.session import get_session
    async for session in get_session():
        yield session


async def get_redis_client() -> redis.Redis:
    """Get Redis client."""
    import redis.asyncio as redis
    client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=False)
    try:
        yield client
    finally:
        await client.close()


async def get_event_bus() -> EventBus:
    """Get event bus."""
    # Import the global event bus from main
    from ...main import event_bus
    return event_bus


def get_payment_providers():
    """Get payment providers."""
    # This should be configured properly in production
    from ...infrastructure.providers.stripe_provider import StripeProvider
    from ...infrastructure.providers.paypal_provider import PayPalProvider

    providers = {}

    # Placeholder configs - should come from environment
    try:
        providers["stripe"] = StripeProvider(
            api_key="sk_test_placeholder",
            webhook_secret="whsec_placeholder",
            base_url="https://api.stripe.com/v1",
        )
    except Exception:
        pass  # Skip if not configured

    try:
        providers["paypal"] = PayPalProvider(
            api_key="paypal_placeholder",
            webhook_secret="paypal_whsec_placeholder",
            base_url="https://api.paypal.com/v1",
        )
    except Exception:
        pass  # Skip if not configured

    return providers


async def get_payment_service(
    session: AsyncSession = Depends(get_db_session),
    redis_client: redis.Redis = Depends(get_redis_client),
    event_bus: EventBus = Depends(get_event_bus),
) -> PaymentApplicationService:
    """Get payment application service."""

    # Initialize repositories
    payment_repo = SqlAlchemyPaymentRepository(session)
    payment_method_repo = SqlAlchemyPaymentMethodRepository(session)
    transaction_repo = SqlAlchemyTransactionRepository(session)
    idempotency_repo = RedisIdempotencyRepository(redis_client)

    # Initialize services
    validation_service = PaymentValidationService()
    idempotency_service = IdempotencyService(idempotency_repo)
    webhook_service = WebhookProcessingService(get_payment_providers())

    # Create application service
    return PaymentApplicationService(
        payment_repository=payment_repo,
        payment_method_repository=payment_method_repo,
        transaction_repository=transaction_repo,
        idempotency_service=idempotency_service,
        validation_service=validation_service,
        webhook_service=webhook_service,
        providers=get_payment_providers(),
        event_bus=event_bus,
    )


# Helper functions
def payment_to_response(payment) -> PaymentResponse:
    """Convert payment entity to response schema."""
    from .schemas import MoneySchema, PaymentMethodSchema

    return PaymentResponse(
        id=payment.id,
        idempotency_key=payment.idempotency_key,
        amount=MoneySchema(amount=str(payment.amount.amount), currency=payment.amount.currency),
        fees=MoneySchema(amount=str(payment.fees.amount), currency=payment.fees.currency),
        net_amount=MoneySchema(amount=str(payment.net_amount.amount), currency=payment.net_amount.currency),
        customer_id=payment.customer_id,
        payment_method=PaymentMethodSchema(
            id=payment.payment_method.payment_method_id,
            type=payment.payment_method.type,
            provider=payment.payment_method.provider,
            is_default=payment.payment_method.is_default,
            metadata=payment.payment_method.metadata,
            expires_at=payment.payment_method.expires_at,
        ),
        status=payment.status.value,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        description=payment.description,
        metadata=payment.metadata,
        failure_reason=payment.failure_reason,
        processed_at=payment.processed_at,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
    )


def payment_method_to_response(pm) -> PaymentMethodSchema:
    """Convert payment method entity to response schema."""
    return PaymentMethodSchema(
        id=pm.payment_method_id,
        type=pm.type,
        provider=pm.provider,
        is_default=pm.is_default,
        metadata=pm.metadata,
        expires_at=pm.expires_at,
    )


# API Endpoints

@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_payment(
    request: CreatePaymentRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentResponse:
    """Create a new payment."""
    try:
        payment = await service.create_payment(
            idempotency_key=request.idempotency_key,
            amount=request.amount.to_money(),
            customer_id=request.customer_id,
            payment_method_id=request.payment_method_id,
            description=request.description,
            provider=request.provider,
            metadata=request.metadata,
            capture=request.capture,
        )
        return payment_to_response(payment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_payment(
    payment_id: UUID,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentResponse:
    """Get a payment by ID."""
    payment = await service.get_payment(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )
    return payment_to_response(payment)


@router.get(
    "",
    response_model=ListPaymentsResponse,
)
async def list_payments(
    customer_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> ListPaymentsResponse:
    """List payments with optional filters."""
    payments = await service.list_payments(
        customer_id=customer_id,
        status=status_filter,
        provider=provider,
        limit=limit,
        offset=offset,
    )

    return ListPaymentsResponse(
        payments=[payment_to_response(p) for p in payments],
        total_count=len(payments),  # This should be improved with proper pagination
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{payment_id}/confirm",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def confirm_payment(
    payment_id: UUID,
    request: ConfirmPaymentRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentResponse:
    """Confirm a payment."""
    try:
        await service.confirm_payment(payment_id)
        payment = await service.get_payment(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment {payment_id} not found",
            )
        return payment_to_response(payment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{payment_id}/cancel",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def cancel_payment(
    payment_id: UUID,
    request: CancelPaymentRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentResponse:
    """Cancel a payment."""
    try:
        await service.cancel_payment(payment_id, request.reason)
        payment = await service.get_payment(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment {payment_id} not found",
            )
        return payment_to_response(payment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def refund_payment(
    payment_id: UUID,
    request: RefundPaymentRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentResponse:
    """Refund a payment."""
    try:
        await service.refund_payment(
            payment_id=payment_id,
            amount=request.amount.to_money(),
            reason=request.reason,
        )
        payment = await service.get_payment(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment {payment_id} not found",
            )
        return payment_to_response(payment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Payment Methods API

@router.post(
    "/payment-methods",
    response_model=PaymentMethodSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
    },
)
async def create_payment_method(
    request: CreatePaymentMethodRequest,
    service: PaymentApplicationService = Depends(get_payment_service),
) -> PaymentMethodSchema:
    """Create a payment method."""
    try:
        # Note: This needs customer_id - it should come from authentication
        # For now, using a placeholder
        customer_id = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder

        payment_method = await service.create_payment_method(
            customer_id=customer_id,
            type=request.type,
            provider=request.provider,
            payment_method_data=request.payment_method_data,
        )
        return payment_method_to_response(payment_method)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/payment-methods",
    response_model=ListPaymentMethodsResponse,
)
async def list_payment_methods(
    customer_id: UUID,  # This should come from authentication
    service: PaymentApplicationService = Depends(get_payment_service),
) -> ListPaymentMethodsResponse:
    """List payment methods for a customer."""
    payment_methods = await service.list_payment_methods(customer_id)
    return ListPaymentMethodsResponse(
        payment_methods=[payment_method_to_response(pm) for pm in payment_methods]
    )


@router.post(
    "/payment-methods/{payment_method_id}/set-default",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def set_default_payment_method(
    payment_method_id: str,
    request: SetDefaultPaymentMethodRequest,
    customer_id: UUID,  # This should come from authentication
    service: PaymentApplicationService = Depends(get_payment_service),
) -> None:
    """Set a payment method as default."""
    # This would need to be implemented in the application service
    pass


# Webhook endpoint
@router.post(
    "/webhooks/{provider}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def process_webhook(
    provider: str,
    payload: bytes = Depends(lambda: None),  # Raw body
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    paypal_transmission_id: Optional[str] = Header(None, alias="paypal-transmission-id"),
    paypal_transmission_time: Optional[str] = Header(None, alias="paypal-transmission-time"),
    paypal_transmission_sig: Optional[str] = Header(None, alias="paypal-transmission-sig"),
    paypal_cert_url: Optional[str] = Header(None, alias="paypal-cert-url"),
    paypal_auth_algo: Optional[str] = Header(None, alias="paypal-auth-algo"),
    service: PaymentApplicationService = Depends(get_payment_service),
) -> WebhookResponse:
    """Process webhook from payment provider."""
    try:
        headers = {}

        if provider == "stripe" and stripe_signature:
            headers["stripe-signature"] = stripe_signature
        elif provider == "paypal":
            headers.update({
                "paypal-transmission-id": paypal_transmission_id,
                "paypal-transmission-time": paypal_transmission_time,
                "paypal-transmission-sig": paypal_transmission_sig,
                "paypal-cert-url": paypal_cert_url,
                "paypal-auth-algo": paypal_auth_algo,
            })

        await service.process_webhook(provider, payload, "", headers)
        return WebhookResponse()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # For webhooks, we should return 200 even on errors to avoid retries
        # Log the error and return success
        return WebhookResponse(
            status="error",
            message=f"Webhook processing failed: {str(e)}"
        )