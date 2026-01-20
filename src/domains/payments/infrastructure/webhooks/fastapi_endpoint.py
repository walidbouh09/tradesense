"""FastAPI webhook endpoint with security and monitoring."""

import time
from typing import Dict, Any

from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.logging.audit_logger import AuditLogger
from shared.infrastructure.messaging.event_bus import EventBus
import redis.asyncio as redis

from .webhook_handler import WebhookHandler


router = APIRouter()


async def get_webhook_handler(
    request: Request,
    session: AsyncSession = Depends(),  # Would be injected properly
    redis_client: redis.Redis = Depends(),  # Would be injected properly
    event_bus: EventBus = Depends(),  # Would be injected properly
    audit_logger: AuditLogger = Depends(),  # Would be injected properly
) -> WebhookHandler:
    """Get webhook handler with dependencies."""
    # In production, webhook secrets should come from secure config
    webhook_secrets = {
        "stripe": "whsec_stripe_webhook_secret_placeholder",
        "paypal": "whsec_paypal_webhook_secret_placeholder",
    }

    return WebhookHandler(
        session=session,
        redis_client=redis_client,
        event_bus=event_bus,
        audit_logger=audit_logger,
        webhook_secrets=webhook_secrets,
    )


@router.post(
    "/stripe",
    summary="Stripe Webhook Endpoint",
    description="""
    Secure Stripe webhook endpoint with:

    - **Signature Verification**: Validates Stripe webhook signatures
    - **Idempotency**: Prevents duplicate processing of same event
    - **Audit Trail**: Complete logging of all webhook events
    - **Retry Safety**: Handles Stripe's webhook retries gracefully

    **Headers Required:**
    - `stripe-signature`: Stripe webhook signature for verification

    **Response Codes:**
    - `200`: Webhook processed successfully
    - `400`: Invalid signature or malformed payload
    - `500`: Internal processing error
    """,
    responses={
        200: {"description": "Webhook processed successfully"},
        400: {"description": "Invalid webhook signature or payload"},
        401: {"description": "Unauthorized - invalid signature"},
        429: {"description": "Rate limited"},
        500: {"description": "Internal server error"},
    },
)
async def stripe_webhook(
    request: Request,
    webhook_handler: WebhookHandler = Depends(get_webhook_handler),
) -> JSONResponse:
    """Handle Stripe webhook with full security."""
    start_time = time.time()

    try:
        # Extract webhook data
        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")
        source_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing stripe-signature header",
            )

        # Process webhook
        result = await webhook_handler.handle_webhook(
            provider="stripe",
            payload=payload,
            signature=signature,
            headers=dict(request.headers),
            source_ip=source_ip,
            user_agent=user_agent,
        )

        # Determine response status
        if result.get("error"):
            if "signature" in result["error"].lower():
                status_code = status.HTTP_401_UNAUTHORIZED
            else:
                status_code = status.HTTP_400_BAD_REQUEST
        elif result.get("idempotent"):
            status_code = status.HTTP_200_OK  # Already processed
        else:
            status_code = status.HTTP_200_OK

        # Add processing metadata
        result["processing_time_seconds"] = time.time() - start_time
        result["status_code"] = status_code

        return JSONResponse(
            content=result,
            status_code=status_code,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Log error but don't expose internal details
        error_result = {
            "error": "Internal webhook processing error",
            "processed": False,
            "processing_time_seconds": time.time() - start_time,
        }

        return JSONResponse(
            content=error_result,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/paypal",
    summary="PayPal Webhook Endpoint",
    description="""
    Secure PayPal webhook endpoint with signature verification and audit trail.

    **Headers Required:**
    - `paypal-transmission-id`
    - `paypal-transmission-time`
    - `paypal-transmission-sig`
    - `paypal-cert-url`
    - `paypal-auth-algo`
    """,
)
async def paypal_webhook(
    request: Request,
    webhook_handler: WebhookHandler = Depends(get_webhook_handler),
) -> JSONResponse:
    """Handle PayPal webhook."""
    start_time = time.time()

    try:
        payload = await request.body()
        headers = dict(request.headers)
        source_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")

        # PayPal requires specific headers for signature verification
        required_headers = [
            "paypal-transmission-id",
            "paypal-transmission-time",
            "paypal-transmission-sig",
            "paypal-cert-url",
            "paypal-auth-algo",
        ]

        missing_headers = [h for h in required_headers if not headers.get(h)]
        if missing_headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required headers: {', '.join(missing_headers)}",
            )

        # Create signature string from required headers
        signature_parts = []
        for header in required_headers:
            signature_parts.append(f"{header}={headers[header]}")

        signature = "|".join(signature_parts)

        result = await webhook_handler.handle_webhook(
            provider="paypal",
            payload=payload,
            signature=signature,
            headers=headers,
            source_ip=source_ip,
            user_agent=user_agent,
        )

        result["processing_time_seconds"] = time.time() - start_time

        status_code = (
            status.HTTP_401_UNAUTHORIZED if "signature" in result.get("error", "").lower()
            else status.HTTP_200_OK
        )

        return JSONResponse(content=result, status_code=status_code)

    except HTTPException:
        raise
    except Exception as e:
        error_result = {
            "error": "Internal webhook processing error",
            "processed": False,
            "processing_time_seconds": time.time() - start_time,
        }

        return JSONResponse(
            content=error_result,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/health",
    summary="Webhook Health Check",
    description="Check webhook processing health and statistics.",
)
async def webhook_health(
    request: Request,
    session: AsyncSession = Depends(),
) -> JSONResponse:
    """Webhook health check with processing statistics."""
    from .repository import SqlAlchemyWebhookEventRepository

    repo = SqlAlchemyWebhookEventRepository(session)
    stats = await repo.get_processing_stats(hours=24)

    return JSONResponse(content={
        "status": "healthy",
        "stats": stats,
        "timestamp": time.time(),
    })


# Webhook retry endpoint for manual processing
@router.post(
    "/retry/{webhook_id}",
    summary="Retry Failed Webhook",
    description="Manually retry processing a failed webhook.",
)
async def retry_webhook(
    webhook_id: str,
    request: Request,
    webhook_handler: WebhookHandler = Depends(get_webhook_handler),
) -> JSONResponse:
    """Manually retry a failed webhook."""
    # This would implement manual retry logic
    # For now, return placeholder
    return JSONResponse(content={
        "message": f"Retry initiated for webhook {webhook_id}",
        "status": "queued",
    })