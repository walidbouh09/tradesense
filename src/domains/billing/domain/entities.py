"""Billing domain entities."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from shared.kernel.entity import AggregateRoot
from shared.kernel.events import DomainEvent
from shared.utils.money import Money


class SubscriptionStatus:
    """Subscription status value object."""

    ACTIVE = "active"
    PENDING = "pending"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PAST_DUE = "past_due"

    VALID_STATUSES = {
        ACTIVE, PENDING, CANCELLED, EXPIRED,
        SUSPENDED, PAST_DUE
    }

    def __init__(self, value: str) -> None:
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid subscription status: {value}")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SubscriptionStatus):
            return NotImplemented
        return self.value == other.value

    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.value == self.ACTIVE

    def is_terminal(self) -> bool:
        """Check if status is terminal (no further transitions)."""
        return self.value in {self.CANCELLED, self.EXPIRED}

    def can_transition_to(self, new_status: 'SubscriptionStatus') -> bool:
        """Check if transition to new status is valid."""
        transitions = {
            self.PENDING: {self.ACTIVE, self.CANCELLED},
            self.ACTIVE: {self.CANCELLED, self.SUSPENDED, self.PAST_DUE, self.EXPIRED},
            self.SUSPENDED: {self.ACTIVE, self.CANCELLED},
            self.PAST_DUE: {self.ACTIVE, self.CANCELLED, self.SUSPENDED},
            self.CANCELLED: set(),  # Terminal
            self.EXPIRED: set(),    # Terminal
        }
        return new_status.value in transitions.get(self.value, set())


class BillingCycle:
    """Billing cycle value object."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ONE_TIME = "one_time"

    VALID_CYCLES = {MONTHLY, QUARTERLY, ANNUAL, ONE_TIME}

    def __init__(self, value: str) -> None:
        if value not in self.VALID_CYCLES:
            raise ValueError(f"Invalid billing cycle: {value}")
        self.value = value

    def get_next_billing_date(self, current_date: datetime) -> datetime:
        """Calculate next billing date."""
        if self.value == self.MONTHLY:
            # Add one month
            if current_date.month == 12:
                return current_date.replace(year=current_date.year + 1, month=1)
            else:
                return current_date.replace(month=current_date.month + 1)
        elif self.value == self.QUARTERLY:
            # Add three months
            month = current_date.month + 3
            year = current_date.year
            if month > 12:
                year += 1
                month -= 12
            return current_date.replace(year=year, month=month)
        elif self.value == self.ANNUAL:
            # Add one year
            return current_date.replace(year=current_date.year + 1)
        else:  # ONE_TIME
            # No next billing date
            return current_date

    def __str__(self) -> str:
        return self.value


class SubscriptionPlan:
    """Subscription plan value object."""

    def __init__(
        self,
        plan_id: str,
        name: str,
        description: str,
        price: Money,
        billing_cycle: BillingCycle,
        features: List[str],
        is_active: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.plan_id = plan_id
        self.name = name
        self.description = description
        self.price = price
        self.billing_cycle = billing_cycle
        self.features = features
        self.is_active = is_active
        self.metadata = metadata or {}

    def is_one_time(self) -> bool:
        """Check if this is a one-time plan."""
        return self.billing_cycle.value == BillingCycle.ONE_TIME

    def is_recurring(self) -> bool:
        """Check if this is a recurring plan."""
        return not self.is_one_time()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SubscriptionPlan):
            return NotImplemented
        return self.plan_id == other.plan_id


class Subscription(AggregateRoot):
    """Subscription aggregate root."""

    def __init__(
        self,
        subscription_id: UUID,
        customer_id: UUID,
        plan: SubscriptionPlan,
        payment_method_id: str,
        start_date: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(subscription_id)
        self.customer_id = customer_id
        self.plan = plan
        self.payment_method_id = payment_method_id
        self.start_date = start_date
        self.metadata = metadata or {}

        # State
        self.status = SubscriptionStatus(SubscriptionStatus.PENDING)
        self.current_period_start = start_date
        self.current_period_end = self._calculate_period_end(start_date)
        self.cancel_at_period_end = False
        self.cancelled_at: Optional[datetime] = None

        # Financial tracking
        self.total_billed = Money(0, plan.price.currency)
        self.outstanding_balance = Money(0, plan.price.currency)

        # Audit trail
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # Invoices and payments
        self.invoices: List['Invoice'] = []

    def _calculate_period_end(self, start_date: datetime) -> datetime:
        """Calculate period end based on billing cycle."""
        return self.plan.billing_cycle.get_next_billing_date(start_date)

    def activate(self, activated_at: datetime) -> None:
        """Activate the subscription."""
        if not self.status.can_transition_to(SubscriptionStatus(SubscriptionStatus.ACTIVE)):
            raise ValueError(f"Cannot activate subscription in {self.status} state")

        old_status = self.status
        self.status = SubscriptionStatus(SubscriptionStatus.ACTIVE)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(SubscriptionActivated(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            plan_id=self.plan.plan_id,
            activated_at=activated_at,
        ))

        self.add_domain_event(SubscriptionStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

    def renew(self, renewal_date: datetime) -> None:
        """Renew the subscription for next billing period."""
        if not self.status.is_active():
            raise ValueError("Can only renew active subscriptions")

        # Update billing period
        self.current_period_start = self.current_period_end
        self.current_period_end = self._calculate_period_end(self.current_period_start)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(SubscriptionRenewed(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            renewal_date=renewal_date,
            next_billing_date=self.current_period_end,
        ))

    def cancel(self, cancel_at_period_end: bool = True, cancelled_at: Optional[datetime] = None) -> None:
        """Cancel the subscription."""
        if not self.status.can_transition_to(SubscriptionStatus(SubscriptionStatus.CANCELLED)):
            raise ValueError(f"Cannot cancel subscription in {self.status} state")

        old_status = self.status
        self.status = SubscriptionStatus(SubscriptionStatus.CANCELLED)
        self.cancel_at_period_end = cancel_at_period_end
        self.cancelled_at = cancelled_at or datetime.utcnow()
        self.updated_at = self.cancelled_at

        self.add_domain_event(SubscriptionStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(SubscriptionCancelled(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            cancelled_at=self.cancelled_at,
            cancel_at_period_end=cancel_at_period_end,
        ))

    def suspend(self, reason: str) -> None:
        """Suspend the subscription."""
        if not self.status.can_transition_to(SubscriptionStatus(SubscriptionStatus.SUSPENDED)):
            raise ValueError(f"Cannot suspend subscription in {self.status} state")

        old_status = self.status
        self.status = SubscriptionStatus(SubscriptionStatus.SUSPENDED)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(SubscriptionStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(SubscriptionSuspended(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            suspended_at=self.updated_at,
            reason=reason,
        ))

    def add_invoice(self, invoice: 'Invoice') -> None:
        """Add an invoice to this subscription."""
        self.invoices.append(invoice)
        self.total_billed += invoice.amount
        self.updated_at = datetime.utcnow()

    def update_outstanding_balance(self, new_balance: Money) -> None:
        """Update outstanding balance."""
        self.outstanding_balance = new_balance
        self.updated_at = datetime.utcnow()

    def is_due_for_renewal(self, current_date: datetime) -> bool:
        """Check if subscription is due for renewal."""
        return current_date >= self.current_period_end and self.status.is_active()

    def should_cancel_at_period_end(self) -> bool:
        """Check if subscription should be cancelled at period end."""
        return self.cancel_at_period_end and self.status.is_active()


class InvoiceStatus:
    """Invoice status value object."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"

    VALID_STATUSES = {DRAFT, OPEN, PAID, VOID, UNCOLLECTIBLE}

    def __init__(self, value: str) -> None:
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid invoice status: {value}")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def is_final(self) -> bool:
        """Check if status is final."""
        return self.value in {self.PAID, self.VOID, self.UNCOLLECTIBLE}


class InvoiceLineItem:
    """Invoice line item value object."""

    def __init__(
        self,
        description: str,
        amount: Money,
        quantity: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.description = description
        self.amount = amount
        self.quantity = quantity
        self.metadata = metadata or {}

    @property
    def total_amount(self) -> Money:
        """Calculate total amount for line item."""
        return self.amount * self.quantity


class Invoice(AggregateRoot):
    """Invoice aggregate root."""

    def __init__(
        self,
        invoice_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        currency: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(invoice_id)
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.billing_period_start = billing_period_start
        self.billing_period_end = billing_period_end
        self.currency = currency
        self.metadata = metadata or {}

        # Status and amounts
        self.status = InvoiceStatus(InvoiceStatus.DRAFT)
        self.subtotal = Money(0, currency)
        self.tax_amount = Money(0, currency)
        self.discount_amount = Money(0, currency)
        self.amount = Money(0, currency)  # Final amount after tax and discounts

        # Line items
        self.line_items: List[InvoiceLineItem] = []

        # Payment info
        self.payment_id: Optional[str] = None
        self.paid_at: Optional[datetime] = None

        # Dates
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.due_date = billing_period_end + timedelta(days=30)  # 30 days to pay

    def add_line_item(self, item: InvoiceLineItem) -> None:
        """Add a line item to the invoice."""
        if item.amount.currency != self.currency:
            raise ValueError(f"Line item currency {item.amount.currency} doesn't match invoice currency {self.currency}")

        self.line_items.append(item)
        self._recalculate_totals()

    def finalize(self) -> None:
        """Finalize the invoice for billing."""
        if self.status.value != InvoiceStatus.DRAFT:
            raise ValueError("Can only finalize draft invoices")

        if not self.line_items:
            raise ValueError("Cannot finalize invoice without line items")

        self.status = InvoiceStatus(InvoiceStatus.OPEN)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(InvoiceFinalized(
            aggregate_id=self.id,
            subscription_id=self.subscription_id,
            customer_id=self.customer_id,
            amount=self.amount,
            due_date=self.due_date,
        ))

    def mark_as_paid(self, payment_id: str, paid_at: datetime) -> None:
        """Mark invoice as paid."""
        if self.status.value not in {InvoiceStatus.DRAFT, InvoiceStatus.OPEN}:
            raise ValueError("Can only mark draft or open invoices as paid")

        old_status = self.status
        self.status = InvoiceStatus(InvoiceStatus.PAID)
        self.payment_id = payment_id
        self.paid_at = paid_at
        self.updated_at = datetime.utcnow()

        self.add_domain_event(InvoiceStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(InvoicePaid(
            aggregate_id=self.id,
            subscription_id=self.subscription_id,
            customer_id=self.customer_id,
            amount=self.amount,
            payment_id=payment_id,
            paid_at=paid_at,
        ))

    def void(self, reason: str) -> None:
        """Void the invoice."""
        if self.status.is_final():
            raise ValueError("Cannot void finalized invoices")

        old_status = self.status
        self.status = InvoiceStatus(InvoiceStatus.VOID)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(InvoiceStatusChanged(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(InvoiceVoided(
            aggregate_id=self.id,
            customer_id=self.customer_id,
            voided_at=self.updated_at,
            reason=reason,
        ))

    def _recalculate_totals(self) -> None:
        """Recalculate invoice totals."""
        # Calculate subtotal
        self.subtotal = Money(0, self.currency)
        for item in self.line_items:
            self.subtotal += item.total_amount

        # For now, no tax or discount calculation
        # In production, this would involve tax rules and discount codes
        self.amount = self.subtotal

    def is_overdue(self, current_date: datetime) -> bool:
        """Check if invoice is overdue."""
        return current_date > self.due_date and self.status.value == InvoiceStatus.OPEN


class PayoutStatus:
    """Payout status value object."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    VALID_STATUSES = {PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED}

    def __init__(self, value: str) -> None:
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid payout status: {value}")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def is_final(self) -> bool:
        """Check if status is final."""
        return self.value in {self.COMPLETED, self.FAILED, self.CANCELLED}


class Payout(AggregateRoot):
    """Payout aggregate root for profit distributions."""

    def __init__(
        self,
        payout_id: UUID,
        trader_id: UUID,
        amount: Money,
        profit_source: str,  # e.g., "challenge_completion", "monthly_profit"
        period_start: datetime,
        period_end: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(payout_id)
        self.trader_id = trader_id
        self.amount = amount
        self.profit_source = profit_source
        self.period_start = period_start
        self.period_end = period_end
        self.metadata = metadata or {}

        # Status
        self.status = PayoutStatus(PayoutStatus.PENDING)
        self.processing_fee = Money(0, amount.currency)  # Platform fee deducted
        self.net_amount = amount  # Amount actually paid to trader

        # Payment details
        self.payment_id: Optional[str] = None
        self.external_reference: Optional[str] = None
        self.processed_at: Optional[datetime] = None
        self.failure_reason: Optional[str] = None

        # Audit
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def start_processing(self) -> None:
        """Start payout processing."""
        if self.status.value != PayoutStatus.PENDING:
            raise ValueError("Can only start processing pending payouts")

        old_status = self.status
        self.status = PayoutStatus(PayoutStatus.PROCESSING)
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PayoutStatusChanged(
            aggregate_id=self.id,
            trader_id=self.trader_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

    def complete(self, payment_id: str, external_reference: str, processed_at: datetime) -> None:
        """Mark payout as completed."""
        if self.status.value != PayoutStatus.PROCESSING:
            raise ValueError("Can only complete processing payouts")

        old_status = self.status
        self.status = PayoutStatus(PayoutStatus.COMPLETED)
        self.payment_id = payment_id
        self.external_reference = external_reference
        self.processed_at = processed_at
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PayoutStatusChanged(
            aggregate_id=self.id,
            trader_id=self.trader_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(PayoutCompleted(
            aggregate_id=self.id,
            trader_id=self.trader_id,
            amount=self.net_amount,
            payment_id=payment_id,
            processed_at=processed_at,
            profit_source=self.profit_source,
        ))

    def fail(self, reason: str) -> None:
        """Mark payout as failed."""
        if self.status.is_final():
            raise ValueError("Cannot fail finalized payouts")

        old_status = self.status
        self.status = PayoutStatus(PayoutStatus.FAILED)
        self.failure_reason = reason
        self.updated_at = datetime.utcnow()

        self.add_domain_event(PayoutStatusChanged(
            aggregate_id=self.id,
            trader_id=self.trader_id,
            old_status=str(old_status),
            new_status=str(self.status),
            changed_at=self.updated_at,
        ))

        self.add_domain_event(PayoutFailed(
            aggregate_id=self.id,
            trader_id=self.trader_id,
            amount=self.net_amount,
            failure_reason=reason,
            failed_at=self.updated_at,
        ))

    def calculate_fees(self, platform_fee_percent: Decimal) -> None:
        """Calculate platform fees for this payout."""
        fee_amount = self.amount * (platform_fee_percent / Decimal(100))
        self.processing_fee = fee_amount
        self.net_amount = self.amount - fee_amount


# Domain Events
class SubscriptionActivated(DomainEvent):
    """Event emitted when subscription is activated."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        plan_id: str,
        activated_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.plan_id = plan_id
        self.activated_at = activated_at


class SubscriptionRenewed(DomainEvent):
    """Event emitted when subscription is renewed."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        renewal_date: datetime,
        next_billing_date: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.renewal_date = renewal_date
        self.next_billing_date = next_billing_date


class SubscriptionCancelled(DomainEvent):
    """Event emitted when subscription is cancelled."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        cancelled_at: datetime,
        cancel_at_period_end: bool,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.cancelled_at = cancelled_at
        self.cancel_at_period_end = cancel_at_period_end


class SubscriptionSuspended(DomainEvent):
    """Event emitted when subscription is suspended."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        suspended_at: datetime,
        reason: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.suspended_at = suspended_at
        self.reason = reason


class SubscriptionStatusChanged(DomainEvent):
    """Event emitted when subscription status changes."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        old_status: str,
        new_status: str,
        changed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_at = changed_at


class InvoiceFinalized(DomainEvent):
    """Event emitted when invoice is finalized."""

    def __init__(
        self,
        aggregate_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        amount: Money,
        due_date: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.amount = amount
        self.due_date = due_date


class InvoicePaid(DomainEvent):
    """Event emitted when invoice is paid."""

    def __init__(
        self,
        aggregate_id: UUID,
        subscription_id: UUID,
        customer_id: UUID,
        amount: Money,
        payment_id: str,
        paid_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.subscription_id = subscription_id
        self.customer_id = customer_id
        self.amount = amount
        self.payment_id = payment_id
        self.paid_at = paid_at


class InvoiceVoided(DomainEvent):
    """Event emitted when invoice is voided."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        voided_at: datetime,
        reason: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.voided_at = voided_at
        self.reason = reason


class InvoiceStatusChanged(DomainEvent):
    """Event emitted when invoice status changes."""

    def __init__(
        self,
        aggregate_id: UUID,
        customer_id: UUID,
        old_status: str,
        new_status: str,
        changed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.customer_id = customer_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_at = changed_at


class PayoutCompleted(DomainEvent):
    """Event emitted when payout is completed."""

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        amount: Money,
        payment_id: str,
        processed_at: datetime,
        profit_source: str,
    ) -> None:
        super().__init__(aggregate_id)
        self.trader_id = trader_id
        self.amount = amount
        self.payment_id = payment_id
        self.processed_at = processed_at
        self.profit_source = profit_source


class PayoutFailed(DomainEvent):
    """Event emitted when payout fails."""

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        amount: Money,
        failure_reason: str,
        failed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.trader_id = trader_id
        self.amount = amount
        self.failure_reason = failure_reason
        self.failed_at = failed_at


class PayoutStatusChanged(DomainEvent):
    """Event emitted when payout status changes."""

    def __init__(
        self,
        aggregate_id: UUID,
        trader_id: UUID,
        old_status: str,
        new_status: str,
        changed_at: datetime,
    ) -> None:
        super().__init__(aggregate_id)
        self.trader_id = trader_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_at = changed_at