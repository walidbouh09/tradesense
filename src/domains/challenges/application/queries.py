"""
Application Queries for Challenge Engine.

Queries represent read operations with filtering and pagination.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from shared.kernel.queries import Query


@dataclass
class GetChallengeDetails(Query):
    """Query to get detailed challenge information."""

    challenge_id: str

    @property
    def result_type(self) -> str:
        return "ChallengeDetails"


@dataclass
class GetChallengesByTrader(Query):
    """Query to get all challenges for a trader."""

    trader_id: str
    status_filter: Optional[str] = None  # ACTIVE, FAILED, FUNDED, or None for all
    limit: int = 50
    offset: int = 0

    @property
    def result_type(self) -> str:
        return "List[ChallengeSummary]"

    def __post_init__(self):
        if self.status_filter and self.status_filter not in {"ACTIVE", "FAILED", "FUNDED"}:
            raise ValueError(f"Invalid status_filter: {self.status_filter}")


@dataclass
class GetChallengePerformanceMetrics(Query):
    """Query to get performance metrics for a challenge."""

    challenge_id: str

    @property
    def result_type(self) -> str:
        return "ChallengePerformanceMetrics"


@dataclass
class GetChallengesByDateRange(Query):
    """Query to get challenges within a date range."""

    start_date: datetime
    end_date: datetime
    status_filter: Optional[str] = None
    limit: int = 100
    offset: int = 0

    @property
    def result_type(self) -> str:
        return "List[ChallengeSummary]"

    def __post_init__(self):
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")


@dataclass
class GetChallengeRiskMetrics(Query):
    """Query to get risk metrics for analysis."""

    challenge_id: str

    @property
    def result_type(self) -> str:
        return "ChallengeRiskMetrics"