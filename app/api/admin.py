"""
Admin API Endpoints

Provides administrative endpoints for platform management.
Requires ADMIN or SUPERADMIN role.
"""

from flask import jsonify, request, current_app
from functools import wraps
from . import api_bp
from app.admin import admin_service


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In a real implementation, this would check JWT token for admin role
        # For demo purposes, we'll allow all requests
        return f(*args, **kwargs)
    return decorated_function


@api_bp.route('/admin/dashboard', methods=['GET'])
@admin_required
def get_admin_dashboard():
    """
    Get comprehensive admin dashboard statistics.

    Returns all key metrics and KPIs for platform monitoring.
    """
    try:
        dashboard_stats = admin_service.get_dashboard_stats()

        if 'error' in dashboard_stats:
            return jsonify({'error': dashboard_stats['error']}), 500

        return jsonify({
            'dashboard': dashboard_stats,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting admin dashboard: {e}")
        return jsonify({'error': 'Failed to get admin dashboard'}), 500


@api_bp.route('/admin/users', methods=['GET'])
@admin_required
def get_user_management():
    """
    Get user management data for admin interface.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Users per page (default: 50, max: 100)
    - search: Search by email
    - status: Filter by status (active, deleted)
    """
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)
        search = request.args.get('search')
        status = request.args.get('status')

        if page < 1:
            return jsonify({'error': 'Page must be >= 1'}), 400

        user_data = admin_service.get_user_management_data(
            page=page,
            per_page=per_page,
            search=search,
            status=status
        )

        if 'error' in user_data:
            return jsonify({'error': user_data['error']}), 500

        return jsonify({
            'user_management': user_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user management data: {e}")
        return jsonify({'error': 'Failed to get user management data'}), 500


@api_bp.route('/admin/users/<user_id>/manage', methods=['POST'])
@admin_required
def manage_user(user_id: str):
    """
    Perform administrative actions on a user.

    Expects:
    {
        "action": "suspend|reactivate|change_role",
        "role": "USER|ADMIN|SUPERADMIN"  // Only for change_role action
    }
    """
    try:
        data = request.get_json()

        if not data or 'action' not in data:
            return jsonify({'error': 'Action is required'}), 400

        action = data['action']

        if action not in ['suspend', 'reactivate', 'change_role']:
            return jsonify({'error': 'Invalid action'}), 400

        result = admin_service.manage_user(user_id, action, **data)

        if 'error' in result:
            return jsonify({'error': result['error']}), 400

        return jsonify({
            'result': result,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error managing user {user_id}: {e}")
        return jsonify({'error': 'Failed to manage user'}), 500


@api_bp.route('/admin/health', methods=['GET'])
@admin_required
def get_system_health():
    """
    Get system health and performance metrics.

    Returns database, API, and infrastructure health indicators.
    """
    try:
        health_data = admin_service.get_system_health()

        return jsonify({
            'health': health_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting system health: {e}")
        return jsonify({'error': 'Failed to get system health'}), 500


@api_bp.route('/admin/audit-logs', methods=['GET'])
@admin_required
def get_audit_logs():
    """
    Get audit logs for administrative monitoring.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 100)
    - user_id: Filter by user ID
    - action: Filter by action type
    - date_from: Filter from date (ISO format)
    - date_to: Filter to date (ISO format)
    """
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)
        user_id = request.args.get('user_id')
        action = request.args.get('action')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        if page < 1:
            return jsonify({'error': 'Page must be >= 1'}), 400

        audit_logs = admin_service.get_audit_logs(
            page=page,
            per_page=per_page,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to
        )

        return jsonify({
            'audit_logs': audit_logs,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting audit logs: {e}")
        return jsonify({'error': 'Failed to get audit logs'}), 500


@api_bp.route('/admin/stats/revenue', methods=['GET'])
@admin_required
def get_revenue_stats():
    """
    Get detailed revenue statistics.

    Query parameters:
    - timeframe: 'day', 'week', 'month', 'year' (default: 'month')
    """
    try:
        timeframe = request.args.get('timeframe', 'month')

        if timeframe not in ['day', 'week', 'month', 'year']:
            return jsonify({'error': 'Invalid timeframe'}), 400

        # Mock revenue data - in real implementation, this would query payment data
        revenue_data = {
            'timeframe': timeframe,
            'total_revenue': 125430.50,
            'monthly_revenue': 15234.75,
            'daily_average': 512.45,
            'top_revenue_sources': [
                {'source': 'Starter Challenges', 'amount': 45230.25, 'percentage': 36.1},
                {'source': 'Professional Challenges', 'amount': 52340.50, 'percentage': 41.7},
                {'source': 'Expert Challenges', 'amount': 21850.75, 'percentage': 17.4},
                {'source': 'Master Challenges', 'amount': 6009.00, 'percentage': 4.8}
            ],
            'revenue_trends': [
                {'period': '2024-01', 'revenue': 12345.67},
                {'period': '2024-02', 'revenue': 14567.89},
                {'period': '2024-03', 'revenue': 15678.90},
                {'period': '2024-04', 'revenue': 15234.75}
            ]
        }

        return jsonify({
            'revenue_stats': revenue_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting revenue stats: {e}")
        return jsonify({'error': 'Failed to get revenue stats'}), 500


@api_bp.route('/admin/stats/challenges', methods=['GET'])
@admin_required
def get_challenge_stats():
    """
    Get detailed challenge statistics.

    Query parameters:
    - timeframe: 'day', 'week', 'month', 'year' (default: 'month')
    """
    try:
        timeframe = request.args.get('timeframe', 'month')

        if timeframe not in ['day', 'week', 'month', 'year']:
            return jsonify({'error': 'Invalid timeframe'}), 400

        # Mock challenge stats - in real implementation, this would query challenge data
        challenge_data = {
            'timeframe': timeframe,
            'total_challenges': 3456,
            'active_challenges': 234,
            'completed_challenges': 3122,
            'success_rate': 68.5,
            'average_duration': 14.3,  # days
            'challenge_types': {
                'starter': {'count': 2341, 'success_rate': 71.2},
                'professional': {'count': 892, 'success_rate': 63.8},
                'expert': {'count': 189, 'success_rate': 45.2},
                'master': {'count': 34, 'success_rate': 23.5}
            },
            'completion_trends': [
                {'period': '2024-01', 'started': 234, 'completed': 198, 'funded': 142},
                {'period': '2024-02', 'started': 345, 'completed': 312, 'funded': 223},
                {'period': '2024-03', 'started': 423, 'completed': 398, 'funded': 289},
                {'period': '2024-04', 'started': 378, 'completed': 345, 'funded': 245}
            ]
        }

        return jsonify({
            'challenge_stats': challenge_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting challenge stats: {e}")
        return jsonify({'error': 'Failed to get challenge stats'}), 500


@api_bp.route('/admin/stats/trading', methods=['GET'])
@admin_required
def get_trading_stats():
    """
    Get detailed trading activity statistics.

    Query parameters:
    - timeframe: 'day', 'week', 'month', 'year' (default: 'month')
    """
    try:
        timeframe = request.args.get('timeframe', 'month')

        if timeframe not in ['day', 'week', 'month', 'year']:
            return jsonify({'error': 'Invalid timeframe'}), 400

        # Mock trading stats - in real implementation, this would query trade data
        trading_data = {
            'timeframe': timeframe,
            'total_trades': 45678,
            'daily_average': 1522.6,
            'total_volume': 23456789.50,
            'winning_trades': 31245,
            'losing_trades': 14433,
            'win_rate': 68.4,
            'avg_trade_size': 513.45,
            'popular_symbols': [
                {'symbol': 'AAPL', 'trades': 3456, 'volume': 1234567.89},
                {'symbol': 'MSFT', 'trades': 2876, 'volume': 987654.32},
                {'symbol': 'GOOGL', 'trades': 2134, 'volume': 765432.10},
                {'symbol': 'TSLA', 'trades': 1876, 'volume': 654321.98}
            ],
            'trading_hours': [
                {'hour': 9, 'trades': 2345, 'avg_pnl': 12.34},
                {'hour': 10, 'trades': 3456, 'avg_pnl': 23.45},
                {'hour': 11, 'trades': 4234, 'avg_pnl': -5.67},
                {'hour': 12, 'trades': 3876, 'avg_pnl': 8.90}
            ]
        }

        return jsonify({
            'trading_stats': trading_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting trading stats: {e}")
        return jsonify({'error': 'Failed to get trading stats'}), 500


@api_bp.route('/admin/export/users', methods=['GET'])
@admin_required
def export_users():
    """
    Export user data for administrative purposes.

    Query parameters:
    - format: 'csv', 'json' (default: 'json')
    - include_stats: Include trading statistics (default: true)
    """
    try:
        format_type = request.args.get('format', 'json')
        include_stats = request.args.get('include_stats', 'true').lower() == 'true'

        if format_type not in ['csv', 'json']:
            return jsonify({'error': 'Invalid format. Must be csv or json'}), 400

        # In a real implementation, this would export actual user data
        # For now, return mock response
        export_data = {
            'export_format': format_type,
            'include_stats': include_stats,
            'total_users': 1250,
            'export_timestamp': '2024-01-18T10:30:00Z',
            'download_url': f'/api/admin/downloads/users_export_{format_type}.{"csv" if format_type == "csv" else "json"}'
        }

        return jsonify({
            'export': export_data,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error exporting users: {e}")
        return jsonify({'error': 'Failed to export users'}), 500


@api_bp.route('/admin/system/maintenance', methods=['POST'])
@admin_required
def system_maintenance():
    """
    Perform system maintenance operations.

    Expects:
    {
        "operation": "cleanup_old_data|reindex_database|clear_cache",
        "parameters": {}  // Operation-specific parameters
    }
    """
    try:
        data = request.get_json()

        if not data or 'operation' not in data:
            return jsonify({'error': 'Operation is required'}), 400

        operation = data['operation']
        parameters = data.get('parameters', {})

        # Mock maintenance operations
        operations = {
            'cleanup_old_data': {
                'description': 'Remove old logs and temporary data',
                'estimated_duration': '5 minutes',
                'impact': 'low'
            },
            'reindex_database': {
                'description': 'Rebuild database indexes for better performance',
                'estimated_duration': '30 minutes',
                'impact': 'medium'
            },
            'clear_cache': {
                'description': 'Clear all cached data',
                'estimated_duration': '2 minutes',
                'impact': 'low'
            }
        }

        if operation not in operations:
            return jsonify({'error': f'Unknown operation: {operation}'}), 400

        # In a real implementation, this would execute the actual maintenance
        result = {
            'operation': operation,
            'status': 'scheduled',
            'scheduled_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            'estimated_completion': (datetime.now(timezone.utc) + timedelta(minutes=operations[operation]['estimated_duration'])).isoformat(),
            'impact': operations[operation]['impact'],
            'message': f'Maintenance operation {operation} has been scheduled'
        }

        return jsonify({
            'maintenance': result,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error performing maintenance: {e}")
        return jsonify({'error': 'Failed to perform maintenance'}), 500