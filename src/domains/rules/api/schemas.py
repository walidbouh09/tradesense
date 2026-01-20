"""Rules engine API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RuleConditionSchema(BaseModel):
    """Rule condition schema."""
    field: str = Field(..., description="Field name to evaluate")
    operator: str = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Value to compare against")
    secondary_value: Optional[Any] = Field(None, description="Secondary value for BETWEEN operations")


class RuleParameterSchema(BaseModel):
    """Rule parameter schema."""
    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value")
    data_type: str = Field(..., description="Parameter data type")
    description: Optional[str] = Field("", description="Parameter description")


class RuleDefinitionSchema(BaseModel):
    """Rule definition schema."""
    rule_id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    rule_type: str = Field(..., description="Rule type")
    severity: str = Field(..., description="Rule severity level")
    conditions: List[RuleConditionSchema] = Field(..., description="Rule conditions")
    parameters: List[RuleParameterSchema] = Field(default_factory=list, description="Rule parameters")
    enabled: bool = Field(True, description="Whether rule is enabled")
    tags: List[str] = Field(default_factory=list, description="Rule tags")
    version: str = Field("1.0", description="Rule version")


class RuleSetSchema(BaseModel):
    """Rule set schema."""
    name: str = Field(..., description="Rule set name")
    description: str = Field(..., description="Rule set description")
    rules: List[RuleDefinitionSchema] = Field(..., description="Rules in the set")
    tags: List[str] = Field(default_factory=list, description="Rule set tags")
    version: str = Field("1.0", description="Rule set version")


class RuleEngineSchema(BaseModel):
    """Rule engine schema."""
    id: UUID = Field(..., description="Rule engine ID")
    name: str = Field(..., description="Rule engine name")
    description: str = Field(..., description="Rule engine description")
    rule_sets: List[RuleSetSchema] = Field(default_factory=list, description="Rule sets")
    active_rule_set_name: Optional[str] = Field(None, description="Active rule set name")
    evaluation_count: int = Field(0, description="Total evaluations performed")
    last_evaluation_at: Optional[datetime] = Field(None, description="Last evaluation timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CreateRuleEngineRequest(BaseModel):
    """Create rule engine request."""
    name: str = Field(..., description="Rule engine name")
    description: str = Field(..., description="Rule engine description")
    rule_sets: List[RuleSetSchema] = Field(default_factory=list, description="Initial rule sets")


class AddRuleSetRequest(BaseModel):
    """Add rule set request."""
    rule_set: RuleSetSchema = Field(..., description="Rule set to add")


class ActivateRuleSetRequest(BaseModel):
    """Activate rule set request."""
    rule_set_name: str = Field(..., description="Name of rule set to activate")


class RuleEvaluationContextSchema(BaseModel):
    """Rule evaluation context schema."""
    challenge_id: Optional[UUID] = Field(None, description="Challenge ID")
    trader_id: Optional[UUID] = Field(None, description="Trader ID")
    initial_balance: Optional[float] = Field(None, description="Initial balance")
    current_balance: Optional[float] = Field(None, description="Current balance")
    daily_pnl: Optional[float] = Field(None, description="Daily P&L")
    total_pnl: Optional[float] = Field(None, description="Total P&L")
    trading_days: Optional[int] = Field(None, description="Trading days")
    daily_trade_count: Optional[int] = Field(None, description="Daily trade count")
    total_trades: Optional[int] = Field(None, description="Total trades")
    daily_drawdown_percent: Optional[float] = Field(None, description="Daily drawdown percentage")
    total_drawdown_percent: Optional[float] = Field(None, description="Total drawdown percentage")
    max_single_day_profit_percent: Optional[float] = Field(None, description="Max single day profit percentage")
    additional_data: Dict[str, Any] = Field(default_factory=dict, description="Additional context data")


class EvaluateRulesRequest(BaseModel):
    """Evaluate rules request."""
    context: RuleEvaluationContextSchema = Field(..., description="Evaluation context")
    rule_types: Optional[List[str]] = Field(None, description="Filter by rule types")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class RuleEvaluationResultSchema(BaseModel):
    """Rule evaluation result schema."""
    rule_id: str = Field(..., description="Rule ID")
    rule_name: str = Field(..., description="Rule name")
    passed: bool = Field(..., description="Whether rule passed")
    severity: str = Field(..., description="Rule severity")
    message: str = Field(..., description="Evaluation message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Evaluation details")
    condition_results: List[str] = Field(default_factory=list, description="Condition evaluation results")
    evaluation_timestamp: str = Field(..., description="Evaluation timestamp")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Context snapshot")


class RuleEvaluationResponse(BaseModel):
    """Rule evaluation response."""
    evaluation_summary: Dict[str, Any] = Field(..., description="Evaluation summary")
    violations: List[RuleEvaluationResultSchema] = Field(default_factory=list, description="Rule violations")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    violation_analysis: Dict[str, Any] = Field(default_factory=dict, description="Violation analysis")
    should_halt_trading: bool = Field(False, description="Whether trading should be halted")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Context snapshot")


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request."""
    trading_context: RuleEvaluationContextSchema = Field(..., description="Trading context")


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response."""
    risk_assessment: Dict[str, Any] = Field(..., description="Risk assessment details")
    risk_violations: List[Dict[str, Any]] = Field(default_factory=list, description="Risk violations")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Context snapshot")


class CreateChallengeRuleEngineRequest(BaseModel):
    """Create challenge rule engine request."""
    challenge_id: UUID = Field(..., description="Challenge ID")
    challenge_type: str = Field(..., description="Challenge type (PHASE_1, PHASE_2, FUNDED)")
    initial_balance: float = Field(..., description="Initial balance amount")
    currency: str = Field("USD", description="Currency code")


class RuleViolationSchema(BaseModel):
    """Rule violation schema."""
    rule_id: str = Field(..., description="Rule ID")
    rule_name: str = Field(..., description="Rule name")
    severity: str = Field(..., description="Violation severity")
    message: str = Field(..., description="Violation message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Violation details")
    evaluation_timestamp: str = Field(..., description="Violation timestamp")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Context snapshot")


class ViolationAnalysisRequest(BaseModel):
    """Violation analysis request."""
    entity_id: UUID = Field(..., description="Entity ID (challenge, trader, etc.)")
    entity_type: str = Field(..., description="Entity type")
    time_window_hours: int = Field(24, description="Time window for analysis in hours")


class ViolationAnalysisResponse(BaseModel):
    """Violation analysis response."""
    analysis: Dict[str, Any] = Field(..., description="Violation analysis")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    requires_immediate_action: bool = Field(False, description="Whether immediate action is required")
    violations: List[RuleViolationSchema] = Field(default_factory=list, description="Recent violations")


class RuleTemplateRequest(BaseModel):
    """Rule template request."""
    template_type: str = Field(..., description="Template type")
    parameters: Dict[str, Any] = Field(..., description="Template parameters")


class RuleTemplateResponse(BaseModel):
    """Rule template response."""
    rule: RuleDefinitionSchema = Field(..., description="Generated rule")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    rule_engines_count: int = Field(..., description="Number of rule engines")
    active_evaluations: int = Field(..., description="Active evaluations in last hour")
    last_evaluation: Optional[str] = Field(None, description="Last evaluation timestamp")