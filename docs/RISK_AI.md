# Adaptive Risk Scoring System - Technical Documentation

## Overview

The Adaptive Risk Scoring system implements intelligent risk assessment for prop trading challenges. It analyzes trader behavior patterns and computes dynamic risk scores to enhance the existing rule-based risk management system.

**Key Characteristics:**
- **Fully Explainable**: No black-box models - all scoring logic is transparent
- **Regulator-Friendly**: Designed for financial compliance and audit requirements
- **Deterministic**: Same input data always produces identical risk scores
- **Async Computation**: Runs in background workers without impacting trading performance
- **Append-Only Storage**: Complete audit trail of all risk assessments

## Why This AI Exists

### Business Context
Prop trading firms face significant financial risk from trader behavior. Traditional rule-based systems (max drawdown, profit targets) are necessary but insufficient for comprehensive risk management. The Adaptive Risk Scoring system provides:

1. **Early Warning**: Identifies risky behavior patterns before rule violations
2. **Behavioral Insights**: Quantifies trader psychology and decision-making quality
3. **Dynamic Assessment**: Adapts risk evaluation based on trading patterns
4. **Regulatory Compliance**: Provides explainable risk metrics for oversight

### Technical Motivation
- **Performance Isolation**: Risk analysis doesn't slow down trading operations
- **Scalability**: Background processing can scale independently
- **Auditability**: Every risk decision is logged and explainable
- **Enhancement Path**: Foundation for future ML-based scoring models

## Architecture

### Domain Structure

```
app/domains/risk_ai/
├── __init__.py          # Domain exports
├── README.md           # Architecture documentation
├── features.py         # Feature engineering
├── scorer.py          # Risk scoring logic
├── thresholds.py      # Risk level definitions
├── service.py         # Orchestration service
└── model.py           # Persistence models

tests/risk_ai/
├── test_features.py   # Feature engineering tests
├── test_scorer.py     # Scoring logic tests
├── test_thresholds.py # Threshold tests
└── test_service.py    # Service integration tests
```

### Component Responsibilities

#### Feature Engineering (`features.py`)
**Purpose**: Extract risk-relevant features from raw trading data

**Features Computed:**
- **Performance**: `avg_trade_pnl`, `pnl_volatility`, `win_rate`, `profit_factor`
- **Risk**: `max_intraday_drawdown`, `drawdown_speed`, `loss_streak`
- **Behavior**: `trades_per_hour`, `overtrading_score`, `revenge_trading_score`

**Design Principles:**
- Pure functions with no side effects
- Financially meaningful calculations
- Robust handling of edge cases
- Deterministic results from same input

#### Risk Scorer (`scorer.py`)
**Purpose**: Compute explainable risk scores from engineered features

**Scoring Formula:**
```
Risk Score = (Volatility × 30%) + (Drawdown × 25%) + (Behavior × 20%) +
             (Loss Streak × 15%) + (Overtrading × 10%)
```

**Component Breakdown:**
- **Volatility (30%)**: Return consistency and predictability
- **Drawdown (25%)**: Risk-taking patterns and loss tolerance
- **Behavior (20%)**: Trading frequency and market participation
- **Loss Streak (15%)**: Current losing momentum and streak risk
- **Overtrading (10%)**: Excessive trading relative to profitability

#### Thresholds (`thresholds.py`)
**Purpose**: Define risk level classifications and actionable responses

**Risk Levels:**
- **STABLE (0-30)**: Low risk, standard monitoring
- **MONITOR (30-60)**: Moderate risk, enhanced oversight
- **HIGH_RISK (60-80)**: High risk, active intervention needed
- **CRITICAL (80-100)**: Critical risk, immediate action required

#### Risk AI Service (`service.py`)
**Purpose**: Orchestrate complete risk assessment workflow

**Workflow:**
1. Validate input data
2. Convert trade records to domain objects
3. Engineer risk features
4. Compute risk score
5. Classify risk level
6. Generate action plan
7. Return structured assessment

## Why Heuristics First (Not ML)

### Current Approach: Explainable Heuristics

**Advantages:**
1. **Full Transparency**: Every score component is mathematically explainable
2. **Regulatory Compliance**: No "black box" decision-making
3. **Deterministic**: Identical results from same data every time
4. **Audit-Friendly**: Complete scoring breakdown for oversight
5. **Fast Iteration**: Easy to modify and deploy rule changes

**Implementation:**
```python
# Example: Volatility scoring
volatility_ratio = pnl_volatility / abs(avg_trade_pnl)
score = min(100, volatility_ratio / 5.0 * 100)
```

### Future Evolution: ML Models

**Transition Strategy:**
1. **Phase 1 (Current)**: Heuristic baseline with full explainability
2. **Phase 2**: Hybrid approach - heuristics + ML feature engineering
3. **Phase 3**: ML model with explainability techniques (SHAP, LIME)
4. **Phase 4**: Advanced ML with regulatory-approved interpretability

**ML Readiness Features:**
- **Feature Store**: Structured features for model training
- **Score History**: Labeled data for supervised learning
- **A/B Testing**: Compare heuristic vs ML performance
- **Model Validation**: Backtesting against historical outcomes

## Feature Explainability

### Performance Features

#### Average Trade PnL
**Formula**: `sum(realized_pnl) / trade_count`
**Meaning**: Overall profitability per trade
**Risk Implication**: Consistently negative = high risk

#### PnL Volatility
**Formula**: Population standard deviation of trade PnL
**Meaning**: Consistency of trading returns
**Risk Implication**: High volatility = unpredictable performance

#### Win Rate
**Formula**: `profitable_trades / total_trades × 100`
**Meaning**: Percentage of successful trades
**Risk Implication**: Low win rate with high frequency = overtrading risk

#### Profit Factor
**Formula**: `gross_profit / gross_loss` (if gross_loss > 0)
**Meaning**: Reward-to-risk ratio
**Risk Implication**: < 1.0 = losing strategy

### Risk Features

#### Max Intraday Drawdown
**Formula**: Maximum `(peak - trough) / peak` within a trading day
**Meaning**: Largest single-day equity decline experienced
**Risk Implication**: > 5% = significant risk tolerance

#### Drawdown Speed
**Formula**: Average loss percentage per losing trade
**Meaning**: How quickly capital is depleted
**Risk Implication**: Fast drawdown = aggressive risk-taking

#### Loss Streak
**Formula**: Current consecutive losing trades
**Meaning**: Recent losing momentum
**Risk Implication**: Long streaks indicate emotional trading

### Behavioral Features

#### Trades Per Hour
**Formula**: `total_trades / analysis_period_hours`
**Meaning**: Trading frequency intensity
**Risk Implication**: Very high/low frequency can indicate issues

#### Overtrading Score
**Formula**: `(frequency_penalty × (1 - win_rate)) × 100`
**Meaning**: Trading too frequently relative to success
**Risk Implication**: High score = potential overtrading behavior

#### Revenge Trading Score
**Formula**: Percentage of trades showing position size increases after losses
**Meaning**: Emotional response to losses
**Risk Implication**: High score = revenge trading patterns

## Audit & Compliance Alignment

### Regulatory Requirements Addressed

#### SEC/FinRA Compliance
- **Explainable Decisions**: All risk scores have detailed breakdowns
- **Audit Trail**: Complete history of assessments and features
- **Deterministic Logic**: Same data always produces same results
- **No Black Box**: Transparent mathematical formulas

#### SOC 2 Compliance
- **Data Integrity**: Append-only storage prevents tampering
- **Access Controls**: Separate permissions for risk data
- **Change Management**: Versioned scoring algorithms
- **Monitoring**: Automated alerts for system issues

### Audit Trail Implementation

#### Database Schema
```sql
-- Risk scores table with complete audit trail
CREATE TABLE risk_scores (
    id UUID PRIMARY KEY,
    challenge_id UUID NOT NULL,
    user_id UUID NOT NULL,
    risk_score NUMERIC(5,2) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    score_breakdown JSONB NOT NULL,      -- Component details
    feature_summary JSONB NOT NULL,      -- Input features
    assessed_at TIMESTAMPTZ NOT NULL,
    assessment_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
```

#### Audit Capabilities
- **Feature Preservation**: Store exact inputs used for scoring
- **Score Breakdown**: Component contributions and weights
- **Version Tracking**: Algorithm version for each assessment
- **Temporal Queries**: Risk score evolution over time

### Data Retention
- **7+ years**: For regulatory compliance
- **Partitioned Storage**: Monthly partitions for performance
- **Cold Storage**: Archive older data to reduce costs
- **Backup Verification**: Regular integrity checks

## Roadmap Toward ML Models

### Phase 1 → Phase 2: Feature Enhancement
**Goal**: Improve feature engineering while maintaining explainability

**Improvements:**
- Time-series features (momentum, trends)
- Cross-challenge comparisons
- Market condition adjustments
- Advanced behavioral pattern recognition

### Phase 2 → Phase 3: ML Integration
**Goal**: Introduce ML models with maintained explainability

**Implementation:**
- **Model Types**: Gradient boosting, neural networks
- **Explainability**: SHAP values, feature importance
- **Validation**: Backtesting against historical performance
- **Fallback**: Heuristic scores if ML fails

### Phase 3 → Phase 4: Advanced ML
**Goal**: Full ML-driven scoring with regulatory approval

**Capabilities:**
- Deep learning for pattern recognition
- Real-time feature engineering
- Adaptive threshold adjustment
- Predictive risk forecasting

### Technical Foundation

#### Data Pipeline
```
Raw Trades → Feature Engineering → Feature Store → ML Models → Risk Scores
     ↓              ↓                      ↓              ↓
  Audit       Explainable             Training       Explainable
  Trail       Features               Data           Scores
```

#### Model Governance
- **Version Control**: All models versioned and auditable
- **A/B Testing**: Compare model performance safely
- **Drift Detection**: Monitor for concept drift
- **Fallback Logic**: Automatic fallback to heuristics

### Success Metrics

#### Model Performance
- **Accuracy**: Risk score correlation with actual outcomes
- **Precision**: False positive rate for critical alerts
- **Recall**: Detection rate for high-risk traders
- **Stability**: Score consistency over time

#### Business Impact
- **Early Detection**: Time to identify risky behavior
- **False Alerts**: Reduction in unnecessary interventions
- **Regulatory Compliance**: Audit pass rate
- **Operational Efficiency**: Risk team productivity

## Implementation Details

### Async Processing Architecture

#### Worker Integration
```python
# In risk_worker.py
def perform_risk_assessment(self, session, challenges):
    for challenge in challenges:
        # Load trade history
        trades = self._load_challenge_trades(session, challenge.id)

        # Perform assessment
        assessment = self.risk_ai_service.assess_challenge_risk(...)

        # Persist results
        self._persist_risk_score(session, assessment)

        # Emit alerts if needed
        self._check_risk_alerts(assessment)
```

#### Event Emission
```python
# Alert structure for monitoring systems
alert_payload = {
    'alert_type': 'WARNING',  # or 'CRITICAL'
    'risk_score': 75.5,
    'risk_level': 'HIGH_RISK',
    'action_required': 'Implement position size limits',
    'trading_context': {...},  # Relevant trade metrics
    'recommended_actions': [...]  # Specific recommendations
}
```

### Error Handling & Resilience

#### Graceful Degradation
- **Data Issues**: Skip invalid trades, use defaults
- **Computation Errors**: Log and continue with other assessments
- **Persistence Failures**: Assessment succeeds, persistence is logged failure
- **Worker Crashes**: Independent of trading operations

#### Monitoring & Alerting
- **Assessment Success Rate**: Track computation reliability
- **Score Distribution**: Monitor for anomalies
- **Alert Effectiveness**: Measure response times and outcomes
- **Performance Metrics**: Track computation time and resource usage

### Testing Strategy

#### Unit Tests
- **Feature Engineering**: Deterministic calculations
- **Scoring Logic**: Score bounds and component weights
- **Threshold Logic**: Classification accuracy
- **Service Integration**: End-to-end workflows

#### Integration Tests
- **Worker Processing**: Background assessment execution
- **Database Persistence**: Audit trail integrity
- **Event Emission**: Alert delivery to monitoring systems

#### Performance Tests
- **Scalability**: Assessment throughput under load
- **Memory Usage**: Large trade histories
- **Database Impact**: Query performance and locking

### Deployment Considerations

#### Environment Configuration
```bash
# Production settings
RISK_AI_ENABLED=true
RISK_ASSESSMENT_INTERVAL=300  # 5 minutes
MAX_ASSESSMENT_BATCH_SIZE=50  # Challenges per cycle
RISK_SCORE_RETENTION_DAYS=2555  # 7 years
```

#### Scaling Strategy
- **Horizontal**: Multiple worker instances
- **Vertical**: Increase memory for large assessments
- **Database**: Read replicas for historical analysis
- **Caching**: Redis for frequently accessed features

#### Rollback Plan
- **Feature Flags**: Disable risk AI without code changes
- **Version Pinning**: Specify scoring algorithm versions
- **Data Recovery**: Recompute scores from trade history
- **Alert Suppression**: Temporarily disable alerts if needed

## Conclusion

The Adaptive Risk Scoring system provides a robust foundation for intelligent risk management in prop trading. By starting with fully explainable heuristics, it ensures regulatory compliance and auditability while establishing the technical foundation for future ML enhancements.

The system's design prioritizes:
- **Transparency**: Every risk score is mathematically explainable
- **Reliability**: Deterministic results with comprehensive error handling
- **Performance**: Async processing that doesn't impact trading operations
- **Compliance**: Complete audit trails and regulatory-friendly design

This approach balances innovation with the conservative requirements of financial technology, providing meaningful risk insights while maintaining the highest standards of safety and accountability.