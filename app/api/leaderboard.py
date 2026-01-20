"""
Leaderboard API Endpoints

Provides access to trader rankings and performance statistics.
"""

from flask import jsonify, request, current_app
from . import api_bp
from app.leaderboard import leaderboard_service


@api_bp.route('/leaderboard/global', methods=['GET'])
def get_global_leaderboard():
    """
    Get global trader leaderboard.

    Query parameters:
    - limit: Number of results (default: 50, max: 100)
    - timeframe: 'all', 'month', 'week', 'today' (default: 'all')
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
        timeframe = request.args.get('timeframe', 'all')

        if timeframe not in ['all', 'month', 'week', 'today']:
            return jsonify({'error': 'Invalid timeframe. Must be: all, month, week, or today'}), 400

        leaderboard = leaderboard_service.get_global_leaderboard(limit=limit, timeframe=timeframe)

        return jsonify({
            'leaderboard': leaderboard,
            'count': len(leaderboard),
            'limit': limit,
            'timeframe': timeframe,
            'last_updated': leaderboard_service.get_leaderboard_stats().get('last_updated')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting global leaderboard: {e}")
        return jsonify({'error': 'Failed to get leaderboard'}), 500


@api_bp.route('/leaderboard/categories', methods=['GET'])
def get_category_leaderboards():
    """
    Get specialized leaderboards by category.

    Returns leaderboards for: most_profitable, highest_success_rate, most_active, best_risk_management
    """
    try:
        categories = leaderboard_service.get_category_leaderboards()

        return jsonify({
            'categories': categories,
            'last_updated': leaderboard_service.get_leaderboard_stats().get('last_updated')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting category leaderboards: {e}")
        return jsonify({'error': 'Failed to get category leaderboards'}), 500


@api_bp.route('/leaderboard/user/<user_id>', methods=['GET'])
def get_user_rankings(user_id: str):
    """
    Get detailed rankings for a specific user.

    Returns user's position across all ranking categories.
    """
    try:
        rankings = leaderboard_service.get_user_rankings(user_id)

        return jsonify({
            'user_rankings': rankings,
            'last_updated': leaderboard_service.get_leaderboard_stats().get('last_updated')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user rankings for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user rankings'}), 500


@api_bp.route('/leaderboard/stats', methods=['GET'])
def get_leaderboard_stats():
    """
    Get overall leaderboard statistics.

    Returns aggregate stats about the trading community.
    """
    try:
        stats = leaderboard_service.get_leaderboard_stats()

        return jsonify({
            'stats': stats
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting leaderboard stats: {e}")
        return jsonify({'error': 'Failed to get leaderboard stats'}), 500


@api_bp.route('/leaderboard/top-traders', methods=['GET'])
def get_top_traders():
    """
    Get top 10 traders across all categories.

    Returns a summary of the best performers.
    """
    try:
        # Get top traders from global leaderboard
        top_traders = leaderboard_service.get_global_leaderboard(limit=10, timeframe='all')

        # Get category winners
        categories = leaderboard_service.get_category_leaderboards()

        # Extract winners from each category
        winners = {}
        for category, traders in categories.items():
            if traders:
                winners[category] = traders[0]

        return jsonify({
            'top_traders': top_traders,
            'category_winners': winners,
            'last_updated': leaderboard_service.get_leaderboard_stats().get('last_updated')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting top traders: {e}")
        return jsonify({'error': 'Failed to get top traders'}), 500


@api_bp.route('/leaderboard/rankings/<user_id>', methods=['GET'])
def get_user_position(user_id: str):
    """
    Get a user's position in the leaderboard.

    Returns rank, percentile, and nearby traders.
    """
    try:
        # Get user's rankings
        user_rankings = leaderboard_service.get_user_rankings(user_id)

        # Get global leaderboard to find nearby traders
        global_board = leaderboard_service.get_global_leaderboard(limit=100)

        # Find user's position and nearby traders
        user_position = None
        nearby_traders = []

        for trader in global_board:
            if trader['user_id'] == user_id:
                user_position = trader['rank']
                break

        if user_position:
            # Get traders around the user's position
            start_idx = max(0, user_position - 6)
            end_idx = min(len(global_board), user_position + 5)
            nearby_traders = global_board[start_idx:end_idx]

            # Calculate percentile
            total_traders = len(global_board)
            percentile = ((total_traders - user_position + 1) / total_traders) * 100
        else:
            percentile = 0

        return jsonify({
            'user_id': user_id,
            'position': user_position,
            'percentile': round(percentile, 1),
            'nearby_traders': nearby_traders,
            'rankings': user_rankings.get('rankings', {}),
            'stats': user_rankings.get('stats', {}),
            'last_updated': leaderboard_service.get_leaderboard_stats().get('last_updated')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user position for {user_id}: {e}")
        return jsonify({'error': 'Failed to get user position'}), 500