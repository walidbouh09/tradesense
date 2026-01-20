"""Payment domain repositories."""

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
from uuid import UUID

from .entities import Payment, Transaction, PaymentMethod
from .value_objects import IdempotencyRecord


class PaymentRepository(ABC):
    """Repository interface for Payment aggregate."""

    @abstractmethod
    async def save(self, payment: Payment) -> None:
        """Save a payment."""
        pass

    @abstractmethod
    async def find_by_id(self, payment_id: UUID) -> Optional[Payment]:
        """Find payment by ID."""
        pass

    @abstractmethod
    async def find_by_idempotency_key(self, key: str) -> Optional[Payment]:
        """Find payment by idempotency key."""
        pass

    @abstractmethod
    async def find_by_customer_id(
        self,
        customer_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Payment]:
        """Find payments by customer ID."""
        pass

    @abstractmethod
    async def find_by_provider_payment_id(self, provider_payment_id: str) -> Optional[Payment]:
        """Find payment by provider payment ID."""
        pass

    @abstractmethod
    async def update_status(self, payment_id: UUID, status: str) -> None:
        """Update payment status."""
        pass


class PaymentMethodRepository(ABC):
    """Repository interface for PaymentMethod."""

    @abstractmethod
    async def save(self, payment_method: PaymentMethod) -> None:
        """Save a payment method."""
        pass

    @abstractmethod
    async def find_by_id(self, payment_method_id: str) -> Optional[PaymentMethod]:
        """Find payment method by ID."""
        pass

    @abstractmethod
    async def find_by_customer_id(self, customer_id: UUID) -> List[PaymentMethod]:
        """Find payment methods by customer ID."""
        pass

    @abstractmethod
    async def find_default_by_customer_id(self, customer_id: UUID) -> Optional[PaymentMethod]:
        """Find default payment method for customer."""
        pass

    @abstractmethod
    async def delete(self, payment_method_id: str) -> None:
        """Delete a payment method."""
        pass

    @abstractmethod
    async def set_default(self, payment_method_id: str, customer_id: UUID) -> None:
        """Set payment method as default for customer."""
        pass


class TransactionRepository(ABC):
    """Repository interface for Transaction."""

    @abstractmethod
    async def save(self, transaction: Transaction) -> None:
        """Save a transaction."""
        pass

    @abstractmethod
    async def find_by_id(self, transaction_id: UUID) -> Optional[Transaction]:
        """Find transaction by ID."""
        pass

    @abstractmethod
    async def find_by_payment_id(self, payment_id: UUID) -> List[Transaction]:
        """Find transactions by payment ID."""
        pass

    @abstractmethod
    async def update_status(self, transaction_id: UUID, status: str) -> None:
        """Update transaction status."""
        pass


class IdempotencyRepository(ABC):
    """Repository interface for idempotency records."""

    @abstractmethod
    async def save(self, record: IdempotencyRecord) -> None:
        """Save idempotency record."""
        pass

    @abstractmethod
    async def find_by_key(self, key: str) -> Optional[IdempotencyRecord]:
        """Find idempotency record by key."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if idempotency key exists."""
        pass

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete expired idempotency records. Returns count deleted."""
        pass