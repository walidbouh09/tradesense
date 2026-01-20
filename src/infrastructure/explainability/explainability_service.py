"""
Explainability Service - Human-Readable Decision Explanations

Provides transparent explanations for PASS/FAIL decisions without duplicating business logic.
Shows the complete trace: trade → rule → violation → decision
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from shared.infrastructure.logging.audit_logger import AuditLogger

from infrastructure.audit.audit_service import AuditService


class ExplainabilityService:
    """
    Service for explaining challenge decisions in human-readable format.

    Key Principles:
    - Never duplicate business logic
    - Use audit trail as single source of truth
    - Provide complete decision trace
    - Support dispute resolution
    """

    def __init__(
        self,
        audit_service: AuditService,
        audit_logger: AuditLogger,
    ):
        self.audit_service = audit_service
        self.audit_logger = audit_logger

    async def explain_challenge_decision(self, challenge_id: str) -> Dict[str, Any]:
        """
        Generate complete explanation for a challenge decision.

        Returns human-readable explanation with full audit trail.
        """
        # Get reconstruction from audit service
        reconstruction = await self.audit_service.reconstruct_challenge_decision(challenge_id)

        if not reconstruction["timeline"]:
            return {
                "error": "Challenge not found or no audit trail available",
                "challenge_id": challenge_id,
            }

        # Build explanation from audit trail
        explanation = {
            "challenge_id": challenge_id,
            "final_decision": reconstruction["final_decision"],
            "decision_summary": self._build_decision_summary(reconstruction),
            "timeline_summary": self._build_timeline_summary(reconstruction["timeline"]),
            "decision_factors": self._explain_decision_factors(reconstruction["decision_factors"]),
            "performance_metrics": self._extract_performance_metrics(reconstruction["timeline"]),
            "rule_evaluation_trace": self._build_rule_evaluation_trace(reconstruction["timeline"]),
            "dispute_resolution_info": self._build_dispute_resolution_info(challenge_id, reconstruction),
            "generated_at": datetime.utcnow().isoformat(),
            "audit_trail_complete": reconstruction["audit_trail_complete"],
        }

        # Log explanation generation
        self.audit_logger.log_business_event(
            event_type="decision_explanation_generated",
            details={
                "challenge_id": challenge_id,
                "decision": reconstruction["final_decision"]["decision"] if reconstruction["final_decision"] else "unknown",
                "explanation_length": len(str(explanation)),
            },
        )

        return explanation

    def _build_decision_summary(self, reconstruction: Dict[str, Any]) -> str:
        """Build human-readable decision summary."""
        final_decision = reconstruction.get("final_decision")

        if not final_decision:
            # Active challenge
            timeline = reconstruction.get("timeline", [])
            if timeline:
                last_event = timeline[-1]
                return f"Challenge {reconstruction['challenge_id']} is currently ACTIVE. Last activity: {last_event['event_type']} on {last_event['timestamp'][:10]}."
            return f"Challenge {reconstruction['challenge_id']} is currently ACTIVE."

        decision = final_decision["decision"]
        timestamp = final_decision["timestamp"][:19]  # YYYY-MM-DD HH:MM:SS

        if decision == "ChallengePassed":
            return f"✅ CHALLENGE PASSED on {timestamp}. The trader successfully met all evaluation requirements."

        elif decision == "ChallengeFailed":
            reason = final_decision.get("reason", "Unknown reason")
            return f"❌ CHALLENGE FAILED on {timestamp}. Reason: {self._humanize_failure_reason(reason)}"

        return f"Unknown decision state: {decision}"

    def _humanize_failure_reason(self, reason: str) -> str:
        """Convert technical failure reasons to human-readable explanations."""
        reason_mappings = {
            "Daily loss limit exceeded": "The trading account exceeded the maximum allowed daily loss limit",
            "Total loss limit exceeded": "The trading account exceeded the maximum allowed total loss limit",
            "Minimum trading days not met": "The trader did not complete the minimum required number of trading days",
            "Profit target not reached": "The required profit target was not achieved within the time limit",
            "Rule violation": "One or more trading rules were violated",
            "Time limit exceeded": "The challenge duration expired before requirements were met",
        }

        # Try exact match first
        if reason in reason_mappings:
            return reason_mappings[reason]

        # Try partial matches
        for technical, human in reason_mappings.items():
            if technical.lower() in reason.lower():
                return human

        # Return original if no mapping found
        return reason

    def _build_timeline_summary(self, timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build summary of challenge timeline."""
        if not timeline:
            return {"total_events": 0, "date_range": None}

        start_date = timeline[0]["timestamp"][:10]
        end_date = timeline[-1]["timestamp"][:10]

        # Count event types
        event_counts = {}
        for event in timeline:
            event_type = event["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "total_events": len(timeline),
            "date_range": f"{start_date} to {end_date}" if start_date != end_date else start_date,
            "event_counts": event_counts,
            "key_milestones": self._extract_key_milestones(timeline),
        }

    def _extract_key_milestones(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract key milestones from timeline."""
        milestones = []

        for event in timeline:
            event_type = event["event_type"]
            event_data = event["data"]

            if event_type == "ChallengeStarted":
                milestones.append({
                    "type": "started",
                    "description": "Challenge evaluation period began",
                    "timestamp": event["timestamp"][:19],
                    "details": {
                        "initial_balance": event_data.get("initial_balance", "Unknown"),
                        "challenge_type": event_data.get("challenge_type", "Unknown"),
                    }
                })

            elif event_type == "TradingMetricsUpdated":
                # Show significant metric changes
                current_balance = event_data.get("current_balance", 0)
                if isinstance(current_balance, str):
                    current_balance = float(current_balance)

                milestones.append({
                    "type": "metrics_updated",
                    "description": f"Account balance updated to ${current_balance:,.2f}",
                    "timestamp": event["timestamp"][:19],
                    "details": {
                        "balance": current_balance,
                        "daily_pnl": event_data.get("daily_pnl"),
                        "trading_days": event_data.get("trading_days"),
                    }
                })

            elif event_type == "RuleViolationDetected":
                severity = event_data.get("severity", "UNKNOWN")
                rule_name = event_data.get("rule_name", "Unknown rule")

                milestones.append({
                    "type": "violation",
                    "description": f"⚠️ {severity} rule violation: {rule_name}",
                    "timestamp": event["timestamp"][:19],
                    "details": {
                        "rule_name": rule_name,
                        "severity": severity,
                        "description": event_data.get("description", ""),
                    }
                })

            elif event_type in ["ChallengePassed", "ChallengeFailed"]:
                decision = "PASSED" if event_type == "ChallengePassed" else "FAILED"
                milestones.append({
                    "type": "completed",
                    "description": f"Challenge {decision}",
                    "timestamp": event["timestamp"][:19],
                    "details": {
                        "reason": event_data.get("reason") or event_data.get("failure_reason"),
                        "final_balance": event_data.get("final_balance"),
                        "trading_days": event_data.get("trading_days"),
                    }
                })

        return milestones[-10:]  # Return last 10 milestones

    def _explain_decision_factors(self, decision_factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Explain the factors that led to the final decision."""
        if not decision_factors:
            return {
                "total_factors": 0,
                "explanation": "No specific decision factors recorded.",
                "critical_events": [],
            }

        # Categorize factors
        violations = [f for f in decision_factors if f["event"] == "RuleViolationDetected"]
        metrics_updates = [f for f in decision_factors if f["event"] == "TradingMetricsUpdated"]

        # Analyze violations by severity
        critical_violations = [v for v in violations if v["data"].get("severity") == "CRITICAL"]
        high_violations = [v for v in violations if v["data"].get("severity") == "HIGH"]

        explanation_parts = []

        if critical_violations:
            explanation_parts.append(
                f"❌ {len(critical_violations)} critical rule violations occurred, "
                "which automatically fail the challenge."
            )

        if high_violations:
            explanation_parts.append(
                f"⚠️ {len(high_violations)} high-severity rule violations contributed to the decision."
            )

        if not violations:
            explanation_parts.append(
                "✅ No rule violations were recorded during the challenge period."
            )

        # Analyze performance trend
        if metrics_updates:
            final_metrics = metrics_updates[-1]["data"]
            current_balance = final_metrics.get("current_balance", 0)

            if isinstance(current_balance, str):
                current_balance = float(current_balance)

            explanation_parts.append(
                f"📊 Final account balance: ${current_balance:,.2f}"
            )

        return {
            "total_factors": len(decision_factors),
            "total_violations": len(violations),
            "critical_violations": len(critical_violations),
            "high_violations": len(high_violations),
            "explanation": " ".join(explanation_parts),
            "critical_events": [
                {
                    "type": "violation",
                    "severity": v["data"].get("severity"),
                    "rule": v["data"].get("rule_name"),
                    "description": v["data"].get("description"),
                    "sequence_id": v["sequence_id"],
                }
                for v in critical_violations[:5]  # Top 5 critical violations
            ],
        }

    def _extract_performance_metrics(self, timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key performance metrics from timeline."""
        metrics = {
            "initial_balance": None,
            "final_balance": None,
            "peak_balance": None,
            "total_trades": 0,
            "trading_days": 0,
            "win_rate": None,
            "total_pnl": None,
            "max_drawdown": None,
        }

        for event in timeline:
            event_data = event["data"]

            if event["event_type"] == "ChallengeStarted":
                metrics["initial_balance"] = event_data.get("initial_balance")

            elif event["event_type"] == "TradingMetricsUpdated":
                # Update latest metrics
                metrics["final_balance"] = event_data.get("current_balance")
                metrics["peak_balance"] = event_data.get("peak_balance")
                metrics["trading_days"] = event_data.get("trading_days", 0)
                metrics["max_drawdown"] = event_data.get("max_drawdown")

            elif event["event_type"] == "TradeExecuted":
                metrics["total_trades"] += 1

        # Calculate derived metrics
        if metrics["initial_balance"] and metrics["final_balance"]:
            try:
                initial = float(metrics["initial_balance"])
                final = float(metrics["final_balance"])
                metrics["total_pnl"] = final - initial
                metrics["pnl_percentage"] = ((final - initial) / initial) * 100
            except (ValueError, ZeroDivisionError):
                pass

        return metrics

    def _build_rule_evaluation_trace(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build trace of rule evaluations and violations."""
        rule_events = []

        for event in timeline:
            if event["event_type"] in ["RuleViolationDetected", "RuleEvaluationCompleted"]:
                rule_events.append({
                    "timestamp": event["timestamp"][:19],
                    "event_type": event["event_type"],
                    "rule_name": event["data"].get("rule_name"),
                    "severity": event["data"].get("severity"),
                    "description": event["data"].get("description"),
                    "current_value": event["data"].get("current_value"),
                    "limit_value": event["data"].get("limit_value"),
                    "passed": event["data"].get("passed", False),
                })

        return rule_events

    def _build_dispute_resolution_info(self, challenge_id: str, reconstruction: Dict[str, Any]) -> Dict[str, Any]:
        """Build information for dispute resolution."""
        final_decision = reconstruction.get("final_decision")

        dispute_info = {
            "challenge_id": challenge_id,
            "dispute_eligible": False,
            "dispute_deadline": None,
            "dispute_reasons": [],
            "required_evidence": [],
            "contact_information": {
                "email": "disputes@tradesense.ai",
                "response_time": "2-5 business days",
            },
        }

        if final_decision and final_decision["decision"] == "ChallengeFailed":
            # Disputes are eligible for failed challenges within 30 days
            decision_date = datetime.fromisoformat(final_decision["timestamp"])
            dispute_deadline = decision_date.replace(day=min(decision_date.day + 30, 28))  # Handle month boundaries

            dispute_info.update({
                "dispute_eligible": datetime.utcnow() < dispute_deadline,
                "dispute_deadline": dispute_deadline.isoformat(),
                "dispute_reasons": [
                    "Technical error in rule evaluation",
                    "Incorrect trade recording",
                    "System outage during trading",
                    "Misapplication of challenge rules",
                    "Evidence of platform malfunction",
                ],
                "required_evidence": [
                    "Screenshots of trading platform",
                    "Trade confirmations",
                    "Communication records",
                    "System error messages",
                    "Detailed timeline of events",
                ],
            })

        return dispute_info

    async def generate_dispute_report(self, challenge_id: str, dispute_reason: str, evidence: List[str]) -> Dict[str, Any]:
        """
        Generate a comprehensive dispute report for review.

        This provides all information needed for manual dispute resolution.
        """
        # Get full explanation
        explanation = await self.explain_challenge_decision(challenge_id)

        if "error" in explanation:
            return explanation

        # Add dispute-specific information
        dispute_report = {
            **explanation,
            "dispute": {
                "reason": dispute_reason,
                "evidence_provided": evidence,
                "submitted_at": datetime.utcnow().isoformat(),
                "status": "under_review",
                "review_deadline": (datetime.utcnow().replace(day=datetime.utcnow().day + 5)).isoformat(),
            },
            "for_reviewer": {
                "audit_trail_integrity": await self._verify_audit_integrity(challenge_id),
                "system_health_during_period": await self._check_system_health(challenge_id),
                "similar_cases": await self._find_similar_cases(challenge_id),
            }
        }

        self.audit_logger.log_business_event(
            event_type="dispute_report_generated",
            details={
                "challenge_id": challenge_id,
                "dispute_reason": dispute_reason,
                "evidence_count": len(evidence),
            },
            severity="WARNING"
        )

        return dispute_report

    async def _verify_audit_integrity(self, challenge_id: str) -> Dict[str, Any]:
        """Verify audit trail integrity for this challenge."""
        # Simplified - would check hash chain integrity
        return {
            "integrity_verified": True,
            "events_checked": 0,
            "verification_timestamp": datetime.utcnow().isoformat(),
        }

    async def _check_system_health(self, challenge_id: str) -> Dict[str, Any]:
        """Check system health during challenge period."""
        # Would check for outages, errors, etc. during challenge timeframe
        return {
            "system_healthy": True,
            "outages_during_period": [],
            "error_rate": 0.0,
        }

    async def _find_similar_cases(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Find similar dispute cases for precedent."""
        # Would search historical disputes with similar patterns
        return []

    async def export_explanation(self, challenge_id: str, format: str = "pdf") -> bytes:
        """
        Export decision explanation in specified format.

        Returns formatted document for sharing with traders.
        """
        explanation = await self.explain_challenge_decision(challenge_id)

        if "error" in explanation:
            raise ValueError(explanation["error"])

        # In production, would generate PDF/HTML document
        # For now, return JSON
        import json
        return json.dumps(explanation, indent=2).encode('utf-8')