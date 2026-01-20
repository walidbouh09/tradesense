"""Webhook event repository."""

from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WebhookEventModel, WebhookProcessingLog


class SqlAlchemyWebhookEventRepository:
    """Repository for webhook events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, webhook_event: WebhookEventModel) -> None:
        """Save webhook event."""
        self.session.add(webhook_event)
        await self.session.commit()

    async def find_by_id(self, webhook_id: str) -> Optional[WebhookEventModel]:
        """Find webhook event by ID."""
        result = await self.session.execute(
            select(WebhookEventModel).where(WebhookEventModel.id == webhook_id)
        )
        return result.scalar_one_or_none()

    async def find_by_event_id(self, provider: str, event_id: str) -> Optional[WebhookEventModel]:
        """Find webhook event by provider and event ID."""
        result = await self.session.execute(
            select(WebhookEventModel).where(
                and_(
                    WebhookEventModel.provider == provider,
                    WebhookEventModel.event_id == event_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def find_unprocessed(self, limit: int = 100) -> List[WebhookEventModel]:
        """Find unprocessed webhook events."""
        result = await self.session.execute(
            select(WebhookEventModel)
            .where(WebhookEventModel.processed == False)
            .order_by(WebhookEventModel.received_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def find_by_payment_id(self, payment_id: str) -> List[WebhookEventModel]:
        """Find webhook events by payment ID."""
        result = await self.session.execute(
            select(WebhookEventModel)
            .where(WebhookEventModel.payment_id == payment_id)
            .order_by(desc(WebhookEventModel.received_at))
        )
        return result.scalars().all()

    async def get_processing_stats(self, hours: int = 24) -> dict:
        """Get webhook processing statistics."""
        since = datetime.utcnow() - timedelta(hours=hours)

        # Total webhooks received
        total_result = await self.session.execute(
            select(WebhookEventModel.id).where(WebhookEventModel.received_at >= since)
        )
        total_received = len(total_result.scalars().all())

        # Processed webhooks
        processed_result = await self.session.execute(
            select(WebhookEventModel.id).where(
                and_(
                    WebhookEventModel.received_at >= since,
                    WebhookEventModel.processed == True,
                )
            )
        )
        total_processed = len(processed_result.scalars().all())

        # Failed webhooks
        failed_result = await self.session.execute(
            select(WebhookEventModel.id).where(
                and_(
                    WebhookEventModel.received_at >= since,
                    WebhookEventModel.processing_error.isnot(None),
                )
            )
        )
        total_failed = len(failed_result.scalars().all())

        return {
            "total_received": total_received,
            "total_processed": total_processed,
            "total_failed": total_failed,
            "processing_rate": total_processed / total_received if total_received > 0 else 0,
            "failure_rate": total_failed / total_received if total_received > 0 else 0,
        }

    async def cleanup_old_events(self, days_to_keep: int = 90) -> int:
        """Clean up old webhook events (for GDPR compliance)."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # In a real implementation, you'd archive events before deleting
        # For now, just count them
        result = await self.session.execute(
            select(WebhookEventModel.id).where(WebhookEventModel.received_at < cutoff_date)
        )
        old_count = len(result.scalars().all())

        # Actually delete (in production, archive first)
        # await self.session.execute(
        #     delete(WebhookEventModel).where(WebhookEventModel.received_at < cutoff_date)
        # )
        # await self.session.commit()

        return old_count