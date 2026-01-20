"""
User Profiles Service

Manages user profiles, statistics, achievements, and preferences.
"""

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, desc, func
import logging

logger = logging.getLogger(__name__)


class UserProfileService:
    """
    Service for managing user profiles and trading statistics.

    Provides comprehensive user data including performance metrics,
    achievements, preferences, and trading history summaries.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
        self.engine = create_engine(self.database_url, echo=False)

    def get_user_profile(self, user_id: str) -> Dict:
        """
        Get complete user profile with statistics.

        Args:
            user_id: User ID to get profile for

        Returns:
            Complete user profile data
        """
        with Session(self.engine) as session:
            try:
                # Get basic user info
                user_info = session.execute(text("""
                    SELECT id, email, created_at, updated_at, role
                    FROM users
                    WHERE id = :user_id AND deleted_at IS NULL
                """), {'user_id': user_id}).fetchone()

                if not user_info:
                    return {'error': 'User not found'}

                # Get comprehensive trading statistics
                trading_stats = self._get_trading_statistics(session, user_id)

                # Get achievements
                achievements = self._get_user_achievements(session, user_id)

                # Get current active challenges
                active_challenges = self._get_active_challenges(session, user_id)

                # Get recent activity
                recent_activity = self._get_recent_activity(session, user_id)

                # Get risk metrics
                risk_metrics = self._get_risk_metrics(session, user_id)

                # Get leaderboard position
                from app.leaderboard import leaderboard_service
                rankings = leaderboard_service.get_user_rankings(user_id)

                profile = {
                    'user_id': str(user_info.id),
                    'email': user_info.email,
                    'joined_at': user_info.created_at.isoformat(),
                    'last_updated': user_info.updated_at.isoformat() if user_info.updated_at else None,
                    'role': user_info.role,
                    'trading_stats': trading_stats,
                    'achievements': achievements,
                    'active_challenges': active_challenges,
                    'recent_activity': recent_activity,
                    'risk_metrics': risk_metrics,
                    'rankings': rankings.get('rankings', {}),
                    'preferences': self._get_user_preferences(user_id),  # Mock for now
                    'account_status': 'active',
                    'profile_completeness': self._calculate_profile_completeness(trading_stats)
                }

                return profile

            except Exception as e:
                logger.error(f"Error getting user profile for {user_id}: {e}")
                return {'error': str(e)}

    def _get_trading_statistics(self, session: Session, user_id: str) -> Dict:
        """Get comprehensive trading statistics for a user."""
        try:
            stats = session.execute(text("""
                SELECT
                    -- Challenge statistics
                    COUNT(DISTINCT c.id) as total_challenges,
                    COUNT(DISTINCT CASE WHEN c.status = 'PENDING' THEN c.id END) as pending_challenges,
                    COUNT(DISTINCT CASE WHEN c.status = 'ACTIVE' THEN c.id END) as active_challenges,
                    COUNT(DISTINCT CASE WHEN c.status = 'FAILED' THEN c.id END) as failed_challenges,
                    COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as funded_challenges,

                    -- Financial performance
                    COALESCE(SUM(CASE WHEN c.status IN ('ACTIVE', 'FUNDED') THEN c.current_equity END), 0) as total_equity,
                    COALESCE(SUM(CASE WHEN c.status IN ('ACTIVE', 'FUNDED') THEN c.initial_balance END), 0) as total_invested,
                    COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as total_realized_pnl,
                    COALESCE(MAX(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as best_trade,
                    COALESCE(MIN(CASE WHEN c.status = 'FAILED' THEN c.current_equity - c.initial_balance END), 0) as worst_trade,

                    -- Trading activity
                    COUNT(t.id) as total_trades,
                    COUNT(CASE WHEN t.realized_pnl > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN t.realized_pnl < 0 THEN 1 END) as losing_trades,

                    -- Performance ratios
                    COALESCE(AVG(CASE WHEN c.status = 'FUNDED' THEN (c.current_equity - c.initial_balance) / c.initial_balance END), 0) as avg_return_on_success,
                    COALESCE(AVG(t.realized_pnl), 0) as avg_trade_pnl,

                    -- Time-based metrics
                    MAX(c.last_trade_at) as last_trade_date,
                    MIN(c.started_at) as first_challenge_date,
                    EXTRACT(EPOCH FROM (NOW() - MIN(c.started_at))) / 86400 as trading_days

                FROM challenges c
                LEFT JOIN trades t ON c.id = t.challenge_id
                WHERE c.user_id = :user_id
                GROUP BY c.user_id
            """), {'user_id': user_id}).fetchone()

            if not stats:
                return self._get_empty_stats()

            # Calculate derived metrics
            win_rate = (stats.winning_trades / stats.total_trades * 100) if stats.total_trades > 0 else 0
            success_rate = (stats.funded_challenges / stats.total_challenges * 100) if stats.total_challenges > 0 else 0
            total_pnl = float(stats.total_realized_pnl)
            total_return_pct = (total_pnl / stats.total_invested * 100) if stats.total_invested > 0 else 0

            return {
                'challenges': {
                    'total': stats.total_challenges,
                    'pending': stats.pending_challenges,
                    'active': stats.active_challenges,
                    'failed': stats.failed_challenges,
                    'funded': stats.funded_challenges,
                    'success_rate': round(success_rate, 1)
                },
                'financial': {
                    'total_equity': float(stats.total_equity),
                    'total_invested': float(stats.total_invested),
                    'total_realized_pnl': total_pnl,
                    'total_return_pct': round(total_return_pct, 1),
                    'best_trade': float(stats.best_trade),
                    'worst_trade': float(stats.worst_trade),
                    'avg_return_on_success': round(float(stats.avg_return_on_success) * 100, 1)
                },
                'trading': {
                    'total_trades': stats.total_trades,
                    'winning_trades': stats.winning_trades,
                    'losing_trades': stats.losing_trades,
                    'win_rate': round(win_rate, 1),
                    'avg_trade_pnl': round(float(stats.avg_trade_pnl), 2)
                },
                'activity': {
                    'last_trade_date': stats.last_trade_date.isoformat() if stats.last_trade_date else None,
                    'first_challenge_date': stats.first_challenge_date.isoformat() if stats.first_challenge_date else None,
                    'trading_days': round(float(stats.trading_days or 0), 1)
                }
            }

        except Exception as e:
            logger.error(f"Error getting trading statistics for {user_id}: {e}")
            return self._get_empty_stats()

    def _get_empty_stats(self) -> Dict:
        """Return empty statistics structure for new users."""
        return {
            'challenges': {
                'total': 0, 'pending': 0, 'active': 0, 'failed': 0, 'funded': 0, 'success_rate': 0
            },
            'financial': {
                'total_equity': 0, 'total_invested': 0, 'total_realized_pnl': 0,
                'total_return_pct': 0, 'best_trade': 0, 'worst_trade': 0, 'avg_return_on_success': 0
            },
            'trading': {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate': 0, 'avg_trade_pnl': 0
            },
            'activity': {
                'last_trade_date': None, 'first_challenge_date': None, 'trading_days': 0
            }
        }

    def _get_user_achievements(self, session: Session, user_id: str) -> List[Dict]:
        """Get user achievements and badges."""
        try:
            # Get stats for achievement calculation
            stats = self._get_trading_statistics(session, user_id)

            achievements = []

            # Challenge-based achievements
            if stats['challenges']['funded'] >= 1:
                achievements.append({
                    'id': 'first_funded',
                    'name': 'First Funded',
                    'description': 'Successfully funded your first challenge',
                    'icon': '🏆',
                    'unlocked_at': datetime.now(timezone.utc).isoformat(),
                    'rarity': 'common'
                })

            if stats['challenges']['funded'] >= 5:
                achievements.append({
                    'id': 'funded_master',
                    'name': 'Funding Master',
                    'description': 'Successfully funded 5 challenges',
                    'icon': '👑',
                    'unlocked_at': datetime.now(timezone.utc).isoformat(),
                    'rarity': 'rare'
                })

            # Performance-based achievements
            if stats['financial']['total_realized_pnl'] >= 1000:
                achievements.append({
                    'id': 'profit_hunter',
                    'name': 'Profit Hunter',
                    'description': 'Generated $1,000+ in profits',
                    'icon': '💰',
                    'unlocked_at': datetime.now(timezone.utc).isoformat(),
                    'rarity': 'epic'
                })

            if stats['trading']['win_rate'] >= 60:
                achievements.append({
                    'id': 'consistent_winner',
                    'name': 'Consistent Winner',
                    'description': 'Achieved 60%+ win rate',
                    'icon': '🎯',
                    'unlocked_at': datetime.now(timezone.utc).isoformat(),
                    'rarity': 'rare'
                })

            # Activity-based achievements
            if stats['trading']['total_trades'] >= 100:
                achievements.append({
                    'id': 'active_trader',
                    'name': 'Active Trader',
                    'description': 'Executed 100+ trades',
                    'icon': '⚡',
                    'unlocked_at': datetime.now(timezone.utc).isoformat(),
                    'rarity': 'common'
                })

            return achievements

        except Exception as e:
            logger.error(f"Error getting achievements for {user_id}: {e}")
            return []

    def _get_active_challenges(self, session: Session, user_id: str) -> List[Dict]:
        """Get user's active challenges."""
        try:
            challenges = session.execute(text("""
                SELECT
                    id, initial_balance, current_equity, status,
                    started_at, last_trade_at, created_at
                FROM challenges
                WHERE user_id = :user_id AND status IN ('PENDING', 'ACTIVE')
                ORDER BY created_at DESC
                LIMIT 5
            """), {'user_id': user_id}).fetchall()

            return [{
                'id': str(c.id),
                'initial_balance': float(c.initial_balance),
                'current_equity': float(c.current_equity),
                'status': c.status,
                'started_at': c.started_at.isoformat() if c.started_at else None,
                'last_trade_at': c.last_trade_at.isoformat() if c.last_trade_at else None,
                'created_at': c.created_at.isoformat()
            } for c in challenges]

        except Exception as e:
            logger.error(f"Error getting active challenges for {user_id}: {e}")
            return []

    def _get_recent_activity(self, session: Session, user_id: str) -> List[Dict]:
        """Get user's recent trading activity."""
        try:
            activities = session.execute(text("""
                SELECT
                    'trade' as type,
                    t.id as activity_id,
                    t.symbol,
                    t.side,
                    t.quantity,
                    t.price,
                    t.realized_pnl,
                    t.executed_at,
                    c.id as challenge_id
                FROM trades t
                JOIN challenges c ON t.challenge_id = c.id
                WHERE c.user_id = :user_id
                ORDER BY t.executed_at DESC
                LIMIT 10
            """), {'user_id': user_id}).fetchall()

            return [{
                'type': 'trade',
                'id': str(a.activity_id),
                'symbol': a.symbol,
                'side': a.side,
                'quantity': float(a.quantity),
                'price': float(a.price),
                'pnl': float(a.realized_pnl),
                'timestamp': a.executed_at.isoformat(),
                'challenge_id': str(a.challenge_id)
            } for a in activities]

        except Exception as e:
            logger.error(f"Error getting recent activity for {user_id}: {e}")
            return []

    def _get_risk_metrics(self, session: Session, user_id: str) -> Dict:
        """Get user's risk metrics from risk scores."""
        try:
            risk_data = session.execute(text("""
                SELECT
                    risk_score,
                    risk_level,
                    created_at
                FROM risk_scores
                WHERE challenge_id IN (
                    SELECT id FROM challenges WHERE user_id = :user_id
                )
                ORDER BY created_at DESC
                LIMIT 1
            """), {'user_id': user_id}).fetchone()

            if risk_data:
                return {
                    'current_risk_score': risk_data.risk_score,
                    'risk_level': risk_data.risk_level,
                    'last_assessed': risk_data.created_at.isoformat()
                }
            else:
                return {
                    'current_risk_score': None,
                    'risk_level': 'unknown',
                    'last_assessed': None
                }

        except Exception as e:
            logger.error(f"Error getting risk metrics for {user_id}: {e}")
            return {
                'current_risk_score': None,
                'risk_level': 'unknown',
                'last_assessed': None
            }

    def _get_user_preferences(self, user_id: str) -> Dict:
        """Get user preferences (mock implementation)."""
        # In a real implementation, this would come from a preferences table
        return {
            'theme': 'dark',
            'notifications': {
                'email': True,
                'push': True,
                'trade_alerts': True,
                'risk_warnings': True
            },
            'privacy': {
                'show_in_leaderboard': True,
                'public_profile': False
            },
            'trading': {
                'default_challenge_type': 'starter',
                'auto_renew': False
            }
        }

    def _calculate_profile_completeness(self, stats: Dict) -> int:
        """Calculate profile completeness percentage."""
        completeness = 0
        max_score = 100

        # Basic profile (20 points)
        completeness += 20

        # Trading activity (30 points)
        if stats['challenges']['total'] > 0:
            completeness += 15
        if stats['trading']['total_trades'] > 0:
            completeness += 15

        # Performance (30 points)
        if stats['challenges']['funded'] > 0:
            completeness += 15
        if stats['financial']['total_realized_pnl'] > 0:
            completeness += 15

        # Achievements (20 points)
        if stats['challenges']['funded'] >= 3:
            completeness += 10
        if stats['trading']['win_rate'] >= 50:
            completeness += 10

        return min(completeness, max_score)

    def update_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        """
        Update user preferences.

        Args:
            user_id: User ID
            preferences: New preferences data

        Returns:
            Success status
        """
        try:
            # In a real implementation, this would update a preferences table
            logger.info(f"Updated preferences for user {user_id}: {preferences}")
            return True
        except Exception as e:
            logger.error(f"Error updating preferences for {user_id}: {e}")
            return False


# Global user profile service instance
user_profile_service = UserProfileService()