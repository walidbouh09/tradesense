"""
Domain Exceptions for Challenge Engine.

These exceptions represent business rule violations and invalid operations.
They are part of the domain model and should be caught at the application layer.
"""


class ChallengeDomainException(Exception):
    """Base exception for challenge domain errors."""

    def __init__(self, message: str, challenge_id: str = None):
        self.challenge_id = challenge_id
        self.message = message
        super().__init__(f"Challenge {challenge_id}: {message}" if challenge_id else message)


class InvalidChallengeStateException(ChallengeDomainException):
    """
    Exception raised when operation attempted on challenge in invalid state.

    Examples:
    - Processing trade on FAILED challenge
    - Processing trade on FUNDED challenge
    - Attempting to activate already ACTIVE challenge
    """
    pass


class ConcurrentTradeException(ChallengeDomainException):
    """
    Exception raised when concurrent trades detected.

    This prevents race conditions where multiple trades
    with identical timestamps could cause inconsistent state.
    """
    pass


class InvalidTradeDataException(ChallengeDomainException):
    """
    Exception raised when trade data violates business rules.

    Examples:
    - P&L would cause equity to go negative (beyond floor)
    - Invalid timestamps
    - Missing required trade information
    """
    pass


class ChallengeInvariantViolationException(ChallengeDomainException):
    """
    Exception raised when challenge invariants are violated.

    These are serious errors indicating corrupted state.
    """
    pass