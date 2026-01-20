"""
Risk Monitoring API Endpoints

Deterministic, rule-based risk monitoring derived from real challenge + trade data.

Exposes:
- GET /api/risk/summary
- GET /api/risk/alerts
"""

from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from datetime import datetime, timezone, timedelta

from . import api_bp


def get_db_session():
    """Get database session."""
    database_url = current_app.config.get('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
    engine = create_engine(database_url, echo=False)
    return Session(engine)


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _pct(numer: float, denom: float) -> float:
    if denom == 0:
        return 0.0
    return (numer / denom) * 100.0


def _stddev(values: list[float]) -> float:
    # Population stddev (deterministic, simple, no numpy dependency)
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return var ** 0.5


def _compute_challenge_metrics(session: Session, challenge_row, now: datetime) -> dict:
    """
    Compute deterministic risk metrics for a single challenge using real DB data.

    Metrics:
    - drawdown_pct: based on max_equity_ever vs current_equity
    - trade_frequency_24h: trades per hour over last 24 hours
    - equity_volatility: stddev of per-trade PnL as % of initial balance over last N trades
    """
    challenge_id = str(challenge_row.id)
    initial_balance = _safe_float(challenge_row.initial_balance, 0.0)
    current_equity = _safe_float(challenge_row.current_equity, 0.0)
    max_equity_ever = _safe_float(challenge_row.max_equity_ever, initial_balance or 1.0)

    # Drawdown percent from peak
    drawdown_pct = _pct(max_equity_ever - current_equity, max_equity_ever if max_equity_ever > 0 else (initial_balance or 1.0))

    # Trade frequency over last 24h
    since = now - timedelta(hours=24)
    trade_count_24h = session.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM trades
        WHERE challenge_id = :cid
          AND executed_at >= :since
    """), {"cid": challenge_id, "since": since}).scalar() or 0
    trade_frequency_24h = float(trade_count_24h) / 24.0  # trades/hour

    # Equity volatility proxy: stddev of pnl% over last N trades
    # Deterministic and derived from real trade PnL.
    recent_pnls = session.execute(text("""
        SELECT realized_pnl
        FROM trades
        WHERE challenge_id = :cid
        ORDER BY executed_at DESC
        LIMIT 30
    """), {"cid": challenge_id}).fetchall()
    pnl_pct_series = []
    denom = initial_balance if initial_balance > 0 else 1.0
    for row in reversed(recent_pnls):
        pnl_pct_series.append(_pct(_safe_float(row.realized_pnl, 0.0), denom))
    equity_volatility = _stddev(pnl_pct_series)

    return {
        "challenge_id": challenge_id,
        "user_id": str(challenge_row.user_id),
        "status": challenge_row.status,
        "current_equity": current_equity,
        "initial_balance": initial_balance,
        "drawdown_pct": round(drawdown_pct, 2),
        "trade_frequency_per_hour_24h": round(trade_frequency_24h, 3),
        "equity_volatility": round(equity_volatility, 4),
        "as_of": now.isoformat(),
        "last_trade_at": challenge_row.last_trade_at.isoformat() if challenge_row.last_trade_at else None,
    }


def _derive_alerts(metrics: dict) -> list[dict]:
    """
    Deterministic rule-based alerts derived from computed metrics.
    """
    alerts: list[dict] = []
    cid = metrics["challenge_id"]

    drawdown = metrics["drawdown_pct"]
    freq = metrics["trade_frequency_per_hour_24h"]
    vol = metrics["equity_volatility"]

    # Drawdown alerts (peak-to-current)
    if drawdown >= 9.5:
        alerts.append({
            "id": f"{cid}-drawdown-critical",
            "challenge_id": cid,
            "alert_type": "DRAWDOWN",
            "severity": "CRITICAL",
            "title": "Critical drawdown",
            "message": f"Drawdown is {drawdown:.2f}% from peak equity.",
            "created_at": metrics["as_of"],
        })
    elif drawdown >= 8.0:
        alerts.append({
            "id": f"{cid}-drawdown-high",
            "challenge_id": cid,
            "alert_type": "DRAWDOWN",
            "severity": "HIGH",
            "title": "High drawdown",
            "message": f"Drawdown is {drawdown:.2f}% from peak equity.",
            "created_at": metrics["as_of"],
        })
    elif drawdown >= 5.0:
        alerts.append({
            "id": f"{cid}-drawdown-medium",
            "challenge_id": cid,
            "alert_type": "DRAWDOWN",
            "severity": "MEDIUM",
            "title": "Drawdown warning",
            "message": f"Drawdown is {drawdown:.2f}% from peak equity.",
            "created_at": metrics["as_of"],
        })

    # Trade frequency alerts (overtrading proxy)
    # 2 trades/hour ~= 48/day (aggressive); 4/hour ~= 96/day
    if freq >= 4.0:
        alerts.append({
            "id": f"{cid}-freq-critical",
            "challenge_id": cid,
            "alert_type": "TRADE_FREQUENCY",
            "severity": "CRITICAL",
            "title": "Extreme trading frequency",
            "message": f"Trade frequency is {freq:.2f} trades/hour (24h window).",
            "created_at": metrics["as_of"],
        })
    elif freq >= 2.0:
        alerts.append({
            "id": f"{cid}-freq-high",
            "challenge_id": cid,
            "alert_type": "TRADE_FREQUENCY",
            "severity": "HIGH",
            "title": "High trading frequency",
            "message": f"Trade frequency is {freq:.2f} trades/hour (24h window).",
            "created_at": metrics["as_of"],
        })
    elif freq >= 1.0:
        alerts.append({
            "id": f"{cid}-freq-medium",
            "challenge_id": cid,
            "alert_type": "TRADE_FREQUENCY",
            "severity": "MEDIUM",
            "title": "Elevated trading frequency",
            "message": f"Trade frequency is {freq:.2f} trades/hour (24h window).",
            "created_at": metrics["as_of"],
        })

    # Volatility alerts (stddev of pnl% over last 30 trades)
    # These thresholds are intentionally simple and deterministic.
    if vol >= 1.50:
        alerts.append({
            "id": f"{cid}-vol-critical",
            "challenge_id": cid,
            "alert_type": "EQUITY_VOLATILITY",
            "severity": "CRITICAL",
            "title": "Extreme equity volatility",
            "message": f"Equity volatility (stddev of trade PnL%) is {vol:.2f}.",
            "created_at": metrics["as_of"],
        })
    elif vol >= 1.00:
        alerts.append({
            "id": f"{cid}-vol-high",
            "challenge_id": cid,
            "alert_type": "EQUITY_VOLATILITY",
            "severity": "HIGH",
            "title": "High equity volatility",
            "message": f"Equity volatility (stddev of trade PnL%) is {vol:.2f}.",
            "created_at": metrics["as_of"],
        })
    elif vol >= 0.60:
        alerts.append({
            "id": f"{cid}-vol-medium",
            "challenge_id": cid,
            "alert_type": "EQUITY_VOLATILITY",
            "severity": "MEDIUM",
            "title": "Elevated equity volatility",
            "message": f"Equity volatility (stddev of trade PnL%) is {vol:.2f}.",
            "created_at": metrics["as_of"],
        })
    elif vol >= 0.30:
        alerts.append({
            "id": f"{cid}-vol-low",
            "challenge_id": cid,
            "alert_type": "EQUITY_VOLATILITY",
            "severity": "LOW",
            "title": "Slightly elevated volatility",
            "message": f"Equity volatility (stddev of trade PnL%) is {vol:.2f}.",
            "created_at": metrics["as_of"],
        })

    return alerts


@api_bp.route('/risk/summary', methods=['GET'])
def get_risk_summary():
    """
    Risk summary computed from real challenge + trade data.

    Returns aggregate metrics and per-challenge metrics for ACTIVE/PENDING challenges.
    """
    session = None
    try:
        session = get_db_session()
        now = datetime.now(timezone.utc)

        challenges = session.execute(text("""
            SELECT
                id,
                user_id,
                status,
                initial_balance,
                current_equity,
                max_equity_ever,
                last_trade_at
            FROM challenges
            WHERE status IN ('PENDING', 'ACTIVE')
            ORDER BY created_at DESC
        """)).fetchall()

        per_challenge = []
        all_alerts = []

        for c in challenges:
            metrics = _compute_challenge_metrics(session, c, now)
            per_challenge.append(metrics)
            all_alerts.extend(_derive_alerts(metrics))

        critical_alerts = sum(1 for a in all_alerts if a["severity"] == "CRITICAL")
        high_alerts = sum(1 for a in all_alerts if a["severity"] == "HIGH")

        # Aggregate metrics
        if per_challenge:
            avg_drawdown = sum(m["drawdown_pct"] for m in per_challenge) / len(per_challenge)
            avg_freq = sum(m["trade_frequency_per_hour_24h"] for m in per_challenge) / len(per_challenge)
            avg_vol = sum(m["equity_volatility"] for m in per_challenge) / len(per_challenge)
        else:
            avg_drawdown = avg_freq = avg_vol = 0.0

        return jsonify({
            "generated_at": now.isoformat(),
            "active_challenges": len(per_challenge),
            "total_alerts": len(all_alerts),
            "critical_alerts": critical_alerts,
            "high_alerts": high_alerts,
            "avg_drawdown_pct": round(avg_drawdown, 2),
            "avg_trade_frequency_per_hour_24h": round(avg_freq, 3),
            "avg_equity_volatility": round(avg_vol, 4),
            "challenges": per_challenge,
        }), 200

    except Exception as e:
        current_app.logger.error(f"Risk summary error: {e}", exc_info=True)
        return jsonify({"error": "Failed to get risk summary"}), 500
    finally:
        if session is not None:
            session.close()


@api_bp.route('/risk/scores', methods=['GET'])
def get_risk_scores():
    """
    Get risk scores for challenges.

    Returns current risk assessment for all active challenges.
    """
    try:
        session = get_db_session()

        # NOTE: kept for backward compatibility with older UI surfaces.
        # This endpoint is NOT used by the new deterministic risk dashboard.
        # Get all active challenges with trading stats
        challenges = session.execute(text("""
            SELECT
                c.id, c.user_id, c.current_equity, c.initial_balance,
                c.total_trades, c.win_rate, c.avg_trade_pnl,
                c.max_daily_drawdown_percent, c.max_total_drawdown_percent,
                c.profit_target_percent
            FROM challenges c
            WHERE c.status = 'ACTIVE'
        """)).fetchall()

        risk_scores = []
        for challenge in challenges:
            # Deterministic placeholder score derived from drawdown + frequency + volatility
            now = datetime.now(timezone.utc)
            metrics = _compute_challenge_metrics(session, challenge, now)
            # Simple deterministic score: drawdown + 10*freq + 5*vol (clamped 0-100)
            score = metrics["drawdown_pct"] + (metrics["trade_frequency_per_hour_24h"] * 10.0) + (metrics["equity_volatility"] * 5.0)
            score = max(0.0, min(100.0, score))

            risk_scores.append({
                'challenge_id': str(challenge.id),
                'user_id': str(challenge.user_id),
                'score': round(score, 2),
                'level': 'CRITICAL' if score >= 80 else 'HIGH_RISK' if score >= 60 else 'MONITOR' if score >= 30 else 'STABLE',
                'breakdown': {
                    'components': {
                        'drawdown_pct': metrics["drawdown_pct"],
                        'trade_frequency_per_hour_24h': metrics["trade_frequency_per_hour_24h"],
                        'equity_volatility': metrics["equity_volatility"],
                    },
                    'total_score': round(score, 2),
                    'feature_summary': {
                        'current_equity': metrics["current_equity"],
                        'initial_balance': metrics["initial_balance"],
                        'last_trade_at': metrics["last_trade_at"],
                    }
                },
                'computed_at': now.isoformat()
            })

        return jsonify(risk_scores), 200

    except Exception as e:
        current_app.logger.error(f"Risk scores error: {e}")
        return jsonify({'error': 'Failed to get risk scores'}), 500
    finally:
        session.close()


@api_bp.route('/risk/alerts', methods=['GET'])
def get_risk_alerts():
    """
    Get active risk alerts.

    Returns current alerts that need attention.
    """
    try:
        session = get_db_session()

        now = datetime.now(timezone.utc)

        # Derive alerts from real challenge + trade data (no demo data, no randomness)
        challenges = session.execute(text("""
            SELECT
                id,
                user_id,
                status,
                initial_balance,
                current_equity,
                max_equity_ever,
                last_trade_at
            FROM challenges
            WHERE status IN ('PENDING', 'ACTIVE')
            ORDER BY created_at DESC
        """)).fetchall()

        alert_list = []
        for c in challenges:
            metrics = _compute_challenge_metrics(session, c, now)
            alert_list.extend(_derive_alerts(metrics))

        # Most recent first
        alert_list.sort(key=lambda a: a.get("created_at") or "", reverse=True)

        return jsonify(alert_list[:100]), 200

    except Exception as e:
        current_app.logger.error(f"Risk alerts error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get risk alerts'}), 500
    finally:
        session.close()