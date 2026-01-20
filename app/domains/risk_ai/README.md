# Risk AI Domain Structure

## Overview

The Risk AI domain implements adaptive risk scoring for prop trading challenges. It analyzes trader behavior patterns and computes dynamic risk scores to enhance the existing rule-based risk management system.

## Architecture Principles

### Isolation & Safety
- **No dependency** on Challenge Engine or WebSocket components
- **Read-only access** to trading data (never modifies challenge state)
- **Async computation** only (runs in background workers)
- **No impact** on real-time trading performance

### Transparency & Auditability
- **Fully explainable** scoring logic (no black-box models)
- **Deterministic** results from same input data
- **Regulator-friendly** transparency
- **Audit trail** of all risk assessments

### Enhancement, Not Replacement
- **Reinforces** existing risk rules (does not replace them)
- **Advisory system** for risk monitoring
- **Progressive enhancement** toward ML-based scoring

## Module Responsibilities

### 1. Features (`features.py`)
**Purpose:** Extract risk-relevant features from raw trading data

**Responsibilities:**
- Transform trade history into analytical features
- Compute statistical measures of trader behavior
- Provide explainable metrics for risk assessment
- Handle edge cases (insufficient data, etc.)

**Inputs:** List of historical trades (immutable data structures)
**Outputs:** Feature dictionary with explainable metrics

**Key Features:**
- Performance metrics (PnL volatility, win rate, profit factor)
- Risk metrics (drawdown behavior, loss streaks)
- Behavioral metrics (trading frequency, overtrading patterns)

### 2. Scorer (`scorer.py`)
**Purpose:** Compute risk scores from engineered features

**Responsibilities:**
- Apply weighted scoring algorithm to features
- Normalize scores to 0-100 range
- Provide detailed score breakdown for explainability
- Handle missing or invalid feature values

**Inputs:** Feature dictionary from FeatureEngineer
**Outputs:** RiskScore object with score and breakdown

**Scoring Logic:**
- Weighted combination of feature categories
- Baseline heuristic model (explainable by design)
- Ready for ML model replacement in future phases

### 3. Thresholds (`thresholds.py`)
**Purpose:** Define risk level classification and interpretation

**Responsibilities:**
- Map risk scores to severity levels
- Provide actionable thresholds for monitoring
- Support configurable risk policies
- Enable escalation workflows

**Risk Levels:**
- STABLE (0-30): Low risk, normal monitoring
- MONITOR (30-60): Moderate risk, enhanced monitoring
- HIGH_RISK (60-80): High risk, intervention may be needed
- CRITICAL (80-100): Critical risk, immediate action required

### 4. Service (`service.py`)
**Purpose:** Orchestrate the complete risk assessment workflow

**Responsibilities:**
- Coordinate feature extraction and scoring
- Provide clean API for worker integration
- Handle errors gracefully
- Return structured risk assessment results

**Inputs:** Challenge ID and trade history
**Outputs:** Complete RiskAssessment with score, level, and explanation

**Integration Points:**
- Called by background workers
- Results persisted for audit trail
- Alerts emitted for threshold breaches
- No direct UI or real-time dependencies

## Data Flow

```
Challenge ID ──┐
               │
Trade History ─┼── FeatureEngineer ── Features ── RiskScorer ── RiskAssessment
               │                                          │
               └─────────────────── Thresholds ───────────┘
```

## Boundary Analysis

### What Belongs Here
- Risk feature extraction and analysis
- Explainable scoring algorithms
- Risk threshold definitions
- Historical risk score persistence
- Risk alert generation

### What Does NOT Belong Here
- Real-time trading decisions (Challenge Engine)
- WebSocket event emission (infrastructure)
- Database mutations (except risk score history)
- User interface logic
- Payment processing

### Dependencies
- **Read-only:** Trade history from database
- **Infrastructure:** Event bus for alerts
- **No dependencies** on Challenge Engine or WebSocket

## Future Evolution

### Phase 2: ML Models
- Replace heuristic scorer with trained ML models
- Maintain explainability through model interpretability techniques
- A/B testing of scoring algorithms

### Phase 3: Advanced Features
- Time-series risk analysis
- Cross-challenge pattern recognition
- Market condition adjustments
- Dynamic threshold adaptation

### Phase 4: Predictive Capabilities
- Risk score forecasting
- Early warning systems
- Automated risk mitigation recommendations

## Quality Assurance

### Testing Strategy
- Unit tests for all scoring logic
- Deterministic test data
- Edge case coverage
- Regression testing for score stability

### Monitoring & Alerting
- Risk score distribution monitoring
- Alert effectiveness metrics
- Performance impact assessment
- False positive/negative analysis

### Audit & Compliance
- Complete scoring history retention
- Feature value preservation
- Scoring logic version tracking
- Regulatory reporting capabilities