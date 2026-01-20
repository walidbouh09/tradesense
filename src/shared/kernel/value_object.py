"""Base value object abstraction."""

from abc import ABC
from typing import Any


class ValueObject(ABC):
    """Base value object - immutable and compared by value."""
    
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"