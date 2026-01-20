"""Trading domain value objects."""

from decimal import Decimal
from enum import Enum
from typing import Optional

from ....shared.kernel.value_object import ValueObject
from ....shared.utils.money import Money


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TimeInForce(Enum):
    """Time in force enumeration."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


class Symbol(ValueObject):
    """Trading symbol value object."""
    
    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Symbol cannot be empty")
        
        self.value = value.upper().strip()
        
        # Basic validation for common symbol formats
        if len(self.value) < 1 or len(self.value) > 20:
            raise ValueError("Symbol must be between 1 and 20 characters")
    
    def __str__(self) -> str:
        return self.value


class Quantity(ValueObject):
    """Order quantity value object."""
    
    def __init__(self, value: Decimal) -> None:
        if value <= 0:
            raise ValueError("Quantity must be positive")
        
        self.value = value.quantize(Decimal("0.00000001"))  # 8 decimal places
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __add__(self, other: "Quantity") -> "Quantity":
        return Quantity(self.value + other.value)
    
    def __sub__(self, other: "Quantity") -> "Quantity":
        result = self.value - other.value
        if result <= 0:
            raise ValueError("Quantity subtraction would result in non-positive value")
        return Quantity(result)
    
    def __mul__(self, multiplier: Decimal) -> "Quantity":
        return Quantity(self.value * multiplier)
    
    def __lt__(self, other: "Quantity") -> bool:
        return self.value < other.value
    
    def __le__(self, other: "Quantity") -> bool:
        return self.value <= other.value
    
    def __gt__(self, other: "Quantity") -> bool:
        return self.value > other.value
    
    def __ge__(self, other: "Quantity") -> bool:
        return self.value >= other.value


class Price(ValueObject):
    """Price value object."""
    
    def __init__(self, value: Money) -> None:
        if value.amount <= 0:
            raise ValueError("Price must be positive")
        
        self.value = value
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __lt__(self, other: "Price") -> bool:
        return self.value < other.value
    
    def __le__(self, other: "Price") -> bool:
        return self.value <= other.value
    
    def __gt__(self, other: "Price") -> bool:
        return self.value > other.value
    
    def __ge__(self, other: "Price") -> bool:
        return self.value >= other.value


class Fill(ValueObject):
    """Order fill value object."""
    
    def __init__(
        self,
        quantity: Quantity,
        price: Price,
        fill_id: str,
        timestamp: Optional[str] = None,
        commission: Optional[Money] = None,
    ) -> None:
        self.quantity = quantity
        self.price = price
        self.fill_id = fill_id
        self.timestamp = timestamp
        self.commission = commission or Money.zero(price.value.currency)
        
        # Calculate fill value
        self.value = Money(
            self.price.value.amount * self.quantity.value,
            self.price.value.currency
        )
        
        # Net value after commission
        self.net_value = self.value - self.commission
    
    def __str__(self) -> str:
        return f"Fill({self.quantity} @ {self.price})"


class PositionSide(Enum):
    """Position side enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeType(Enum):
    """Trade type enumeration."""
    OPEN = "OPEN"      # Opens a new position
    CLOSE = "CLOSE"    # Closes an existing position
    INCREASE = "INCREASE"  # Increases position size
    REDUCE = "REDUCE"  # Reduces position size


class PnLType(Enum):
    """P&L type enumeration."""
    REALIZED = "REALIZED"    # Closed position P&L
    UNREALIZED = "UNREALIZED"  # Open position P&L


class TradeId(ValueObject):
    """Trade identifier value object."""
    
    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Trade ID cannot be empty")
        
        self.value = value.strip()
    
    def __str__(self) -> str:
        return self.value


class PnL(ValueObject):
    """Profit and Loss value object."""
    
    def __init__(
        self,
        amount: Money,
        pnl_type: PnLType,
        currency: str,
        percentage: Optional[Decimal] = None,
    ) -> None:
        self.amount = amount
        self.pnl_type = pnl_type
        self.currency = currency
        self.percentage = percentage
    
    @property
    def is_profit(self) -> bool:
        return self.amount.amount > 0
    
    @property
    def is_loss(self) -> bool:
        return self.amount.amount < 0
    
    def __str__(self) -> str:
        sign = "+" if self.is_profit else ""
        return f"{sign}{self.amount} ({self.pnl_type.value})"
    
    def __add__(self, other: "PnL") -> "PnL":
        if self.currency != other.currency:
            raise ValueError("Cannot add P&L with different currencies")
        
        return PnL(
            amount=self.amount + other.amount,
            pnl_type=self.pnl_type,  # Keep the first type
            currency=self.currency,
        )


class Commission(ValueObject):
    """Commission value object."""
    
    def __init__(
        self,
        amount: Money,
        rate: Optional[Decimal] = None,
        commission_type: str = "FIXED",
    ) -> None:
        self.amount = amount
        self.rate = rate
        self.commission_type = commission_type
    
    def __str__(self) -> str:
        return f"Commission({self.amount})"