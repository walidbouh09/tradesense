"""Payment infrastructure repositories."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, update, delete, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.money import Money

from ..domain.entities import Payment, PaymentMethod, Transaction, TransactionType, TransactionStatus
from ..domain.repositories import PaymentRepository, PaymentMethodRepository, TransactionRepository, IdempotencyRepository
from ..domain.value_objects import IdempotencyRecord
from .models import PaymentModel, PaymentMethodModel, TransactionModel, IdempotencyRecordModel


class SqlAlchemyPaymentRepository(PaymentRepository):
    """SQLAlchemy implementation of PaymentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, payment: Payment) -> None:
        """Save a payment."""
        # Convert domain entity to model
        model = PaymentModel(
            id=payment.id,
            idempotency_key=payment.idempotency_key,
            amount=float(payment.amount.amount),
            currency=payment.amount.currency,
            fees=float(payment.fees.amount),
            net_amount=float(payment.net_amount.amount),
            customer_id=payment.customer_id,
            payment_method_id=payment.payment_method.payment_method_id,
            status=payment.status.value,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            description=payment.description,
            metadata_=payment.metadata,
            failure_reason=payment.failure_reason,
            processed_at=payment.processed_at,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )

        # Add or update
        existing = await self.session.get(PaymentModel, payment.id)
        if existing:
            # Update existing
            for key, value in model.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing, key, value)
        else:
            self.session.add(model)

        await self.session.commit()

    async def find_by_id(self, payment_id: UUID) -> Optional[Payment]:
        """Find payment by ID."""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return await self._model_to_entity(model)

    async def find_by_idempotency_key(self, key: str) -> Optional[Payment]:
        """Find payment by idempotency key."""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.idempotency_key == key)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return await self._model_to_entity(model)

    async def find_by_customer_id(
        self,
        customer_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Payment]:
        """Find payments by customer ID."""
        result = await self.session.execute(
            select(PaymentModel)
            .where(PaymentModel.customer_id == customer_id)
            .order_by(desc(PaymentModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        models = result.scalars().all()
        payments = []
        for model in models:
            payment = await self._model_to_entity(model)
            if payment:
                payments.append(payment)
        return payments

    async def find_by_provider_payment_id(self, provider_payment_id: str) -> Optional[Payment]:
        """Find payment by provider payment ID."""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.provider_payment_id == provider_payment_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return await self._model_to_entity(model)

    async def update_status(self, payment_id: UUID, status: str) -> None:
        """Update payment status."""
        await self.session.execute(
            update(PaymentModel)
            .where(PaymentModel.id == payment_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.commit()

    async def _model_to_entity(self, model: PaymentModel) -> Payment:
        """Convert model to domain entity."""
        # Get payment method
        payment_method_result = await self.session.execute(
            select(PaymentMethodModel).where(PaymentMethodModel.payment_method_id == model.payment_method_id)
        )
        payment_method_model = payment_method_result.scalar_one_or_none()
        if not payment_method_model:
            raise ValueError(f"Payment method {model.payment_method_id} not found")

        from ..domain.entities import PaymentStatus
        payment_method = PaymentMethod(
            payment_method_id=payment_method_model.payment_method_id,
            type=payment_method_model.type,
            provider=payment_method_model.provider,
            is_default=payment_method_model.is_default,
            metadata=payment_method_model.metadata_,
            expires_at=payment_method_model.expires_at,
        )

        # Create payment entity
        payment = Payment(
            payment_id=model.id,
            idempotency_key=model.idempotency_key,
            amount=Money(model.amount, model.currency),
            customer_id=model.customer_id,
            payment_method=payment_method,
            description=model.description,
            provider=model.provider,
            metadata=model.metadata_,
        )

        # Set state
        payment.status = PaymentStatus(model.status)
        payment.provider_payment_id = model.provider_payment_id
        payment.failure_reason = model.failure_reason
        payment.processed_at = model.processed_at
        payment.created_at = model.created_at
        payment.updated_at = model.updated_at
        payment.fees = Money(model.fees, model.currency)
        payment.net_amount = Money(model.net_amount, model.currency)

        # Load transactions
        transaction_result = await self.session.execute(
            select(TransactionModel).where(TransactionModel.payment_id == model.id)
        )
        transaction_models = transaction_result.scalars().all()

        for tx_model in transaction_models:
            transaction = Transaction(
                transaction_id=tx_model.id,
                payment_id=tx_model.payment_id,
                type=tx_model.type,
                amount=Money(tx_model.amount, tx_model.currency),
                status=tx_model.status,
                provider_transaction_id=tx_model.provider_transaction_id,
                metadata=tx_model.metadata_,
            )
            transaction.processed_at = tx_model.processed_at
            payment.transactions.append(transaction)

        return payment


class SqlAlchemyPaymentMethodRepository(PaymentMethodRepository):
    """SQLAlchemy implementation of PaymentMethodRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, payment_method: PaymentMethod) -> None:
        """Save a payment method."""
        # Note: This repository method needs customer_id passed separately
        # For now, we'll use a temporary approach
        model = PaymentMethodModel(
            payment_method_id=payment_method.payment_method_id,
            customer_id=UUID("00000000-0000-0000-0000-000000000000"),  # This should be passed in
            type=payment_method.type,
            provider=payment_method.provider,
            is_default=payment_method.is_default,
            metadata_=payment_method.metadata,
            expires_at=payment_method.expires_at,
        )

        # Add or update
        existing = await self.session.get(PaymentMethodModel, payment_method.payment_method_id)
        if existing:
            for key, value in model.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing, key, value)
        else:
            self.session.add(model)

        await self.session.commit()

    async def find_by_id(self, payment_method_id: str) -> Optional[PaymentMethod]:
        """Find payment method by ID."""
        result = await self.session.execute(
            select(PaymentMethodModel).where(PaymentMethodModel.payment_method_id == payment_method_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return PaymentMethod(
            payment_method_id=model.payment_method_id,
            type=model.type,
            provider=model.provider,
            is_default=model.is_default,
            metadata=model.metadata_,
            expires_at=model.expires_at,
        )

    async def find_by_customer_id(self, customer_id: UUID) -> List[PaymentMethod]:
        """Find payment methods by customer ID."""
        result = await self.session.execute(
            select(PaymentMethodModel)
            .where(and_(PaymentMethodModel.customer_id == customer_id, PaymentMethodModel.is_active == True))
            .order_by(desc(PaymentMethodModel.created_at))
        )
        models = result.scalars().all()

        return [
            PaymentMethod(
                payment_method_id=model.payment_method_id,
                type=model.type,
                provider=model.provider,
                is_default=model.is_default,
                metadata=model.metadata_,
                expires_at=model.expires_at,
            )
            for model in models
        ]

    async def find_default_by_customer_id(self, customer_id: UUID) -> Optional[PaymentMethod]:
        """Find default payment method for customer."""
        result = await self.session.execute(
            select(PaymentMethodModel).where(
                and_(
                    PaymentMethodModel.customer_id == customer_id,
                    PaymentMethodModel.is_default == True,
                    PaymentMethodModel.is_active == True,
                )
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return PaymentMethod(
            payment_method_id=model.payment_method_id,
            type=model.type,
            provider=model.provider,
            is_default=model.is_default,
            metadata=model.metadata_,
            expires_at=model.expires_at,
        )

    async def delete(self, payment_method_id: str) -> None:
        """Delete a payment method."""
        await self.session.execute(
            update(PaymentMethodModel)
            .where(PaymentMethodModel.payment_method_id == payment_method_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await self.session.commit()

    async def set_default(self, payment_method_id: str, customer_id: UUID) -> None:
        """Set payment method as default for customer."""
        # First, unset all default flags for this customer
        await self.session.execute(
            update(PaymentMethodModel)
            .where(PaymentMethodModel.customer_id == customer_id)
            .values(is_default=False, updated_at=datetime.utcnow())
        )

        # Then set the specified payment method as default
        await self.session.execute(
            update(PaymentMethodModel)
            .where(PaymentMethodModel.payment_method_id == payment_method_id)
            .values(is_default=True, updated_at=datetime.utcnow())
        )

        await self.session.commit()


class SqlAlchemyTransactionRepository(TransactionRepository):
    """SQLAlchemy implementation of TransactionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, transaction: Transaction) -> None:
        """Save a transaction."""
        model = TransactionModel(
            id=transaction.transaction_id,
            payment_id=transaction.payment_id,
            type=transaction.type,
            amount=float(transaction.amount.amount),
            currency=transaction.amount.currency,
            status=transaction.status,
            provider_transaction_id=transaction.provider_transaction_id,
            metadata_=transaction.metadata,
            processed_at=transaction.processed_at,
            created_at=transaction.created_at,
        )

        # Add or update
        existing = await self.session.get(TransactionModel, transaction.transaction_id)
        if existing:
            for key, value in model.__dict__.items():
                if not key.startswith('_'):
                    setattr(existing, key, value)
        else:
            self.session.add(model)

        await self.session.commit()

    async def find_by_id(self, transaction_id: UUID) -> Optional[Transaction]:
        """Find transaction by ID."""
        result = await self.session.execute(
            select(TransactionModel).where(TransactionModel.id == transaction_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        return Transaction(
            transaction_id=model.id,
            payment_id=model.payment_id,
            type=model.type,
            amount=Money(model.amount, model.currency),
            status=model.status,
            provider_transaction_id=model.provider_transaction_id,
            metadata=model.metadata_,
        )

    async def find_by_payment_id(self, payment_id: UUID) -> List[Transaction]:
        """Find transactions by payment ID."""
        result = await self.session.execute(
            select(TransactionModel)
            .where(TransactionModel.payment_id == payment_id)
            .order_by(desc(TransactionModel.created_at))
        )
        models = result.scalars().all()

        return [
            Transaction(
                transaction_id=model.id,
                payment_id=model.payment_id,
                type=model.type,
                amount=Money(model.amount, model.currency),
                status=model.status,
                provider_transaction_id=model.provider_transaction_id,
                metadata=model.metadata_,
            )
            for model in models
        ]

    async def update_status(self, transaction_id: UUID, status: str) -> None:
        """Update transaction status."""
        await self.session.execute(
            update(TransactionModel)
            .where(TransactionModel.id == transaction_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.commit()


class RedisIdempotencyRepository(IdempotencyRepository):
    """Redis implementation of IdempotencyRepository."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def save(self, record: IdempotencyRecord) -> None:
        """Save idempotency record."""
        await self.redis.setex(
            f"idempotency:{record.key}",
            int(record.expires_at),
            str(record.result),
        )

    async def find_by_key(self, key: str) -> Optional[IdempotencyRecord]:
        """Find idempotency record by key."""
        result = await self.redis.get(f"idempotency:{key}")
        if not result:
            return None

        import json
        try:
            result_data = json.loads(result)
            return IdempotencyRecord(
                key=key,
                result=result_data,
                expires_at=float(await self.redis.ttl(f"idempotency:{key}")),
            )
        except (json.JSONDecodeError, ValueError):
            return None

    async def exists(self, key: str) -> bool:
        """Check if idempotency key exists."""
        return await self.redis.exists(f"idempotency:{key}") == 1

    async def delete_expired(self) -> int:
        """Delete expired idempotency records. Redis handles this automatically."""
        # Redis automatically expires keys, so we don't need to do anything
        return 0