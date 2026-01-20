"""
Risk Engine Usage Examples

This file demonstrates how to use the Risk Engine for real-time risk monitoring,
assessment, and alert management in the TradeSense AI prop trading platform.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from src.domains.risk.application.services import (
    RiskMonitoringService,
    RiskAssessmentService,
    RiskProfileService,
    RiskEventHandler,
)
from src.domains.risk.domain.entities import RiskEngine
from src.domains.risk.domain.value_objects import (
    AlertSeverity,
    RiskLevel,
    RiskLimits,
    RiskMetricType,
    RiskProfile,
    RiskThreshold,
    ThresholdType,
)
from src.infrastructure.messaging.event_bus import InMemoryEventBus
from src.shared.utils.money import Money


async def example_1_basic_risk_engine_setup():
    """Example 1: Basic Risk Engine setup and configuration."""
    
    print("=== Example 1: Basic Risk Engine Setup ===")
    
    # Create event bus
    event_bus = InMemoryEventBus()
    
    # Create services
    risk_monitoring = RiskMonitoringService(event_bus)
    risk_assessment = RiskAssessmentService(event_bus)
    risk_profile_service = RiskProfileService(event_bus)
    
    # Create trader and challenge IDs
    user_id = uuid4()
    challenge_id = uuid4()
    
    print(f"👤 User ID: {user_id}")
    print(f"🎯 Challenge ID: {challenge_id}")
    
    # Create risk profile for Phase 1 challenge
    risk_profile = await risk_profile_service.create_challenge_risk_profile(
        user_id=user_id,
        challenge_id=challenge_id,
        challenge_type="PHASE_1",
        initial_balance=Money(Decimal("100000"), "USD"),
    )
    
    print(f"📋 Risk Profile: {risk_profile.profile_name}")
    print(f"📊 Thresholds: {len(risk_profile.thresholds)} configured")
    print(f"📈 Max Daily Trades: {risk_profile.max_daily_trades}")
    print(f"💰 Max Position Size: {risk_profile.max_position_size_percent}%")
    
    # Create risk limits
    risk_limits = await risk_profile_service.create_risk_limits(
        challenge_type="PHASE_1",
        initial_balance=Money(Decimal("100000"), "USD"),
    )
    
    print(f"🚫 Daily Loss Limit: {risk_limits.max_daily_loss_percent}%")
    print(f"🚫 Total Loss Limit: {risk_limits.max_total_loss_percent}%")
    
    # Create Risk Engine
    risk_engine = RiskEngine(
        user_id=user_id,
        challenge_id=challenge_id,
        risk_profile=risk_profile,
        risk_limits=risk_limits,
    )
    
    print(f"🔧 Risk Engine ID: {risk_engine.id}")
    print(f"⚡ Trading Halted: {risk_engine.is_trading_halted}")
    print(f"📊 Risk Score: {risk_engine.current_risk_score.overall_score if risk_engine.current_risk_score else 'Not calculated'}")
    
    return risk_engine, risk_monitoring, risk_assessment


async def example_2_trade_event_processing():
    """Example 2: Processing trade events and risk calculations."""
    
    print("\n=== Example 2: Trade Event Processing ===")
    
    # Setup from example 1
    risk_engine, risk_monitoring, risk_assessment = await example_1_basic_risk_engine_setup()
    
    # Simulate initial balance
    await risk_monitoring.process_pnl_event(
        risk_engine=risk_engine,
        pnl_data={
            "current_balance": "100000.00",
            "daily_pnl": "0.00",
            "total_pnl": "0.00",
            "total_unrealized_pnl": "0.00",
            "date": datetime.now().isoformat(),
        },
    )