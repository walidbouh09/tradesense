"""
Challenge Management API Endpoints

REST endpoints for challenge lifecycle management.
"""

from flask import jsonify, request, current_app
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import uuid
from datetime import datetime, timezone

from . import api_bp


def get_db_session():
    """Get database session."""
    database_url = current_app.config.get('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
    engine = create_engine(database_url, echo=False)
    return Session(engine)


@api_bp.route('/challenges', methods=['GET'])
def list_challenges():
    """
    List challenges for the authenticated user.

    Returns paginated list of user's challenges.
    """
    try:
        session = get_db_session()

        # For demo purposes, return all challenges
        # In production, this would filter by authenticated user
        challenges = session.execute(text("""
            SELECT
                id, user_id, status, initial_balance, current_equity,
                max_equity_ever, started_at, ended_at, last_trade_at,
                created_at, total_trades
            FROM challenges
            ORDER BY created_at DESC
            LIMIT 20
        """)).fetchall()

        challenge_list = []
        for challenge in challenges:
            challenge_list.append({
                'id': str(challenge.id),
                'user_id': str(challenge.user_id),
                'status': challenge.status,
                'initial_balance': float(challenge.initial_balance),
                'current_equity': float(challenge.current_equity),
                'max_equity_ever': float(challenge.max_equity_ever),
                'started_at': challenge.started_at.isoformat() if challenge.started_at else None,
                'ended_at': challenge.ended_at.isoformat() if challenge.ended_at else None,
                'last_trade_at': challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
                'created_at': challenge.created_at.isoformat(),
                'total_trades': challenge.total_trades or 0
            })

        return jsonify({
            'challenges': challenge_list,
            'total': len(challenge_list),
            'page': 1,
            'per_page': 20
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing challenges: {e}")
        return jsonify({'error': 'Failed to list challenges'}), 500
    finally:
        session.close()


@api_bp.route('/challenges', methods=['POST'])
def create_challenge():
    """
    Create a new trading challenge.

    Accepts challenge configuration and creates a new challenge.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract challenge parameters
        initial_balance = data.get('initial_balance', 10000)
        rules = data.get('rules', {})

        max_daily_drawdown = rules.get('max_daily_drawdown', 0.05)
        max_total_drawdown = rules.get('max_total_drawdown', 0.10)
        profit_target = rules.get('profit_target', 0.10)

        # For demo purposes, use the admin user
        # In production, this would come from JWT authentication
        user_id = '550e8400-e29b-41d4-a716-446655440000'  # admin user

        session = get_db_session()

        # Create the challenge
        challenge_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        session.execute(text("""
            INSERT INTO challenges (
                id, user_id, initial_balance, max_daily_drawdown_percent,
                max_total_drawdown_percent, profit_target_percent,
                current_equity, max_equity_ever, daily_start_equity,
                daily_max_equity, daily_min_equity, current_date_value,
                status, created_at, updated_at
            ) VALUES (
                :id, :user_id, :initial_balance, :max_daily_drawdown,
                :max_total_drawdown, :profit_target,
                :initial_balance, :initial_balance, :initial_balance,
                :initial_balance, :initial_balance, :current_date,
                'PENDING', :created_at, :updated_at
            )
        """), {
            'id': challenge_id,
            'user_id': user_id,
            'initial_balance': initial_balance,
            'max_daily_drawdown': max_daily_drawdown,
            'max_total_drawdown': max_total_drawdown,
            'profit_target': profit_target,
            'current_date': now.date(),
            'created_at': now,
            'updated_at': now
        })

        session.commit()

        # Return the created challenge
        return jsonify({
            'id': challenge_id,
            'user_id': user_id,
            'status': 'PENDING',
            'initial_balance': initial_balance,
            'current_equity': initial_balance,
            'max_equity_ever': initial_balance,
            'created_at': now.isoformat(),
            'rules': {
                'max_daily_drawdown': max_daily_drawdown,
                'max_total_drawdown': max_total_drawdown,
                'profit_target': profit_target
            }
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error creating challenge: {e}")
        session.rollback()
        return jsonify({'error': 'Failed to create challenge'}), 500
    finally:
        session.close()


@api_bp.route('/challenges/<challenge_id>', methods=['GET'])
def get_challenge(challenge_id):
    """
    Get detailed information about a specific challenge.

    Returns challenge details including current status and metrics.
    """
    try:
        session = get_db_session()

        # Get challenge details
        challenge = session.execute(text("""
            SELECT
                c.id, c.user_id, c.status, c.initial_balance, c.current_equity,
                c.max_equity_ever, c.started_at, c.ended_at, c.last_trade_at,
                c.created_at, c.total_trades, c.win_rate, c.avg_trade_pnl,
                c.max_daily_drawdown_percent, c.max_total_drawdown_percent, c.profit_target_percent
            FROM challenges c
            WHERE c.id = :challenge_id
        """), {'challenge_id': challenge_id}).fetchone()

        if not challenge:
            return jsonify({'error': 'Challenge not found'}), 404

        # Get recent trades
        trades = session.execute(text("""
            SELECT
                id, symbol, side, quantity, price, realized_pnl, executed_at
            FROM trades
            WHERE challenge_id = :challenge_id
            ORDER BY executed_at DESC
            LIMIT 10
        """), {'challenge_id': challenge_id}).fetchall()

        trade_list = []
        for trade in trades:
            trade_list.append({
                'trade_id': str(trade.id),
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': float(trade.quantity),
                'price': float(trade.price),
                'realized_pnl': float(trade.realized_pnl),
                'executed_at': trade.executed_at.isoformat()
            })

        return jsonify({
            'id': str(challenge.id),
            'user_id': str(challenge.user_id),
            'status': challenge.status,
            'initial_balance': float(challenge.initial_balance),
            'current_equity': float(challenge.current_equity),
            'max_equity_ever': float(challenge.max_equity_ever),
            'started_at': challenge.started_at.isoformat() if challenge.started_at else None,
            'ended_at': challenge.ended_at.isoformat() if challenge.ended_at else None,
            'last_trade_at': challenge.last_trade_at.isoformat() if challenge.last_trade_at else None,
            'created_at': challenge.created_at.isoformat(),
            'total_trades': challenge.total_trades or 0,
            'win_rate': float(challenge.win_rate) if challenge.win_rate else 0,
            'avg_trade_pnl': float(challenge.avg_trade_pnl) if challenge.avg_trade_pnl else 0,
            'rules': {
                'max_daily_drawdown': float(challenge.max_daily_drawdown_percent),
                'max_total_drawdown': float(challenge.max_total_drawdown_percent),
                'profit_target': float(challenge.profit_target_percent)
            },
            'trades': trade_list
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting challenge {challenge_id}: {e}")
        return jsonify({'error': 'Failed to get challenge'}), 500
    finally:
        session.close()