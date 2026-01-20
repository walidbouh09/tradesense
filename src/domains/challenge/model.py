"""
SQLAlchemy model for Challenge entity.

This model handles only persistence concerns. No business logic is included.
All monetary fields use Numeric for precision. All timestamps are UTC timezone-aware.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, Numeric, String, TIMESTAMP, Integer, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ENUM as PGENUM
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class ChallengeStatus:
    """Challenge status enumeration values."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    FUNDED = "FUNDED"


# Create PostgreSQL enum type for challenge status
challenge_status_enum = PGENUM(
    ChallengeStatus.PENDING,
    ChallengeStatus.ACTIVE,
    ChallengeStatus.FAILED,
    ChallengeStatus.FUNDED,
    name="challenge_status_enum",
    create_type=True
)


class Challenge(Base):
    """
    SQLAlchemy model for Challenge entity.

    Maps to the challenges table in PostgreSQL.
    Contains only persistence fields and constraints - no business logic.
    """
    __tablename__ = "challenges"

    # Primary identity
    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Foreign key relationship
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Challenge configuration (immutable after creation)
    challenge_type = Column(String(50), nullable=False)
    initial_balance = Column(Numeric(15, 2), nullable=False)
    max_daily_drawdown_percent = Column(Numeric(5, 2), nullable=False)
    max_total_drawdown_percent = Column(Numeric(5, 2), nullable=False)
    profit_target_percent = Column(Numeric(5, 2), nullable=False)

    # Dynamic equity tracking
    current_equity = Column(Numeric(15, 2), nullable=False)
    max_equity_ever = Column(Numeric(15, 2), nullable=False)

    # Daily tracking
    daily_start_equity = Column(Numeric(15, 2), nullable=False)
    daily_max_equity = Column(Numeric(15, 2), nullable=False)
    daily_min_equity = Column(Numeric(15, 2), nullable=False)
    current_date = Column(TIMESTAMP(timezone=True), nullable=False)

    # Performance tracking
    total_trades = Column(Integer, nullable=False, default=0)
    total_pnl = Column(Numeric(15, 2), nullable=False, default=Decimal('0'))

    # Lifecycle status
    status = Column(challenge_status_enum, nullable=False, default=ChallengeStatus.PENDING, index=True)

    # Time tracking
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_trade_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Rule violation tracking
    failure_reason = Column(String(100), nullable=True)
    funded_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Optimistic locking
    version = Column(Integer, nullable=False, default=1)

    # Relationships (lazy-loaded by default for performance)
    user = relationship("User", back_populates="challenges")

    # Database constraints
    __table_args__ = (
        # Business rule constraints
        CheckConstraint("initial_balance > 0", name="chk_initial_balance_positive"),
        CheckConstraint("current_equity >= 0", name="chk_current_equity_non_negative"),
        CheckConstraint("max_equity_ever >= initial_balance", name="chk_max_equity_consistency"),
        CheckConstraint("max_daily_drawdown_percent BETWEEN 0 AND 100", name="chk_max_daily_drawdown_range"),
        CheckConstraint("max_total_drawdown_percent BETWEEN 0 AND 100", name="chk_max_total_drawdown_range"),
        CheckConstraint("profit_target_percent BETWEEN 0 AND 100", name="chk_profit_target_range"),
        CheckConstraint("total_trades >= 0", name="chk_total_trades_non_negative"),
        CheckConstraint("daily_start_equity >= 0", name="chk_daily_start_equity_positive"),
        CheckConstraint("daily_max_equity >= 0", name="chk_daily_max_equity_positive"),
        CheckConstraint("daily_min_equity >= 0", name="chk_daily_min_equity_positive"),

        # Status consistency constraints
        CheckConstraint("""
            (status IN ('FAILED', 'FUNDED') AND ended_at IS NOT NULL) OR
            (status NOT IN ('FAILED', 'FUNDED') AND ended_at IS NULL)
        """, name="chk_terminal_states_complete"),

        CheckConstraint("""
            (status = 'FUNDED' AND funded_at IS NOT NULL) OR
            (status != 'FUNDED' AND funded_at IS NULL)
        """, name="chk_funded_at_only_funded"),

        # Daily equity bounds
        CheckConstraint("daily_min_equity <= daily_max_equity", name="chk_daily_equity_bounds"),

        # Time ordering
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="chk_ended_after_started"),
        CheckConstraint("last_trade_at IS NULL OR last_trade_at >= started_at", name="chk_last_trade_after_started"),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Challenge(id={self.id}, user_id={self.user_id}, status={self.status}, current_equity={self.current_equity})>"