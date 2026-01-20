"""Domain value objects for Challenge Engine."""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Union
from uuid import UUID

from shared.kernel.value_object import ValueObject


class Money(ValueObject):
    """Money value object with currency safety."""

    def __init__(self, amount: Union[Decimal, str, int, float], currency: str = "USD"):
        if isinstance(amount, float):
            raise ValueError("Float amounts not allowed - use Decimal")

        self._amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self._currency = currency.upper()

        # Validation
        if self._currency not in {"USD", "EUR", "GBP"}:
            raise ValueError(f"Unsupported currency: {self._currency}")

    @property
    def amount(self) -> Decimal:
        """Get the monetary amount."""
        return self._amount

    @property
    def currency(self) -> str:
        """Get the currency code."""
        return self._currency

    def __add__(self, other: 'Money') -> 'Money':
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot add different currencies: {self.currency} vs {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot subtract different currencies: {self.currency} vs {other.currency}")
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, other: Union[Decimal, int]) -> 'Money':
        if not isinstance(other, (Decimal, int)):
            return NotImplemented
        return Money(self.amount * Decimal(str(other)), self.currency)

    def __truediv__(self, other: Union[Decimal, int]) -> 'Money':
        if not isinstance(other, (Decimal, int)):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("Division by zero")
        return Money(self.amount / Decimal(str(other)), self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other: 'Money') -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount < other.amount

    def __le__(self, other: 'Money') -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount <= other.amount

    def __gt__(self, other: 'Money') -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount > other.amount

    def __ge__(self, other: 'Money') -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if other.currency != self.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} vs {other.currency}")
        return self.amount >= other.amount

    def __repr__(self) -> str:
        return f"Money({self.amount}, '{self.currency}')"


class Percentage(ValueObject):
    """Percentage value object validated 0-100."""

    def __init__(self, value: Union[Decimal, str, int, float]):
        if isinstance(value, float):
            raise ValueError("Float values not allowed - use Decimal")

        self._value = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

        # Validation: 0-100 inclusive
        if not (Decimal('0') <= self._value <= Decimal('100')):
            raise ValueError(f"Percentage must be between 0 and 100: {self._value}")

    @property
    def value(self) -> Decimal:
        """Get the percentage value."""
        return self._value

    @property
    def decimal(self) -> Decimal:
        """Get the decimal representation (e.g., 5.5% = 0.055)."""
        return self._value / Decimal('100')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.value == other.value

    def __lt__(self, other: 'Percentage') -> bool:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: 'Percentage') -> bool:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: 'Percentage') -> bool:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: 'Percentage') -> bool:
        if not isinstance(other, Percentage):
            return NotImplemented
        return self.value >= other.value

    def __repr__(self) -> str:
        return f"Percentage({self.value})"


class PnL(ValueObject):
    """Profit and Loss value object - signed money."""

    def __init__(self, amount: Money):
        self._amount = amount

    @property
    def amount(self) -> Money:
        """Get the P&L amount."""
        return self._amount

    @property
    def currency(self) -> str:
        """Get the currency."""
        return self._amount.currency

    @property
    def is_profit(self) -> bool:
        """Check if this represents a profit."""
        return self._amount.amount > 0

    @property
    def is_loss(self) -> bool:
        """Check if this represents a loss."""
        return self._amount.amount < 0

    @property
    def is_breakeven(self) -> bool:
        """Check if this is breakeven."""
        return self._amount.amount == 0

    def __add__(self, other: 'PnL') -> 'PnL':
        if not isinstance(other, PnL):
            return NotImplemented
        return PnL(self.amount + other.amount)

    def __sub__(self, other: 'PnL') -> 'PnL':
        if not isinstance(other, PnL):
            return NotImplemented
        return PnL(self.amount - other.amount)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PnL):
            return NotImplemented
        return self.amount == other.amount

    def __repr__(self) -> str:
        return f"PnL({self.amount})"


class ChallengeId(ValueObject):
    """Challenge identifier value object - UUID wrapper."""

    def __init__(self, value: Union[str, UUID]):
        if isinstance(value, str):
            self._value = UUID(value)
        elif isinstance(value, UUID):
            self._value = value
        else:
            raise ValueError(f"ChallengeId must be string or UUID, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Get the UUID value."""
        return self._value

    def __str__(self) -> str:
        """String representation of the UUID."""
        return str(self._value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChallengeId):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash(self._value)

    def __repr__(self) -> str:
        return f"ChallengeId('{self._value}')"