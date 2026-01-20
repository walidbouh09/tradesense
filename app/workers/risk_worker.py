"""
Risk Worker - Background Monitoring for TradeSense AI

Performs periodic background processing for non-critical risk monitoring.
Scans active challenges and performs checks that don't belong in synchronous
trade processing.

WHAT BELONGS HERE (vs Challenge Engine):
- Periodic health checks on active challenges
- Risk trend analysis over time
- Non-critical alert generation
- Data aggregation for analytics
- Maintenance tasks (cleanup, archiving)

WHAT DOES NOT BELONG HERE:
- Synchronous trade processing (belongs in ChallengeEngine)
- Critical business rule evaluation (belongs in ChallengeEngine)
- Real-time risk decisions (belongs in ChallengeEngine)
- User-facing API responses (belongs in Flask routes)
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List

# Database and configuration
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Application imports
from src.domains.challenge.model import Challenge, ChallengeStatus
from src.core.event_bus import event_bus

# Risk AI imports
from app.domains.risk_ai.service import RiskAIService
from app.domains.risk_ai.model import RiskScore

# Configure logging for background worker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('risk_worker')


class RiskWorker:
    """
    Background risk monitoring worker.

    Runs continuously, scanning active challenges for potential issues
    that don't require immediate synchronous processing.
    """

    def __init__(self):
        """Initialize worker with configuration."""
        # Database configuration
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/tradesense')
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Worker configuration
        self.interval_seconds = int(os.getenv('WORKER_INTERVAL', '60'))  # Default 1 minute
        self.max_runtime_hours = int(os.getenv('WORKER_MAX_RUNTIME', '24'))  # Restart daily

        # Risk monitoring thresholds
        self.inactive_threshold_minutes = int(os.getenv('INACTIVE_THRESHOLD_MINUTES', '30'))
        self.high_activity_threshold = int(os.getenv('HIGH_ACTIVITY_THRESHOLD', '100'))  # trades per hour

        # Health check file for Docker health checks
        self.health_file = '/tmp/worker_health'

        # Initialize Risk AI Service for adaptive risk scoring
        self.risk_ai_service = RiskAIService()

        logger.info("Risk worker initialized", extra={
            'interval': self.interval_seconds,
            'database': self.database_url.replace('://', '://[redacted]@'),
            'risk_ai_enabled': True,
        })

    def run(self):
        """
        Main worker loop.

        Runs continuously until terminated or max runtime reached.
        """
        start_time = datetime.now(timezone.utc)
        max_runtime = timedelta(hours=self.max_runtime_hours)

        logger.info("Starting risk monitoring worker")

        try:
            while True:
                cycle_start = datetime.now(timezone.utc)

                # Check if we've exceeded max runtime
                if datetime.now(timezone.utc) - start_time > max_runtime:
                    logger.info("Max runtime reached, restarting worker")
                    break

                try:
                    # Perform monitoring cycle
                    self.perform_monitoring_cycle()

                    # Update health check timestamp
                    self.update_health_check()

                except Exception as e:
                    logger.error("Error in monitoring cycle", exc_info=True)
                    # Continue running despite errors

                # Sleep until next cycle
                cycle_duration = datetime.now(timezone.utc) - cycle_start
                sleep_time = max(0, self.interval_seconds - cycle_duration.total_seconds())

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Worker received shutdown signal")
        except Exception as e:
            logger.error("Fatal worker error", exc_info=True)
        finally:
            logger.info("Worker shutting down")

    def perform_monitoring_cycle(self):
        """
        Perform one complete monitoring cycle.

        Scans active challenges and performs background risk checks.
        """
        with self.SessionLocal() as session:
            try:
                # Get all active challenges for monitoring
                active_challenges = self.get_active_challenges(session)

                if not active_challenges:
                    logger.debug("No active challenges to monitor")
                    return

                logger.debug(f"Monitoring {len(active_challenges)} active challenges")

                # Perform monitoring tasks
                self.check_inactive_challenges(session, active_challenges)
                self.check_high_activity_challenges(session, active_challenges)
                self.check_stale_daily_resets(session, active_challenges)

                # Perform adaptive risk scoring (new AI-powered assessment)
                self.perform_risk_assessment(session, active_challenges)

                self.update_challenge_metrics(session, active_challenges)

                # Commit all changes
                session.commit()

            except SQLAlchemyError as e:
                logger.error("Database error in monitoring cycle", exc_info=True)
                session.rollback()
            except Exception as e:
                logger.error("Unexpected error in monitoring cycle", exc_info=True)
                session.rollback()

    def get_active_challenges(self, session: Session) -> List[Challenge]:
        """
        Get all challenges that need monitoring.

        Focuses on ACTIVE challenges that are currently being traded.
        """
        return session.query(Challenge).filter(
            Challenge.status == ChallengeStatus.ACTIVE
        ).all()

    def check_inactive_challenges(self, session: Session, challenges: List[Challenge]):
        """
        Check for challenges with no recent trading activity.

        Generates alerts for challenges that may have stalled or
        traders that have stopped trading.
        """
        now = datetime.now(timezone.utc)
        threshold = timedelta(minutes=self.inactive_threshold_minutes)

        for challenge in challenges:
            if not challenge.last_trade_at:
                continue

            inactive_duration = now - challenge.last_trade_at

            if inactive_duration > threshold:
                # Emit alert for monitoring (not critical decision)
                event_bus.emit('RISK_ALERT', {
                    'challenge_id': str(challenge.id),
                    'user_id': str(challenge.user_id),
                    'alert_type': 'INACTIVE_TRADING',
                    'severity': 'MEDIUM',
                    'title': 'Inactive Trading Detected',
                    'message': f'No trades for {inactive_duration.total_seconds() / 60:.0f} minutes',
                    'current_equity': str(challenge.current_equity),
                    'last_trade_at': challenge.last_trade_at.isoformat(),
                    'alert_timestamp': now.isoformat(),
                })

                logger.info("Inactive trading alert", extra={
                    'challenge_id': str(challenge.id),
                    'inactive_minutes': inactive_duration.total_seconds() / 60,
                })

    def check_high_activity_challenges(self, session: Session, challenges: List[Challenge]):
        """
        Check for challenges with unusually high trading activity.

        May indicate automated trading or system stress.
        """
        # This would typically analyze trade frequency over time
        # For now, just log high-trade-count challenges
        for challenge in challenges:
            if challenge.total_trades > self.high_activity_threshold:
                logger.warning("High activity challenge detected", extra={
                    'challenge_id': str(challenge.id),
                    'total_trades': challenge.total_trades,
                })

    def check_stale_daily_resets(self, session: Session, challenges: List[Challenge]):
        """
        Check for challenges that haven't had daily resets when they should.

        Ensures daily drawdown calculations remain accurate.
        """
        now = datetime.now(timezone.utc)

        for challenge in challenges:
            # If it's a new day but daily reset hasn't occurred
            if now.date() != challenge.current_date:
                logger.warning("Stale daily reset detected", extra={
                    'challenge_id': str(challenge.id),
                    'current_date': challenge.current_date.isoformat(),
                    'actual_date': now.date().isoformat(),
                })

                # Could emit alert or trigger correction
                # For now, just log for monitoring

    def perform_risk_assessment(self, session: Session, challenges: List[Challenge]):
        """
        Perform adaptive risk scoring for active challenges.

        Uses AI-powered analysis to compute dynamic risk scores based on
        trading patterns, behavior, and performance metrics.

        This is the core of the Risk AI system - runs in background
        to provide enhanced risk intelligence without impacting trading.
        """
        for challenge in challenges:
            try:
                # Load trade history for this challenge
                trades = self._load_challenge_trades(session, challenge.id)

                if not trades:
                    # No trades yet - skip risk assessment
                    continue

                # Perform risk assessment using Risk AI Service
                assessment = self.risk_ai_service.assess_challenge_risk(
                    challenge_id=challenge.id,
                    trader_id=challenge.user_id,
                    trades=trades,
                    challenge_started_at=challenge.started_at or challenge.created_at
                )

                # Persist risk score (will be implemented in next task)
                self._persist_risk_score(session, assessment)

                # Check for alerts based on risk score
                self._check_risk_alerts(assessment)

                logger.info("Risk assessment completed", extra={
                    'challenge_id': str(challenge.id),
                    'risk_score': float(assessment.risk_score.score),
                    'risk_level': assessment.threshold.level.value,
                    'total_trades': len(trades),
                })

            except Exception as e:
                logger.error("Risk assessment failed for challenge", extra={
                    'challenge_id': str(challenge.id),
                    'error': str(e),
                })
                # Continue processing other challenges

    def _load_challenge_trades(self, session: Session, challenge_id) -> List[Dict[str, Any]]:
        """
        Load trade history for a challenge.

        Returns trades in format expected by Risk AI Service.
        """
        # Import Trade model (assuming it exists)
        try:
            from src.domains.trading.model import Trade
            trades_query = session.query(Trade).filter(
                Trade.challenge_id == challenge_id
            ).order_by(Trade.executed_at).all()

            # Convert to dictionaries for Risk AI Service
            return [{
                'trade_id': str(trade.id),
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': trade.quantity,
                'price': trade.price,
                'realized_pnl': trade.realized_pnl,
                'executed_at': trade.executed_at
            } for trade in trades_query]

        except ImportError:
            # Fallback if Trade model not available
            logger.warning("Trade model not available, skipping risk assessment")
            return []

    def _persist_risk_score(self, session: Session, assessment):
        """
        Persist risk score to database.

        Creates audit trail of risk assessments for compliance and analysis.
        Append-only storage ensures complete historical record.
        """
        try:
            risk_score_record = RiskScore(
                challenge_id=assessment.challenge_id,
                user_id=assessment.trader_id,
                risk_score=assessment.risk_score.score,
                risk_level=assessment.threshold.level.value,
                score_breakdown=assessment.risk_score.breakdown,
                feature_summary=assessment.risk_score.breakdown.get('feature_summary', {}),
                assessed_at=assessment.assessed_at,
                assessment_version='1.0',
                action_plan=assessment.action_plan
            )

            session.add(risk_score_record)

            # Note: No explicit commit here - handled by monitoring cycle
            # This ensures all risk assessments are persisted atomically

            logger.debug("Risk score persisted", extra={
                'challenge_id': str(assessment.challenge_id),
                'risk_score': float(assessment.risk_score.score),
                'record_id': str(risk_score_record.id)
            })

        except Exception as e:
            logger.error("Failed to persist risk score", extra={
                'challenge_id': str(assessment.challenge_id),
                'error': str(e)
            })
            # Don't raise - risk assessment should continue even if persistence fails
            # This maintains system availability while logging the issue

    def _check_risk_alerts(self, assessment):
        """
        Check if risk assessment should trigger alerts.

        Emits structured alerts for risk monitoring while maintaining
        clear separation between alerting and core decision logic.

        Alerting is supplementary to core business rules - alerts enhance
        monitoring but don't change challenge outcomes.
        """
        alert_type = self.risk_ai_service.should_emit_alert(
            float(assessment.risk_score.score)
        )

        if alert_type:
            # Create comprehensive alert payload
            alert_payload = self._build_alert_payload(assessment, alert_type)

            # Emit alert event (separate from business logic)
            event_bus.emit('RISK_AI_ALERT', alert_payload)

            # Log alert for operational monitoring
            self._log_risk_alert(assessment, alert_type)

    def _build_alert_payload(self, assessment, alert_type: str) -> dict:
        """
        Build comprehensive alert payload for risk monitoring.

        Includes all relevant information for risk teams to take action
        while maintaining separation from core trading decisions.
        """
        return {
            # Alert identity
            'alert_id': f"risk_ai_{assessment.challenge_id}_{int(assessment.assessed_at.timestamp())}",
            'alert_type': alert_type.upper(),
            'severity': alert_type.upper(),  # WARNING or CRITICAL

            # Context
            'challenge_id': str(assessment.challenge_id),
            'trader_id': str(assessment.trader_id),
            'assessment_timestamp': assessment.assessed_at.isoformat(),

            # Risk assessment results
            'risk_score': float(assessment.risk_score.score),
            'risk_level': assessment.threshold.level.value,
            'score_breakdown': assessment.risk_score.breakdown,

            # Action guidance (computed, not decision logic)
            'action_required': assessment.threshold.action_required,
            'escalation_criteria': assessment.threshold.escalation_criteria,
            'monitoring_frequency': assessment.threshold.monitoring_frequency,

            # Trading context (for risk analysis)
            'trading_context': {
                'total_trades': assessment.features.total_trades,
                'analysis_period_hours': float(assessment.features.analysis_period_hours),
                'win_rate': float(assessment.features.win_rate),
                'avg_trade_pnl': float(assessment.features.avg_trade_pnl),
                'pnl_volatility': float(assessment.features.pnl_volatility),
                'max_intraday_drawdown': float(assessment.features.max_intraday_drawdown),
                'current_loss_streak': assessment.features.loss_streak,
                'trades_per_hour': float(assessment.features.trades_per_hour),
                'overtrading_score': float(assessment.features.overtrading_score),
                'revenge_trading_score': float(assessment.features.revenge_trading_score),
            },

            # Alert metadata
            'alert_source': 'adaptive_risk_ai',
            'alert_version': '1.0',
            'correlation_id': f"challenge_{assessment.challenge_id}",

            # Business impact assessment
            'business_impact': self._assess_business_impact(assessment),

            # Recommended actions (computed guidance)
            'recommended_actions': assessment.action_plan.get('immediate_actions', []),
            'timeline': assessment.action_plan.get('timeline', 'Immediate'),
            'escalation_contacts': assessment.action_plan.get('escalation_contacts', []),
        }

    def _assess_business_impact(self, assessment) -> str:
        """
        Assess potential business impact of the risk level.

        Provides qualitative assessment for risk teams to prioritize response.
        """
        score = float(assessment.risk_score.score)
        level = assessment.threshold.level.value

        if level == 'CRITICAL':
            return 'HIGH_IMPACT'
        elif level == 'HIGH_RISK':
            return 'MODERATE_IMPACT'
        elif level == 'MONITOR':
            return 'LOW_IMPACT'
        else:
            return 'MINIMAL_IMPACT'

    def _log_risk_alert(self, assessment, alert_type: str):
        """
        Log risk alert for operational monitoring.

        Structured logging for alerting dashboards and incident response.
        """
        logger.warning("Adaptive Risk AI Alert Triggered", extra={
            'alert_type': alert_type.upper(),
            'challenge_id': str(assessment.challenge_id),
            'trader_id': str(assessment.trader_id),
            'risk_score': float(assessment.risk_score.score),
            'risk_level': assessment.threshold.level.value,
            'total_trades': assessment.features.total_trades,
            'action_required': assessment.threshold.action_required,
            'assessment_timestamp': assessment.assessed_at.isoformat(),
            # Additional context for operational dashboards
            'win_rate': float(assessment.features.win_rate),
            'max_drawdown': float(assessment.features.max_drawdown),
            'loss_streak': assessment.features.loss_streak,
            'overtrading_score': float(assessment.features.overtrading_score),
        })

    def update_challenge_metrics(self, session: Session, challenges: List[Challenge]):
        """
        Update derived metrics for challenges.

        Calculates and stores metrics that are expensive to compute
        but useful for monitoring and analytics.
        """
        # This could include:
        # - Rolling averages of trade frequency
        # - Risk metrics over time
        # - Performance trends
        # - Pattern analysis

        # For now, just ensure challenges have recent activity timestamps
        now = datetime.now(timezone.utc)

        for challenge in challenges:
            # Could update last_monitored_at or other maintenance fields
            # This is where we'd add derived metrics computation
            pass

    def update_health_check(self):
        """
        Update health check file for Docker health monitoring.

        Touch the file to indicate worker is running successfully.
        """
        try:
            with open(self.health_file, 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.error("Failed to update health check file", exc_info=True)


def main():
    """
    Main entry point for the risk worker.

    Can be run directly or via Docker CMD.
    """
    worker = RiskWorker()
    worker.run()


if __name__ == '__main__':
    main()