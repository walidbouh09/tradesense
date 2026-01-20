"""
Risk AI Domain - Adaptive Risk Scoring for Prop Trading

This domain provides intelligent risk assessment for trading challenges.
It analyzes trader behavior patterns and computes dynamic risk scores
to enhance the existing rule-based risk management system.

Domain Principles:
- Fully isolated from Challenge Engine (read-only access)
- No impact on real-time trading decisions
- Async computation in background workers
- Explainable, auditable scoring logic
- Regulator-friendly transparency

Key Components:
- Feature Engineering: Extract risk-relevant features from trade history
- Risk Scorer: Compute explainable risk scores from features
- Risk Service: Orchestrate feature extraction and scoring
- Persistence: Store risk score history for audit and analysis
"""

from .service import RiskAIService
from .scorer import RiskScorer
from .features import FeatureEngineer
from .thresholds import RiskThresholds

__all__ = ['RiskAIService', 'RiskScorer', 'FeatureEngineer', 'RiskThresholds']