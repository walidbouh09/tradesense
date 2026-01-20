"""
Rewards and Achievements System

Manages gamification elements, achievements, badges, and rewards for traders.
"""

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, and_, or_
import logging

logger = logging.getLogger(__name__)


class RewardsService:
    """
    Service for managing achievements, badges, and rewards.

    Provides gamification elements to encourage positive trading behavior
    and track user milestones.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
        self.engine = create_engine(self.database_url, echo=False)

        # Achievement definitions
        self.achievements = self._define_achievements()

        # Badge definitions
        self.badges = self._define_badges()

    def _define_achievements(self) -> Dict[str, Dict]:
        """Define all available achievements."""
        return {
            # Onboarding achievements
            'first_login': {
                'id': 'first_login',
                'name': 'Welcome to TradeSense!',
                'description': 'Complete your first login',
                'icon': '🎯',
                'category': 'onboarding',
                'rarity': 'common',
                'points': 10,
                'requirements': {'logins': 1}
            },
            'first_challenge': {
                'id': 'first_challenge',
                'name': 'First Challenge',
                'description': 'Start your first trading challenge',
                'icon': '🚀',
                'category': 'onboarding',
                'rarity': 'common',
                'points': 25,
                'requirements': {'challenges_started': 1}
            },

            # Performance achievements
            'first_win': {
                'id': 'first_win',
                'name': 'First Victory',
                'description': 'Win your first trade',
                'icon': '🏆',
                'category': 'performance',
                'rarity': 'common',
                'points': 50,
                'requirements': {'winning_trades': 1}
            },
            'profit_hunter': {
                'id': 'profit_hunter',
                'name': 'Profit Hunter',
                'description': 'Generate $1,000+ in profits',
                'icon': '💰',
                'category': 'performance',
                'rarity': 'rare',
                'points': 200,
                'requirements': {'total_pnl': 1000}
            },
            'funded_trader': {
                'id': 'funded_trader',
                'name': 'Funded Trader',
                'description': 'Successfully fund your first challenge',
                'icon': '💎',
                'category': 'performance',
                'rarity': 'epic',
                'points': 500,
                'requirements': {'funded_challenges': 1}
            },
            'master_trader': {
                'id': 'master_trader',
                'name': 'Master Trader',
                'description': 'Fund 10 challenges successfully',
                'icon': '👑',
                'category': 'performance',
                'rarity': 'legendary',
                'points': 1000,
                'requirements': {'funded_challenges': 10}
            },

            # Consistency achievements
            'streak_master': {
                'id': 'streak_master',
                'name': 'Streak Master',
                'description': 'Achieve a 10-trade winning streak',
                'icon': '🔥',
                'category': 'consistency',
                'rarity': 'rare',
                'points': 150,
                'requirements': {'max_win_streak': 10}
            },
            'consistent_winner': {
                'id': 'consistent_winner',
                'name': 'Consistent Winner',
                'description': 'Maintain 60%+ win rate over 50 trades',
                'icon': '🎯',
                'category': 'consistency',
                'rarity': 'epic',
                'points': 300,
                'requirements': {'win_rate_over_50_trades': 60}
            },

            # Activity achievements
            'active_trader': {
                'id': 'active_trader',
                'name': 'Active Trader',
                'description': 'Execute 100+ trades',
                'icon': '⚡',
                'category': 'activity',
                'rarity': 'common',
                'points': 75,
                'requirements': {'total_trades': 100}
            },
            'speed_trader': {
                'id': 'speed_trader',
                'name': 'Speed Trader',
                'description': 'Execute 10+ trades in a single day',
                'icon': '💨',
                'category': 'activity',
                'rarity': 'rare',
                'points': 100,
                'requirements': {'trades_in_single_day': 10}
            },

            # Risk management achievements
            'risk_manager': {
                'id': 'risk_manager',
                'name': 'Risk Manager',
                'description': 'Complete a challenge without breaching drawdown limits',
                'icon': '🛡️',
                'category': 'risk',
                'rarity': 'uncommon',
                'points': 125,
                'requirements': {'perfect_risk_management': 1}
            },
            'survivor': {
                'id': 'survivor',
                'name': 'Survivor',
                'description': 'Recover from a 50%+ drawdown to profitability',
                'icon': '🦅',
                'category': 'risk',
                'rarity': 'epic',
                'points': 400,
                'requirements': {'recovery_from_large_drawdown': True}
            },

            # Social achievements
            'leaderboard_climber': {
                'id': 'leaderboard_climber',
                'name': 'Leaderboard Climber',
                'description': 'Reach top 10 in weekly leaderboard',
                'icon': '📈',
                'category': 'social',
                'rarity': 'uncommon',
                'points': 80,
                'requirements': {'weekly_top_10': 1}
            },
            'community_helper': {
                'id': 'community_helper',
                'name': 'Community Helper',
                'description': 'Help 5 other traders with advice',
                'icon': '🤝',
                'category': 'social',
                'rarity': 'uncommon',
                'points': 60,
                'requirements': {'community_help': 5}
            },

            # Special achievements
            'early_adopter': {
                'id': 'early_adopter',
                'name': 'Early Adopter',
                'description': 'Join TradeSense AI during beta period',
                'icon': '🌟',
                'category': 'special',
                'rarity': 'legendary',
                'points': 1000,
                'requirements': {'beta_user': True}
            },
            'perfectionist': {
                'id': 'perfectionist',
                'name': 'Perfectionist',
                'description': 'Achieve 100% win rate over 10 trades',
                'icon': '💫',
                'category': 'special',
                'rarity': 'legendary',
                'points': 750,
                'requirements': {'perfect_10_trades': True}
            }
        }

    def _define_badges(self) -> Dict[str, Dict]:
        """Define badge tiers and requirements."""
        return {
            'bronze': {
                'name': 'Bronze Trader',
                'icon': '🥉',
                'requirements': {'total_points': 500},
                'benefits': ['Basic profile badge', 'Access to bronze challenges']
            },
            'silver': {
                'name': 'Silver Trader',
                'icon': '🥈',
                'requirements': {'total_points': 1500},
                'benefits': ['Silver profile badge', 'Priority support', 'Advanced analytics']
            },
            'gold': {
                'name': 'Gold Trader',
                'icon': '🥇',
                'requirements': {'total_points': 3000},
                'benefits': ['Gold profile badge', 'VIP support', 'Exclusive challenges', 'Monthly bonus']
            },
            'platinum': {
                'name': 'Platinum Trader',
                'icon': '💎',
                'requirements': {'total_points': 5000},
                'benefits': ['Platinum profile badge', 'Dedicated account manager', 'Custom challenges', 'Quarterly bonus']
            },
            'diamond': {
                'name': 'Diamond Trader',
                'icon': '💎',
                'requirements': {'total_points': 10000},
                'benefits': ['Diamond profile badge', 'All platform features', 'Monthly strategy sessions', 'Annual bonus']
            }
        }

    def check_achievements(self, user_id: str) -> List[Dict]:
        """
        Check for newly unlocked achievements for a user.

        Args:
            user_id: User ID to check achievements for

        Returns:
            List of newly unlocked achievements
        """
        with Session(self.engine) as session:
            try:
                # Get user's current stats
                user_stats = self._get_user_stats(session, user_id)

                # Get already unlocked achievements
                unlocked_achievement_ids = session.execute(text("""
                    SELECT achievement_id FROM user_achievements
                    WHERE user_id = :user_id
                """), {'user_id': user_id}).fetchall()

                unlocked_ids = {row.achievement_id for row in unlocked_achievement_ids}

                # Check for new achievements
                new_achievements = []
                for achievement_id, achievement in self.achievements.items():
                    if achievement_id in unlocked_ids:
                        continue

                    if self._check_achievement_requirements(user_stats, achievement):
                        # Unlock the achievement
                        session.execute(text("""
                            INSERT INTO user_achievements (user_id, achievement_id, unlocked_at, points_awarded)
                            VALUES (:user_id, :achievement_id, :unlocked_at, :points)
                        """), {
                            'user_id': user_id,
                            'achievement_id': achievement_id,
                            'unlocked_at': datetime.now(timezone.utc),
                            'points': achievement['points']
                        })

                        new_achievement = achievement.copy()
                        new_achievement['unlocked_at'] = datetime.now(timezone.utc).isoformat()
                        new_achievements.append(new_achievement)

                session.commit()

                # Send notifications for new achievements
                if new_achievements:
                    from app.notifications import notification_service
                    for achievement in new_achievements:
                        notification_service.queue_notification(
                            user_id=user_id,
                            notification_type='achievement_unlocked',
                            data=achievement
                        )

                return new_achievements

            except Exception as e:
                logger.error(f"Error checking achievements for {user_id}: {e}")
                session.rollback()
                return []

    def _get_user_stats(self, session: Session, user_id: str) -> Dict:
        """Get comprehensive user statistics for achievement checking."""
        try:
            stats = session.execute(text("""
                SELECT
                    -- Basic counts
                    (SELECT COUNT(*) FROM challenges WHERE user_id = :user_id) as total_challenges,
                    (SELECT COUNT(*) FROM challenges WHERE user_id = :user_id AND status = 'FUNDED') as funded_challenges,
                    (SELECT COUNT(*) FROM trades WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id)) as total_trades,
                    (SELECT COUNT(*) FROM trades WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id) AND realized_pnl > 0) as winning_trades,

                    -- Financial metrics
                    (SELECT COALESCE(SUM(realized_pnl), 0) FROM trades WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id)) as total_pnl,

                    -- Advanced metrics
                    (SELECT MAX(consecutive_wins) FROM (
                        SELECT COUNT(*) as consecutive_wins
                        FROM (
                            SELECT realized_pnl > 0 as is_win,
                                   ROW_NUMBER() OVER (ORDER BY executed_at) - ROW_NUMBER() OVER (PARTITION BY realized_pnl > 0 ORDER BY executed_at) as grp
                            FROM trades
                            WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id)
                        ) t
                        WHERE is_win = true
                        GROUP BY grp
                    ) consecutive) as max_win_streak,

                    -- Daily activity
                    (SELECT MAX(daily_trades) FROM (
                        SELECT DATE(executed_at), COUNT(*) as daily_trades
                        FROM trades
                        WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id)
                        GROUP BY DATE(executed_at)
                    ) daily) as max_daily_trades,

                    -- Risk management
                    (SELECT COUNT(*) FROM challenges c
                     WHERE user_id = :user_id AND status = 'FUNDED'
                     AND NOT EXISTS (
                         SELECT 1 FROM challenge_events ce
                         WHERE ce.challenge_id = c.id
                         AND ce.event_type IN ('DAILY_DRAWDOWN_EXCEEDED', 'TOTAL_DRAWDOWN_EXCEEDED')
                     )) as perfect_risk_challenges,

                    -- Special conditions
                    (SELECT CASE WHEN COUNT(*) >= 10 THEN
                        (SELECT AVG(CASE WHEN realized_pnl > 0 THEN 100 ELSE 0 END)
                         FROM (SELECT realized_pnl FROM trades
                               WHERE challenge_id IN (SELECT id FROM challenges WHERE user_id = :user_id)
                               ORDER BY executed_at DESC LIMIT 10) last10)
                     ELSE 0 END) as last_10_trades_win_rate

                FROM (SELECT 1) dummy
            """), {'user_id': user_id}).fetchone()

            return {
                'total_challenges': stats.total_challenges or 0,
                'funded_challenges': stats.funded_challenges or 0,
                'total_trades': stats.total_trades or 0,
                'winning_trades': stats.winning_trades or 0,
                'total_pnl': float(stats.total_pnl or 0),
                'max_win_streak': stats.max_win_streak or 0,
                'max_daily_trades': stats.max_daily_trades or 0,
                'perfect_risk_challenges': stats.perfect_risk_challenges or 0,
                'last_10_trades_win_rate': float(stats.last_10_trades_win_rate or 0),
                'logins': 1,  # Mock - would be tracked separately
                'challenges_started': stats.total_challenges or 0,
                'win_rate_over_50_trades': (stats.winning_trades / stats.total_trades * 100) if stats.total_trades >= 50 else 0,
                'trades_in_single_day': stats.max_daily_trades or 0,
                'perfect_10_trades': (stats.last_10_trades_win_rate == 100) if stats.last_10_trades_win_rate else False,
                'recovery_from_large_drawdown': False,  # Would need more complex logic
                'weekly_top_10': 0,  # Would need leaderboard integration
                'community_help': 0,  # Would need social features
                'beta_user': False  # Would be set during registration
            }

        except Exception as e:
            logger.error(f"Error getting user stats for {user_id}: {e}")
            return {}

    def _check_achievement_requirements(self, user_stats: Dict, achievement: Dict) -> bool:
        """Check if user meets achievement requirements."""
        requirements = achievement.get('requirements', {})

        for req_key, req_value in requirements.items():
            user_value = user_stats.get(req_key, 0)

            if req_key in ['win_rate_over_50_trades', 'total_pnl']:
                if user_value < req_value:
                    return False
            elif req_key in ['perfect_10_trades', 'recovery_from_large_drawdown', 'beta_user']:
                if user_value != req_value:
                    return False
            else:
                if user_value < req_value:
                    return False

        return True

    def get_user_achievements(self, user_id: str) -> Dict:
        """
        Get all achievements and badges for a user.

        Args:
            user_id: User ID to get achievements for

        Returns:
            User's achievements, badges, and progress
        """
        with Session(self.engine) as session:
            try:
                # Get unlocked achievements
                unlocked_achievements = session.execute(text("""
                    SELECT ua.achievement_id, ua.unlocked_at, ua.points_awarded, a.name, a.description, a.icon, a.category, a.rarity
                    FROM user_achievements ua
                    JOIN (SELECT * FROM jsonb_object_keys(:achievements::jsonb) as achievement_id) keys ON ua.achievement_id = keys
                    LEFT JOIN jsonb_to_record(:achievements::jsonb) as a(name text, description text, icon text, category text, rarity text)
                        ON a.name IS NOT NULL
                    WHERE ua.user_id = :user_id
                    ORDER BY ua.unlocked_at DESC
                """), {
                    'user_id': user_id,
                    'achievements': self.achievements
                }).fetchall()

                # Get total points
                total_points_result = session.execute(text("""
                    SELECT COALESCE(SUM(points_awarded), 0) as total_points
                    FROM user_achievements
                    WHERE user_id = :user_id
                """), {'user_id': user_id}).fetchone()

                total_points = total_points_result.total_points or 0

                # Determine current badge
                current_badge = None
                for badge_id, badge in self.badges.items():
                    if total_points >= badge['requirements']['total_points']:
                        current_badge = {
                            'id': badge_id,
                            **badge,
                            'earned_at': datetime.now(timezone.utc).isoformat()  # Would be tracked properly
                        }

                # Get progress towards next badge
                next_badge = None
                progress_to_next = 0

                badge_order = ['bronze', 'silver', 'gold', 'platinum', 'diamond']
                current_badge_index = None

                if current_badge:
                    current_badge_index = badge_order.index(current_badge['id'])

                if current_badge_index is None or current_badge_index < len(badge_order) - 1:
                    next_badge_index = 0 if current_badge_index is None else current_badge_index + 1
                    next_badge_id = badge_order[next_badge_index]
                    next_badge = self.badges[next_badge_id]

                    next_badge_required = next_badge['requirements']['total_points']
                    progress_to_next = min(100, (total_points / next_badge_required) * 100)

                # Get achievement progress
                user_stats = self._get_user_stats(session, user_id)
                achievement_progress = []

                for achievement_id, achievement in self.achievements.items():
                    # Check if already unlocked
                    is_unlocked = any(ua.achievement_id == achievement_id for ua in unlocked_achievements)

                    if is_unlocked:
                        progress = 100
                    else:
                        # Calculate progress (simplified)
                        requirements = achievement.get('requirements', {})
                        progress = 0

                        if requirements:
                            first_req = list(requirements.keys())[0]
                            required_value = requirements[first_req]
                            current_value = user_stats.get(first_req, 0)

                            if required_value > 0:
                                progress = min(100, (current_value / required_value) * 100)

                    achievement_progress.append({
                        'achievement_id': achievement_id,
                        'name': achievement['name'],
                        'description': achievement['description'],
                        'icon': achievement['icon'],
                        'category': achievement['category'],
                        'rarity': achievement['rarity'],
                        'points': achievement['points'],
                        'progress': round(progress, 1),
                        'is_unlocked': is_unlocked,
                        'unlocked_at': next((ua.unlocked_at.isoformat() for ua in unlocked_achievements if ua.achievement_id == achievement_id), None)
                    })

                return {
                    'total_points': total_points,
                    'current_badge': current_badge,
                    'next_badge': next_badge,
                    'progress_to_next_badge': round(progress_to_next, 1),
                    'unlocked_achievements': len(unlocked_achievements),
                    'total_achievements': len(self.achievements),
                    'achievements': achievement_progress,
                    'badges': list(self.badges.values()),
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                logger.error(f"Error getting user achievements for {user_id}: {e}")
                return {
                    'error': str(e),
                    'total_points': 0,
                    'unlocked_achievements': 0,
                    'total_achievements': len(self.achievements)
                }

    def get_leaderboard_by_achievements(self, limit: int = 50) -> List[Dict]:
        """
        Get leaderboard ranked by achievement points.

        Args:
            limit: Number of users to return

        Returns:
            Achievement-based leaderboard
        """
        with Session(self.engine) as session:
            try:
                leaderboard = session.execute(text("""
                    SELECT
                        ua.user_id,
                        u.email,
                        SUM(ua.points_awarded) as total_points,
                        COUNT(ua.achievement_id) as achievements_unlocked,
                        MAX(ua.unlocked_at) as last_achievement_date
                    FROM user_achievements ua
                    JOIN users u ON ua.user_id = u.id
                    WHERE u.deleted_at IS NULL
                    GROUP BY ua.user_id, u.email
                    ORDER BY total_points DESC, achievements_unlocked DESC
                    LIMIT :limit
                """), {'limit': limit}).fetchall()

                return [{
                    'rank': i + 1,
                    'user_id': str(row.user_id),
                    'email': row.email.split('@')[0] + '***',
                    'total_points': row.total_points,
                    'achievements_unlocked': row.achievements_unlocked,
                    'last_achievement_date': row.last_achievement_date.isoformat() if row.last_achievement_date else None
                } for i, row in enumerate(leaderboard)]

            except Exception as e:
                logger.error(f"Error getting achievement leaderboard: {e}")
                return []

    def get_achievement_stats(self) -> Dict:
        """
        Get platform-wide achievement statistics.

        Returns aggregate stats about achievements across all users.
        """
        with Session(self.engine) as session:
            try:
                stats = session.execute(text("""
                    SELECT
                        COUNT(DISTINCT ua.user_id) as users_with_achievements,
                        COUNT(ua.achievement_id) as total_achievements_unlocked,
                        SUM(ua.points_awarded) as total_points_awarded,
                        AVG(ua.points_awarded) as avg_points_per_achievement,
                        COUNT(DISTINCT ua.achievement_id) as unique_achievements_unlocked
                    FROM user_achievements ua
                """)).fetchall()

                if stats:
                    stat = stats[0]
                    return {
                        'users_with_achievements': stat.users_with_achievements or 0,
                        'total_achievements_unlocked': stat.total_achievements_unlocked or 0,
                        'total_points_awarded': stat.total_points_awarded or 0,
                        'avg_points_per_achievement': round(float(stat.avg_points_per_achievement or 0), 1),
                        'unique_achievements_unlocked': stat.unique_achievements_unlocked or 0,
                        'total_available_achievements': len(self.achievements),
                        'achievement_unlock_rate': round((stat.unique_achievements_unlocked or 0) / len(self.achievements) * 100, 1),
                        'last_updated': datetime.now(timezone.utc).isoformat()
                    }

                return {
                    'users_with_achievements': 0,
                    'total_achievements_unlocked': 0,
                    'total_points_awarded': 0,
                    'avg_points_per_achievement': 0,
                    'unique_achievements_unlocked': 0,
                    'total_available_achievements': len(self.achievements),
                    'achievement_unlock_rate': 0,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                logger.error(f"Error getting achievement stats: {e}")
                return {'error': str(e)}


# Global rewards service instance
rewards_service = RewardsService()