"""
User Profiles API Endpoints

Provides access to user profiles, statistics, and preferences.
"""

from flask import jsonify, request, current_app
from . import api_bp
from app.user_profiles import user_profile_service


@api_bp.route('/profiles/<user_id>', methods=['GET'])
def get_user_profile(user_id: str):
    """
    Get complete user profile with statistics.

    Returns comprehensive trading statistics, achievements, and activity.
    """
    try:
        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        return jsonify({
            'profile': profile,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user profile for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user profile'}), 500


@api_bp.route('/profiles/<user_id>/stats', methods=['GET'])
def get_user_stats(user_id: str):
    """
    Get user trading statistics summary.

    Returns key metrics and performance indicators.
    """
    try:
        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        return jsonify({
            'stats': profile.get('trading_stats', {}),
            'rankings': profile.get('rankings', {}),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user stats for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user stats'}), 500


@api_bp.route('/profiles/<user_id>/achievements', methods=['GET'])
def get_user_achievements(user_id: str):
    """
    Get user achievements and badges.

    Returns all unlocked achievements with details.
    """
    try:
        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        return jsonify({
            'achievements': profile.get('achievements', []),
            'total_achievements': len(profile.get('achievements', [])),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user achievements for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user achievements'}), 500


@api_bp.route('/profiles/<user_id>/activity', methods=['GET'])
def get_user_activity(user_id: str):
    """
    Get user recent activity.

    Query parameters:
    - limit: Number of activities to return (default: 20, max: 100)
    """
    try:
        limit = min(int(request.args.get('limit', 20)), 100)

        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        # Get recent activity (limit the results)
        recent_activity = profile.get('recent_activity', [])[:limit]

        return jsonify({
            'activity': recent_activity,
            'count': len(recent_activity),
            'limit': limit,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user activity for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user activity'}), 500


@api_bp.route('/profiles/<user_id>/challenges', methods=['GET'])
def get_user_challenges(user_id: str):
    """
    Get user's challenges.

    Query parameters:
    - status: Filter by status (PENDING, ACTIVE, FAILED, FUNDED) - optional
    - limit: Number of challenges to return (default: 10, max: 50)
    """
    try:
        status_filter = request.args.get('status')
        limit = min(int(request.args.get('limit', 10)), 50)

        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        challenges = profile.get('active_challenges', [])

        # Apply status filter if provided
        if status_filter:
            challenges = [c for c in challenges if c['status'] == status_filter]

        # Limit results
        challenges = challenges[:limit]

        return jsonify({
            'challenges': challenges,
            'count': len(challenges),
            'filter': {'status': status_filter} if status_filter else None,
            'limit': limit,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user challenges for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user challenges'}), 500


@api_bp.route('/profiles/<user_id>/preferences', methods=['GET'])
def get_user_preferences(user_id: str):
    """
    Get user preferences and settings.
    """
    try:
        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        return jsonify({
            'preferences': profile.get('preferences', {}),
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user preferences for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user preferences'}), 500


@api_bp.route('/profiles/<user_id>/preferences', methods=['PUT'])
def update_user_preferences(user_id: str):
    """
    Update user preferences and settings.

    Expects:
    {
        "theme": "dark|light",
        "notifications": {
            "email": true,
            "push": true,
            "trade_alerts": true,
            "risk_warnings": true
        },
        "privacy": {
            "show_in_leaderboard": true,
            "public_profile": false
        },
        "trading": {
            "default_challenge_type": "starter",
            "auto_renew": false
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Update preferences
        success = user_profile_service.update_user_preferences(user_id, data)

        if success:
            return jsonify({
                'message': 'Preferences updated successfully',
                'preferences': data,
                'success': True
            }), 200
        else:
            return jsonify({'error': 'Failed to update preferences'}), 500

    except Exception as e:
        current_app.logger.error(f"Error updating user preferences for {user_id}: {e}")
        return jsonify({'error': 'Failed to update preferences'}), 500


@api_bp.route('/profiles/<user_id>/dashboard', methods=['GET'])
def get_user_dashboard(user_id: str):
    """
    Get dashboard data for a user.

    Returns key metrics and recent activity for dashboard display.
    """
    try:
        profile = user_profile_service.get_user_profile(user_id)

        if 'error' in profile:
            return jsonify({'error': profile['error']}), 404

        # Extract dashboard-relevant data
        dashboard = {
            'user_id': profile['user_id'],
            'trading_stats': profile['trading_stats'],
            'rankings': profile['rankings'],
            'active_challenges': profile['active_challenges'][:3],  # Top 3 active challenges
            'recent_activity': profile['recent_activity'][:5],  # Last 5 activities
            'achievements': profile['achievements'][:3],  # Top 3 achievements
            'risk_metrics': profile['risk_metrics'],
            'profile_completeness': profile['profile_completeness']
        }

        return jsonify({
            'dashboard': dashboard,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user dashboard for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user dashboard'}), 500


@api_bp.route('/profiles/summary', methods=['GET'])
def get_profiles_summary():
    """
    Get summary statistics for all users.

    Returns aggregate statistics about the user community.
    """
    try:
        # This would require a more complex query to aggregate all user data
        # For now, return mock data
        summary = {
            'total_users': 1250,
            'active_users_today': 89,
            'total_challenges_created': 3456,
            'total_trades_executed': 45678,
            'total_pnl_generated': 125000.50,
            'top_performers': {
                'best_trader': 'user_001',
                'highest_win_rate': 'user_045',
                'most_active': 'user_123'
            },
            'last_updated': '2024-01-18T10:30:00Z'
        }

        return jsonify({
            'summary': summary,
            'success': True
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting profiles summary: {e}")
        return jsonify({'error': 'Failed to get profiles summary'}), 500