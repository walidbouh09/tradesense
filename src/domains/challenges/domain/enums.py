"""Domain enums for Challenge Engine."""

from enum import Enum


class ChallengeStatus(Enum):
    """Challenge lifecycle states."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    FUNDED = "FUNDED"

    def is_terminal(self) -> bool:
        """Check if this status represents a terminal state."""
        return self in {self.FAILED, self.FUNDED}

    def can_transition_to(self, new_status: 'ChallengeStatus') -> bool:
        """Validate state transitions."""
        valid_transitions = {
            ChallengeStatus.PENDING: {ChallengeStatus.ACTIVE},
            ChallengeStatus.ACTIVE: {ChallengeStatus.FAILED, ChallengeStatus.FUNDED},
            ChallengeStatus.FAILED: set(),  # Terminal
            ChallengeStatus.FUNDED: set(),  # Terminal
        }
        return new_status in valid_transitions.get(self, set())