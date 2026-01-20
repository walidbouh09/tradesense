"""Rules engine database models."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ....infrastructure.database.base import BaseModel


class RuleEngineModel(BaseModel):
    """Rule engine database model."""
    
    __tablename__ = "rule_engines"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    active_rule_set_name = Column(String(255), nullable=True)
    evaluation_count = Column(String(50), default="0")
    last_evaluation_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    rule_sets = relationship("RuleSetModel", back_populates="rule_engine", cascade="all, delete-orphan")
    evaluation_results = relationship("RuleEvaluationResultModel", back_populates="rule_engine", cascade="all, delete-orphan")


class RuleSetModel(BaseModel):
    """Rule set database model."""
    
    __tablename__ = "rule_sets"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    rule_engine_id = Column(PG_UUID(as_uuid=True), ForeignKey("rule_engines.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    version = Column(String(50), default="1.0")
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    rule_engine = relationship("RuleEngineModel", back_populates="rule_sets")
    rules = relationship("RuleDefinitionModel", back_populates="rule_set", cascade="all, delete-orphan")


class RuleDefinitionModel(BaseModel):
    """Rule definition database model."""
    
    __tablename__ = "rule_definitions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    rule_set_id = Column(PG_UUID(as_uuid=True), ForeignKey("rule_sets.id"), nullable=False)
    rule_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rule_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    version = Column(String(50), default="1.0")
    tags = Column(JSON, default=list)
    conditions = Column(JSON, nullable=False)  # Serialized RuleCondition objects
    parameters = Column(JSON, default=list)   # Serialized RuleParameter objects
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    rule_set = relationship("RuleSetModel", back_populates="rules")


class RuleEvaluationResultModel(BaseModel):
    """Rule evaluation result database model."""
    
    __tablename__ = "rule_evaluation_results"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    rule_engine_id = Column(PG_UUID(as_uuid=True), ForeignKey("rule_engines.id"), nullable=False)
    rule_id = Column(String(255), nullable=False, index=True)
    rule_name = Column(String(255), nullable=False)
    passed = Column(Boolean, nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    condition_results = Column(JSON, default=list)
    evaluation_timestamp = Column(DateTime, nullable=False, index=True)
    context_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    rule_engine = relationship("RuleEngineModel", back_populates="evaluation_results")


class RuleViolationTrackerModel(BaseModel):
    """Rule violation tracker database model."""
    
    __tablename__ = "rule_violation_trackers"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    entity_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    total_violations = Column(String(50), default="0")
    unique_rules_violated = Column(String(50), default="0")
    first_violation_at = Column(DateTime, nullable=True)
    last_violation_at = Column(DateTime, nullable=True)
    violation_counts = Column(JSON, default=dict)  # rule_id -> count mapping
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    violations = relationship("RuleViolationModel", back_populates="tracker", cascade="all, delete-orphan")


class RuleViolationModel(BaseModel):
    """Individual rule violation database model."""
    
    __tablename__ = "rule_violations"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    tracker_id = Column(PG_UUID(as_uuid=True), ForeignKey("rule_violation_trackers.id"), nullable=False)
    rule_id = Column(String(255), nullable=False, index=True)
    rule_name = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    condition_results = Column(JSON, default=list)
    evaluation_timestamp = Column(DateTime, nullable=False, index=True)
    context_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tracker = relationship("RuleViolationTrackerModel", back_populates="violations")