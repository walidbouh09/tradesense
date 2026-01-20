"""
SQLAlchemy Model for Risk Scores

Persistence layer for adaptive risk scoring results.
Append-only storage with complete audit trail.
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer, Text, JSON, BigInteger, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class RiskLevel(enum.Enum):
    """Risk severity levels matching application logic."""
    STABLE = "STABLE"
    MONITOR = "MONITOR"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"


class RiskScore(Base):
    """
    Risk Score Model - Adaptive Risk Assessment Results

    Stores complete risk scoring results with detailed breakdowns
    for audit, explainability, and future ML training.
    """
    __tablename__ = 'risk_scores'

    # Primary identity
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Assessment context
    challenge_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Risk score result
    risk_score = Column(Numeric(5, 2), nullable=False)
    risk_level = Column(String(20), nullable=False)

    # Score breakdown for explainability
    score_breakdown = Column(JSON, nullable=False)

    # Feature summary (snapshot for reproducibility)
    feature_summary = Column(JSON, nullable=False)

    # Assessment metadata
    assessed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assessment_version = Column(String(50), nullable=False, default='1.0')

    # Action plan (computed recommendations)
    action_plan = Column(JSON, nullable=False, default=dict)

    # Audit trail
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Metadata for future ML training
    training_labels = Column(JSON, nullable=False, default=dict)

    # Optimistic locking
    version = Column(BigInteger, nullable=False, default=1)

    def __repr__(self):
        return f"<RiskScore(challenge_id={self.challenge_id}, score={self.risk_score}, level={self.risk_level})>"

    @property
    def is_critical(self) -> bool:
        """Check if this represents critical risk."""
        return self.risk_level == RiskLevel.CRITICAL.value

    @property
    def is_high_risk(self) -> bool:
        """Check if this represents high risk."""
        return self.risk_level == RiskLevel.HIGH_RISK.value

    @property
    def requires_action(self) -> bool:
        """Check if this score requires immediate action."""
        return self.risk_level in [RiskLevel.HIGH_RISK.value, RiskLevel.CRITICAL.value]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': str(self.id),
            'challenge_id': str(self.challenge_id),
            'user_id': str(self.user_id),
            'risk_score': float(self.risk_score),
            'risk_level': self.risk_level,
            'score_breakdown': self.score_breakdown,
            'feature_summary': self.feature_summary,
            'assessed_at': self.assessed_at.isoformat(),
            'assessment_version': self.assessment_version,
            'action_plan': self.action_plan,
            'created_at': self.created_at.isoformat()
        }


# Export for easy importing
__all__ = ['RiskScore', 'RiskLevel']