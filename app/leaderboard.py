"""
Leaderboard System

Ranks traders based on performance metrics and achievements.
"""

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, desc, func
import logging

logger = logging.getLogger(__name__)


class LeaderboardService:
    """
    Service for managing trader leaderboards and rankings.

    Tracks various performance metrics and creates competitive rankings.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
        self.engine = create_engine(self.database_url, echo=False)

    def get_global_leaderboard(self, limit: int = 50, timeframe: str = 'all') -> List[Dict]:
        """
        Get global leaderboard of top traders.

        Args:
            limit: Number of traders to return
            timeframe: 'all', 'month', 'week', 'today'

        Returns:
            List of trader rankings with stats
        """
        with Session(self.engine) as session:
            try:
                # Calculate date filter based on timeframe
                date_filter = self._get_date_filter(timeframe)

                # Get trader performance data
                query = text("""
                    SELECT
                        u.id as user_id,
                        u.email,
                        u.created_at as joined_at,
                        COUNT(DISTINCT c.id) as total_challenges,
                        COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as successful_challenges,
                        COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as total_pnl,
                        COALESCE(AVG(CASE WHEN c.status = 'FUNDED' THEN (c.current_equity - c.initial_balance) / c.initial_balance END), 0) as avg_return_pct,
                        MAX(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END) as best_trade,
                        COUNT(t.id) as total_trades,
                        COALESCE(AVG(t.realized_pnl), 0) as avg_trade_pnl,
                        MAX(c.created_at) as last_challenge_date
                    FROM users u
                    LEFT JOIN challenges c ON u.id = c.user_id
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE u.deleted_at IS NULL
                    AND (c.created_at >= :date_filter OR :date_filter IS NULL)
                    GROUP BY u.id, u.email, u.created_at
                    HAVING COUNT(DISTINCT c.id) > 0
                    ORDER BY
                        -- Primary: Success rate
                        (COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END)::float /
                         NULLIF(COUNT(DISTINCT c.id), 0)) DESC,
                        -- Secondary: Total PnL
                        COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) DESC,
                        -- Tertiary: Total challenges
                        COUNT(DISTINCT c.id) DESC
                    LIMIT :limit
                """)

                result = session.execute(query, {
                    'date_filter': date_filter,
                    'limit': limit
                }).fetchall()

                leaderboard = []
                for i, row in enumerate(result, 1):
                    success_rate = (row.successful_challenges / row.total_challenges * 100) if row.total_challenges > 0 else 0

                    trader_data = {
                        'rank': i,
                        'user_id': str(row.user_id),
                        'email': row.email.split('@')[0] + '***',  # Anonymize email
                        'joined_at': row.joined_at.isoformat(),
                        'stats': {
                            'total_challenges': row.total_challenges,
                            'successful_challenges': row.successful_challenges,
                            'success_rate': round(success_rate, 1),
                            'total_pnl': float(row.total_pnl),
                            'avg_return_pct': round(float(row.avg_return_pct) * 100, 1),
                            'best_trade': float(row.best_trade) if row.best_trade else 0,
                            'total_trades': row.total_trades,
                            'avg_trade_pnl': round(float(row.avg_trade_pnl), 2)
                        },
                        'last_active': row.last_challenge_date.isoformat() if row.last_challenge_date else None,
                        'timeframe': timeframe
                    }

                    leaderboard.append(trader_data)

                return leaderboard

            except Exception as e:
                logger.error(f"Error getting global leaderboard: {e}")
                return []

    def get_category_leaderboards(self) -> Dict[str, List[Dict]]:
        """
        Get specialized leaderboards by category.

        Returns leaderboards for different performance categories.
        """
        categories = {}

        # Most Profitable
        categories['most_profitable'] = self._get_category_leaderboard(
            order_by="total_pnl DESC",
            limit=10
        )

        # Highest Success Rate
        categories['highest_success_rate'] = self._get_category_leaderboard(
            order_by="(successful_challenges::float / NULLIF(total_challenges, 0)) DESC",
            limit=10
        )

        # Most Active
        categories['most_active'] = self._get_category_leaderboard(
            order_by="total_challenges DESC",
            limit=10
        )

        # Best Risk Managers
        categories['best_risk_management'] = self._get_category_leaderboard(
            order_by="avg_trade_pnl DESC",
            limit=10
        )

        return categories

    def _get_category_leaderboard(self, order_by: str, limit: int = 10) -> List[Dict]:
        """Helper method for category-specific leaderboards."""
        with Session(self.engine) as session:
            try:
                query = text(f"""
                    SELECT
                        u.id as user_id,
                        u.email,
                        COUNT(DISTINCT c.id) as total_challenges,
                        COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as successful_challenges,
                        COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as total_pnl,
                        COUNT(t.id) as total_trades,
                        COALESCE(AVG(t.realized_pnl), 0) as avg_trade_pnl
                    FROM users u
                    LEFT JOIN challenges c ON u.id = c.user_id
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE u.deleted_at IS NULL
                    GROUP BY u.id, u.email
                    HAVING COUNT(DISTINCT c.id) > 0
                    ORDER BY {order_by}
                    LIMIT :limit
                """)

                result = session.execute(query, {'limit': limit}).fetchall()

                return [{
                    'rank': i + 1,
                    'user_id': str(row.user_id),
                    'email': row.email.split('@')[0] + '***',
                    'stats': {
                        'total_challenges': row.total_challenges,
                        'successful_challenges': row.successful_challenges,
                        'total_pnl': float(row.total_pnl),
                        'total_trades': row.total_trades,
                        'avg_trade_pnl': round(float(row.avg_trade_pnl), 2)
                    }
                } for i, row in enumerate(result)]

            except Exception as e:
                logger.error(f"Error getting category leaderboard: {e}")
                return []

    def get_user_rankings(self, user_id: str) -> Dict:
        """
        Get detailed rankings for a specific user across all categories.

        Args:
            user_id: User ID to get rankings for

        Returns:
            User's ranking data across different metrics
        """
        with Session(self.engine) as session:
            try:
                # Get user's stats
                user_stats = session.execute(text("""
                    SELECT
                        COUNT(DISTINCT c.id) as total_challenges,
                        COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as successful_challenges,
                        COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as total_pnl,
                        COUNT(t.id) as total_trades,
                        COALESCE(AVG(t.realized_pnl), 0) as avg_trade_pnl
                    FROM challenges c
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE c.user_id = :user_id
                """), {'user_id': user_id}).fetchone()

                if not user_stats or user_stats.total_challenges == 0:
                    return {
                        'user_id': user_id,
                        'rankings': {},
                        'stats': {
                            'total_challenges': 0,
                            'successful_challenges': 0,
                            'total_pnl': 0,
                            'total_trades': 0,
                            'avg_trade_pnl': 0
                        }
                    }

                # Calculate rankings
                rankings = {}

                # Overall ranking
                overall_rank = session.execute(text("""
                    SELECT COUNT(*) + 1 as rank FROM (
                        SELECT u.id,
                               (COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END)::float /
                                NULLIF(COUNT(DISTINCT c.id), 0)) as success_rate,
                               COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as pnl
                        FROM users u
                        LEFT JOIN challenges c ON u.id = c.user_id
                        WHERE u.deleted_at IS NULL
                        GROUP BY u.id
                        HAVING COUNT(DISTINCT c.id) > 0
                    ) ranked
                    WHERE (success_rate > :user_success_rate)
                       OR (success_rate = :user_success_rate AND pnl > :user_pnl)
                """), {
                    'user_success_rate': (user_stats.successful_challenges / user_stats.total_challenges) if user_stats.total_challenges > 0 else 0,
                    'user_pnl': float(user_stats.total_pnl)
                }).fetchone()

                rankings['overall'] = overall_rank.rank if overall_rank else 1

                return {
                    'user_id': user_id,
                    'rankings': rankings,
                    'stats': {
                        'total_challenges': user_stats.total_challenges,
                        'successful_challenges': user_stats.successful_challenges,
                        'total_pnl': float(user_stats.total_pnl),
                        'total_trades': user_stats.total_trades,
                        'avg_trade_pnl': round(float(user_stats.avg_trade_pnl), 2)
                    }
                }

            except Exception as e:
                logger.error(f"Error getting user rankings for {user_id}: {e}")
                return {
                    'user_id': user_id,
                    'rankings': {},
                    'stats': {},
                    'error': str(e)
                }

    def get_leaderboard_stats(self) -> Dict:
        """
        Get overall leaderboard statistics.

        Returns aggregate stats about the trading community.
        """
        with Session(self.engine) as session:
            try:
                stats = session.execute(text("""
                    SELECT
                        COUNT(DISTINCT u.id) as total_traders,
                        COUNT(DISTINCT c.id) as total_challenges,
                        COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as successful_challenges,
                        COALESCE(SUM(CASE WHEN c.status = 'FUNDED' THEN c.current_equity - c.initial_balance END), 0) as total_pnl_generated,
                        COUNT(t.id) as total_trades_executed,
                        AVG(CASE WHEN c.status = 'FUNDED' THEN (c.current_equity - c.initial_balance) / c.initial_balance END) as avg_successful_return
                    FROM users u
                    LEFT JOIN challenges c ON u.id = c.user_id
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE u.deleted_at IS NULL
                """)).fetchone()

                return {
                    'total_traders': stats.total_traders or 0,
                    'total_challenges': stats.total_challenges or 0,
                    'successful_challenges': stats.successful_challenges or 0,
                    'total_pnl_generated': float(stats.total_pnl_generated or 0),
                    'total_trades_executed': stats.total_trades_executed or 0,
                    'avg_successful_return': round(float(stats.avg_successful_return or 0) * 100, 1),
                    'success_rate': round((stats.successful_challenges or 0) / (stats.total_challenges or 1) * 100, 1),
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                logger.error(f"Error getting leaderboard stats: {e}")
                return {
                    'error': str(e),
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

    def _get_date_filter(self, timeframe: str) -> Optional[datetime]:
        """Get datetime filter based on timeframe."""
        now = datetime.now(timezone.utc)

        if timeframe == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == 'week':
            return now - timedelta(days=7)
        elif timeframe == 'month':
            return now - timedelta(days=30)
        else:  # 'all'
            return None


# Global leaderboard service instance
leaderboard_service = LeaderboardService()