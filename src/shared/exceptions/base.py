"""Base exception hierarchy for the application."""


class TradeSenseError(Exception):
    """Base exception for all TradeSense errors."""
    pass


class DomainError(TradeSenseError):
    """Base exception for domain-related errors."""
    pass


class ApplicationError(TradeSenseError):
    """Base exception for application layer errors."""
    pass


class InfrastructureError(TradeSenseError):
    """Base exception for infrastructure-related errors."""
    pass


class ValidationError(DomainError):
    """Raised when domain validation fails."""
    pass


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""
    pass


class EntityNotFoundError(ApplicationError):
    """Raised when an entity is not found."""
    
    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(f"{entity_type} with ID {entity_id} not found")
        self.entity_type = entity_type
        self.entity_id = entity_id


class ConcurrencyError(ApplicationError):
    """Raised when a concurrency conflict occurs."""
    pass