"""
Admin Service

Provides administrative functionality for platform management.
"""

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, desc, func, and_, or_
import logging

logger = logging.getLogger(__name__)


class AdminService:
    """
    Service for platform administration and management.

    Provides tools for monitoring, user management, system health,
    and operational oversight.
    """

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://tradesense_user:tradesense_pass@postgres:5432/tradesense')
        self.engine = create_engine(self.database_url, echo=False)

    def get_dashboard_stats(self) -> Dict:
        """
        Get comprehensive dashboard statistics for administrators.

        Returns key metrics and KPIs for platform monitoring.
        """
        with Session(self.engine) as session:
            try:
                # User statistics
                user_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as new_users_week,
                        COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as new_users_month,
                        COUNT(CASE WHEN deleted_at IS NOT NULL THEN 1 END) as deleted_users
                    FROM users
                """)).fetchone()

                # Challenge statistics
                challenge_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as total_challenges,
                        COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) as active_challenges,
                        COUNT(CASE WHEN status = 'FUNDED' THEN 1 END) as funded_challenges,
                        COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed_challenges,
                        COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as challenges_week,
                        AVG(CASE WHEN status IN ('FUNDED', 'FAILED') THEN EXTRACT(EPOCH FROM (ended_at - started_at))/86400 END) as avg_challenge_duration
                    FROM challenges
                """)).fetchone()

                # Trading statistics
                trading_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(CASE WHEN executed_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as trades_week,
                        SUM(realized_pnl) as total_pnl,
                        AVG(realized_pnl) as avg_trade_pnl,
                        COUNT(DISTINCT challenge_id) as active_trading_challenges
                    FROM trades
                """)).fetchone()

                # Financial statistics
                financial_stats = session.execute(text("""
                    SELECT
                        COALESCE(SUM(amount), 0) as total_revenue,
                        COUNT(*) as total_payments,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_payments,
                        AVG(amount) as avg_payment_amount
                    FROM payments
                """)).fetchone()

                # Risk and alerts
                risk_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as total_alerts,
                        COUNT(CASE WHEN severity = 'HIGH' THEN 1 END) as high_severity_alerts,
                        COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '24 hours' THEN 1 END) as alerts_today
                    FROM risk_alerts
                """)).fetchone()

                # Calculate derived metrics
                success_rate = (challenge_stats.funded_challenges / challenge_stats.total_challenges * 100) if challenge_stats.total_challenges > 0 else 0
                conversion_rate = (challenge_stats.funded_challenges / user_stats.total_users * 100) if user_stats.total_users > 0 else 0
                avg_revenue_per_user = (financial_stats.total_revenue / user_stats.total_users) if user_stats.total_users > 0 else 0

                return {
                    'users': {
                        'total': user_stats.total_users or 0,
                        'new_this_week': user_stats.new_users_week or 0,
                        'new_this_month': user_stats.new_users_month or 0,
                        'deleted': user_stats.deleted_users or 0,
                        'active_rate': round((user_stats.total_users - user_stats.deleted_users) / user_stats.total_users * 100, 1) if user_stats.total_users > 0 else 0
                    },
                    'challenges': {
                        'total': challenge_stats.total_challenges or 0,
                        'active': challenge_stats.active_challenges or 0,
                        'funded': challenge_stats.funded_challenges or 0,
                        'failed': challenge_stats.failed_challenges or 0,
                        'success_rate': round(success_rate, 1),
                        'new_this_week': challenge_stats.challenges_week or 0,
                        'avg_duration_days': round(float(challenge_stats.avg_challenge_duration or 0), 1)
                    },
                    'trading': {
                        'total_trades': trading_stats.total_trades or 0,
                        'trades_this_week': trading_stats.trades_week or 0,
                        'total_pnl': float(trading_stats.total_pnl or 0),
                        'avg_trade_pnl': round(float(trading_stats.avg_trade_pnl or 0), 2),
                        'active_trading_accounts': trading_stats.active_trading_challenges or 0
                    },
                    'financial': {
                        'total_revenue': float(financial_stats.total_revenue or 0),
                        'total_payments': financial_stats.total_payments or 0,
                        'successful_payments': financial_stats.successful_payments or 0,
                        'avg_payment_amount': round(float(financial_stats.avg_payment_amount or 0), 2),
                        'payment_success_rate': round(financial_stats.successful_payments / financial_stats.total_payments * 100, 1) if financial_stats.total_payments > 0 else 0,
                        'revenue_per_user': round(avg_revenue_per_user, 2)
                    },
                    'risk': {
                        'total_alerts': risk_stats.total_alerts or 0,
                        'high_severity_alerts': risk_stats.high_severity_alerts or 0,
                        'alerts_today': risk_stats.alerts_today or 0,
                        'alerts_per_user': round(risk_stats.total_alerts / user_stats.total_users, 2) if user_stats.total_users > 0 else 0
                    },
                    'performance': {
                        'conversion_rate': round(conversion_rate, 1),
                        'user_engagement': round(trading_stats.total_trades / user_stats.total_users, 1) if user_stats.total_users > 0 else 0,
                        'platform_health_score': self._calculate_health_score({
                            'success_rate': success_rate,
                            'conversion_rate': conversion_rate,
                            'payment_success_rate': financial_stats.successful_payments / financial_stats.total_payments * 100 if financial_stats.total_payments > 0 else 0
                        })
                    },
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                logger.error(f"Error getting dashboard stats: {e}")
                return {'error': str(e)}

    def _calculate_health_score(self, metrics: Dict) -> float:
        """Calculate overall platform health score (0-100)."""
        success_rate_score = min(100, metrics['success_rate'] * 2)  # 50% success = 100 score
        conversion_score = min(100, metrics['conversion_rate'] * 10)  # 10% conversion = 100 score
        payment_score = metrics['payment_success_rate']  # Direct percentage

        # Weighted average
        health_score = (success_rate_score * 0.4 + conversion_score * 0.4 + payment_score * 0.2)
        return round(health_score, 1)

    def get_user_management_data(self, page: int = 1, per_page: int = 50, search: str = None, status: str = None) -> Dict:
        """
        Get user management data for admin interface.

        Args:
            page: Page number for pagination
            per_page: Number of users per page
            search: Search term for email filtering
            status: Filter by user status

        Returns:
            Paginated user data with statistics
        """
        with Session(self.engine) as session:
            try:
                offset = (page - 1) * per_page

                # Build query conditions
                conditions = []
                params = {}

                if search:
                    conditions.append("u.email ILIKE :search")
                    params['search'] = f'%{search}%'

                if status == 'active':
                    conditions.append("u.deleted_at IS NULL")
                elif status == 'deleted':
                    conditions.append("u.deleted_at IS NOT NULL")

                where_clause = " AND ".join(conditions) if conditions else "1=1"

                # Get users with stats
                users_query = text(f"""
                    SELECT
                        u.id, u.email, u.role, u.created_at, u.updated_at, u.deleted_at,
                        COUNT(DISTINCT c.id) as total_challenges,
                        COUNT(DISTINCT CASE WHEN c.status = 'FUNDED' THEN c.id END) as funded_challenges,
                        COUNT(t.id) as total_trades,
                        COALESCE(SUM(t.realized_pnl), 0) as total_pnl,
                        MAX(c.last_trade_at) as last_activity
                    FROM users u
                    LEFT JOIN challenges c ON u.id = c.user_id
                    LEFT JOIN trades t ON c.id = t.challenge_id
                    WHERE {where_clause}
                    GROUP BY u.id, u.email, u.role, u.created_at, u.updated_at, u.deleted_at
                    ORDER BY u.created_at DESC
                    LIMIT :limit OFFSET :offset
                """)

                params.update({'limit': per_page, 'offset': offset})
                users = session.execute(users_query, params).fetchall()

                # Get total count
                count_query = text(f"""
                    SELECT COUNT(*) as total FROM users u WHERE {where_clause}
                """)
                total_users = session.execute(count_query, {'search': f'%{search}%'} if search else {}).fetchone().total

                # Format user data
                user_list = []
                for user in users:
                    user_list.append({
                        'id': str(user.id),
                        'email': user.email,
                        'role': user.role,
                        'status': 'deleted' if user.deleted_at else 'active',
                        'created_at': user.created_at.isoformat(),
                        'updated_at': user.updated_at.isoformat() if user.updated_at else None,
                        'deleted_at': user.deleted_at.isoformat() if user.deleted_at else None,
                        'stats': {
                            'total_challenges': user.total_challenges or 0,
                            'funded_challenges': user.funded_challenges or 0,
                            'total_trades': user.total_trades or 0,
                            'total_pnl': float(user.total_pnl or 0),
                            'success_rate': round(user.funded_challenges / user.total_challenges * 100, 1) if user.total_challenges > 0 else 0
                        },
                        'last_activity': user.last_activity.isoformat() if user.last_activity else None
                    })

                return {
                    'users': user_list,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': total_users,
                        'total_pages': (total_users + per_page - 1) // per_page
                    },
                    'filters': {
                        'search': search,
                        'status': status
                    }
                }

            except Exception as e:
                logger.error(f"Error getting user management data: {e}")
                return {'error': str(e)}

    def get_system_health(self) -> Dict:
        """
        Get system health and performance metrics.

        Returns database, API, and infrastructure health indicators.
        """
        try:
            health_data = {
                'database': self._check_database_health(),
                'api_endpoints': self._check_api_endpoints(),
                'external_services': self._check_external_services(),
                'performance': self._get_performance_metrics(),
                'alerts': self._get_system_alerts(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Calculate overall health score
            health_scores = []
            if 'response_time' in health_data['database']:
                health_scores.append(100 if health_data['database']['response_time'] < 1000 else 50)
            if health_data['api_endpoints']['status'] == 'healthy':
                health_scores.append(100)
            if all(service['status'] == 'operational' for service in health_data['external_services'].values()):
                health_scores.append(100)

            health_data['overall_health_score'] = round(sum(health_scores) / len(health_scores), 1) if health_scores else 0

            return health_data

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {'error': str(e), 'overall_health_score': 0}

    def _check_database_health(self) -> Dict:
        """Check database connection and performance."""
        try:
            start_time = datetime.now(timezone.utc)

            with Session(self.engine) as session:
                # Simple query to test connection
                result = session.execute(text("SELECT COUNT(*) as user_count FROM users")).fetchone()
                response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                return {
                    'status': 'healthy',
                    'response_time_ms': round(response_time, 2),
                    'user_count': result.user_count,
                    'connection': 'established'
                }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'connection': 'failed'
            }

    def _check_api_endpoints(self) -> Dict:
        """Check API endpoint health (simplified)."""
        # In a real implementation, this would ping actual endpoints
        return {
            'status': 'healthy',
            'endpoints_checked': 12,  # Number of API endpoints
            'response_time_avg': 45.2,  # Mock average response time
            'uptime_percentage': 99.8
        }

    def _check_external_services(self) -> Dict:
        """Check external service dependencies."""
        # Mock external service checks
        return {
            'stripe': {
                'status': 'operational',
                'response_time': 234,
                'last_check': datetime.now(timezone.utc).isoformat()
            },
            'redis': {
                'status': 'operational',
                'response_time': 12,
                'last_check': datetime.now(timezone.utc).isoformat()
            },
            'email_service': {
                'status': 'operational',
                'response_time': 145,
                'last_check': datetime.now(timezone.utc).isoformat()
            }
        }

    def _get_performance_metrics(self) -> Dict:
        """Get system performance metrics."""
        # Mock performance metrics
        return {
            'cpu_usage': 34.5,
            'memory_usage': 67.8,
            'disk_usage': 45.2,
            'network_io': {
                'in': 125.5,
                'out': 89.3
            },
            'active_connections': 234,
            'requests_per_minute': 1250
        }

    def _get_system_alerts(self) -> List[Dict]:
        """Get active system alerts."""
        # Mock alerts - in real implementation, this would check various thresholds
        return [
            {
                'id': 'high_memory_usage',
                'severity': 'warning',
                'message': 'Memory usage above 65%',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'acknowledged': False
            },
            {
                'id': 'slow_database_queries',
                'severity': 'info',
                'message': 'Some database queries are slower than usual',
                'timestamp': (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
                'acknowledged': True
            }
        ]

    def manage_user(self, user_id: str, action: str, **kwargs) -> Dict:
        """
        Perform administrative actions on users.

        Args:
            user_id: Target user ID
            action: Action to perform (suspend, reactivate, change_role, etc.)
            **kwargs: Additional parameters for the action

        Returns:
            Action result
        """
        with Session(self.engine) as session:
            try:
                if action == 'suspend':
                    # Soft delete user
                    session.execute(text("""
                        UPDATE users SET deleted_at = :now WHERE id = :user_id
                    """), {'user_id': user_id, 'now': datetime.now(timezone.utc)})

                    # Deactivate all active challenges
                    session.execute(text("""
                        UPDATE challenges SET status = 'FAILED', ended_at = :now
                        WHERE user_id = :user_id AND status = 'ACTIVE'
                    """), {'user_id': user_id, 'now': datetime.now(timezone.utc)})

                    session.commit()

                    return {
                        'success': True,
                        'action': 'suspend',
                        'user_id': user_id,
                        'message': 'User suspended successfully'
                    }

                elif action == 'reactivate':
                    # Reactivate user
                    session.execute(text("""
                        UPDATE users SET deleted_at = NULL, updated_at = :now
                        WHERE id = :user_id
                    """), {'user_id': user_id, 'now': datetime.now(timezone.utc)})

                    session.commit()

                    return {
                        'success': True,
                        'action': 'reactivate',
                        'user_id': user_id,
                        'message': 'User reactivated successfully'
                    }

                elif action == 'change_role':
                    new_role = kwargs.get('role')
                    if new_role not in ['USER', 'ADMIN', 'SUPERADMIN']:
                        return {'error': 'Invalid role'}

                    session.execute(text("""
                        UPDATE users SET role = :role, updated_at = :now
                        WHERE id = :user_id
                    """), {'user_id': user_id, 'role': new_role, 'now': datetime.now(timezone.utc)})

                    session.commit()

                    return {
                        'success': True,
                        'action': 'change_role',
                        'user_id': user_id,
                        'new_role': new_role,
                        'message': f'User role changed to {new_role}'
                    }

                else:
                    return {'error': f'Unknown action: {action}'}

            except Exception as e:
                session.rollback()
                logger.error(f"Error performing admin action {action} on user {user_id}: {e}")
                return {'error': str(e)}

    def get_audit_logs(self, page: int = 1, per_page: int = 50, user_id: str = None,
                      action: str = None, date_from: str = None, date_to: str = None) -> Dict:
        """
        Get audit logs for administrative monitoring.

        Args:
            page: Page number
            per_page: Items per page
            user_id: Filter by user ID
            action: Filter by action type
            date_from: Filter from date
            date_to: Filter to date

        Returns:
            Paginated audit logs
        """
        # In a real implementation, this would query an audit log table
        # For now, return mock data
        mock_logs = [
            {
                'id': 'log_001',
                'timestamp': (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                'user_id': f'user_{i%10:03d}',
                'action': ['LOGIN', 'TRADE_EXECUTED', 'CHALLENGE_STARTED', 'PAYMENT_PROCESSED'][i%4],
                'resource': f'challenge_{i}' if i%4 == 2 else f'trade_{i}' if i%4 == 1 else 'system',
                'details': {'ip': '192.168.1.100', 'user_agent': 'Mozilla/5.0...'},
                'status': 'success'
            }
            for i in range(100)
        ]

        # Apply filters
        filtered_logs = mock_logs

        if user_id:
            filtered_logs = [log for log in filtered_logs if log['user_id'] == user_id]

        if action:
            filtered_logs = [log for log in filtered_logs if log['action'] == action]

        if date_from:
            from_date = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log['timestamp']) >= from_date]

        if date_to:
            to_date = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log['timestamp']) <= to_date]

        # Pagination
        offset = (page - 1) * per_page
        paginated_logs = filtered_logs[offset:offset + per_page]
        total_logs = len(filtered_logs)

        return {
            'logs': paginated_logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_logs,
                'total_pages': (total_logs + per_page - 1) // per_page
            },
            'filters': {
                'user_id': user_id,
                'action': action,
                'date_from': date_from,
                'date_to': date_to
            }
        }


# Global admin service instance
admin_service = AdminService()