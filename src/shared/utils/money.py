"""Money value object for financial calculations."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

from ..kernel.value_object import ValueObject


class Money(ValueObject):
    """Money value object with currency and precise decimal arithmetic."""
    
    def __init__(self, amount: Union[str, int, float, Decimal], currency: str = "USD") -> None:
        if isinstance(amount, float):
            # Convert float to string to avoid precision issues
            amount = str(amount)
        
        self.amount = Decimal(str(amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.currency = currency.upper()
        
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
    
    def __add__(self, other: "Money") -> "Money":
        self._check_currency_compatibility(other)
        return Money(self.amount + other.amount, self.currency)
    
    def __sub__(self, other: "Money") -> "Money":
        self._check_currency_compatibility(other)
        result_amount = self.amount - other.amount
        if result_amount < 0:
            raise ValueError("Subtraction would result in negative money")
        return Money(result_amount, self.currency)
    
    def __mul__(self, multiplier: Union[int, float, Decimal]) -> "Money":
        return Money(self.amount * Decimal(str(multiplier)), self.currency)
    
    def __truediv__(self, divisor: Union[int, float, Decimal]) -> "Money":
        if divisor == 0:
            raise ValueError("Cannot divide money by zero")
        return Money(self.amount / Decimal(str(divisor)), self.currency)
    
    def __lt__(self, other: "Money") -> bool:
        self._check_currency_compatibility(other)
        return self.amount < other.amount
    
    def __le__(self, other: "Money") -> bool:
        self._check_currency_compatibility(other)
        return self.amount <= other.amount
    
    def __gt__(self, other: "Money") -> bool:
        self._check_currency_compatibility(other)
        return self.amount > other.amount
    
    def __ge__(self, other: "Money") -> bool:
        self._check_currency_compatibility(other)
        return self.amount >= other.amount
    
    def _check_currency_compatibility(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(f"Cannot operate on different currencies: {self.currency} vs {other.currency}")
    
    def to_float(self) -> float:
        """Convert to float (use with caution in financial calculations)."""
        return float(self.amount)
    
    def to_decimal(self) -> Decimal:
        """Get the decimal amount."""
        return self.amount
    
    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
    
    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Create zero money."""
        return cls(0, currency)