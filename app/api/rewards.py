"""
Rewards and Achievements API Endpoints

Provides access to achievements, badges, and gamification features.
"""

from flask import current_app, jsonify, request

from app.rewards import rewards_service

from . import api_bp


@api_bp.route("/rewards/achievements/<user_id>", methods=["GET"])
def get_user_rewards_achievements(user_id: str):
    """
    Get all achievements and badges for a user.

    Returns unlocked achievements, current badge, and progress.
    """
    try:
        rewards_data = rewards_service.get_user_achievements(user_id)

        if "error" in rewards_data:
            return jsonify({"error": rewards_data["error"]}), 500

        return jsonify(
            {"rewards": rewards_data, "user_id": user_id, "success": True}
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user achievements for {user_id}: {e}")
        return jsonify({"error": "Failed to get user achievements"}), 500


@api_bp.route("/rewards/achievements/<user_id>/check", methods=["POST"])
def check_user_achievements(user_id: str):
    """
    Check for newly unlocked achievements for a user.

    This endpoint should be called after significant user actions
    (trade execution, challenge completion, etc.).
    """
    try:
        new_achievements = rewards_service.check_achievements(user_id)

        return jsonify(
            {
                "new_achievements": new_achievements,
                "count": len(new_achievements),
                "user_id": user_id,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error checking achievements for {user_id}: {e}")
        return jsonify({"error": "Failed to check achievements"}), 500


@api_bp.route("/rewards/achievements", methods=["GET"])
def get_all_achievements():
    """
    Get all available achievements.

    Returns the complete list of achievements that can be unlocked.
    """
    try:
        achievements = rewards_service.achievements

        # Group by category
        categories = {}
        for achievement_id, achievement in achievements.items():
            category = achievement["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append({"id": achievement_id, **achievement})

        return jsonify(
            {
                "achievements": achievements,
                "categories": categories,
                "total_achievements": len(achievements),
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting all achievements: {e}")
        return jsonify({"error": "Failed to get achievements"}), 500


@api_bp.route("/rewards/badges", methods=["GET"])
def get_all_badges():
    """
    Get all available badges.

    Returns the complete list of badges that can be earned.
    """
    try:
        badges = rewards_service.badges

        return jsonify(
            {"badges": badges, "total_badges": len(badges), "success": True}
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting all badges: {e}")
        return jsonify({"error": "Failed to get badges"}), 500


@api_bp.route("/rewards/leaderboard", methods=["GET"])
def get_achievement_leaderboard():
    """
    Get leaderboard ranked by achievement points.

    Query parameters:
    - limit: Number of users to return (default: 50, max: 100)
    """
    try:
        limit = min(int(request.args.get("limit", 50)), 100)

        leaderboard = rewards_service.get_leaderboard_by_achievements(limit=limit)

        return jsonify(
            {
                "leaderboard": leaderboard,
                "count": len(leaderboard),
                "limit": limit,
                "ranking_type": "achievements",
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting achievement leaderboard: {e}")
        return jsonify({"error": "Failed to get achievement leaderboard"}), 500


@api_bp.route("/rewards/stats", methods=["GET"])
def get_rewards_stats():
    """
    Get platform-wide achievement and rewards statistics.
    """
    try:
        stats = rewards_service.get_achievement_stats()

        return jsonify({"stats": stats, "success": True}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting rewards stats: {e}")
        return jsonify({"error": "Failed to get rewards stats"}), 500


@api_bp.route("/rewards/progress/<user_id>", methods=["GET"])
def get_user_progress(user_id: str):
    """
    Get user's progress towards achievements.

    Returns detailed progress for each achievement.
    """
    try:
        # Get full achievements data
        rewards_data = rewards_service.get_user_achievements(user_id)

        if "error" in rewards_data:
            return jsonify({"error": rewards_data["error"]}), 500

        # Extract progress information
        progress_data = {
            "user_id": user_id,
            "total_points": rewards_data["total_points"],
            "current_badge": rewards_data["current_badge"],
            "next_badge": rewards_data["next_badge"],
            "progress_to_next_badge": rewards_data["progress_to_next_badge"],
            "achievement_progress": [
                {
                    "id": achievement["achievement_id"],
                    "name": achievement["name"],
                    "category": achievement["category"],
                    "rarity": achievement["rarity"],
                    "progress": achievement["progress"],
                    "is_unlocked": achievement["is_unlocked"],
                    "points": achievement["points"],
                }
                for achievement in rewards_data["achievements"]
            ],
            "unlocked_count": rewards_data["unlocked_achievements"],
            "total_count": rewards_data["total_achievements"],
            "completion_percentage": round(
                rewards_data["unlocked_achievements"]
                / rewards_data["total_achievements"]
                * 100,
                1,
            ),
        }

        return jsonify({"progress": progress_data, "success": True}), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user progress for {user_id}: {e}")
        return jsonify({"error": "Failed to get user progress"}), 500


@api_bp.route("/rewards/milestones/<user_id>", methods=["GET"])
def get_user_milestones(user_id: str):
    """
    Get upcoming achievement milestones for a user.

    Returns the next few achievements the user can unlock.
    """
    try:
        rewards_data = rewards_service.get_user_achievements(user_id)

        if "error" in rewards_data:
            return jsonify({"error": rewards_data["error"]}), 500

        # Find next achievable achievements
        next_milestones = []

        for achievement in rewards_data["achievements"]:
            if (
                not achievement["is_unlocked"] and achievement["progress"] > 50
            ):  # Within reach
                next_milestones.append(
                    {
                        "id": achievement["id"],
                        "name": achievement["name"],
                        "description": achievement["description"],
                        "icon": achievement["icon"],
                        "category": achievement["category"],
                        "rarity": achievement["rarity"],
                        "points": achievement["points"],
                        "current_progress": achievement["progress"],
                        "remaining_progress": round(100 - achievement["progress"], 1),
                    }
                )

        # Sort by progress (closest to completion first)
        next_milestones.sort(key=lambda x: x["current_progress"], reverse=True)

        # Limit to top 5
        next_milestones = next_milestones[:5]

        return jsonify(
            {
                "milestones": next_milestones,
                "count": len(next_milestones),
                "user_id": user_id,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting user milestones for {user_id}: {e}")
        return jsonify({"error": "Failed to get user milestones"}), 500


@api_bp.route("/rewards/achievements/recent", methods=["GET"])
def get_recent_achievements():
    """
    Get recently unlocked achievements across the platform.

    Query parameters:
    - limit: Number of recent achievements to return (default: 20, max: 100)
    """
    try:
        limit = min(int(request.args.get("limit", 20)), 100)

        # In a real implementation, this would query for recent unlocks
        # For now, return mock data structure
        recent_achievements = [
            {
                "achievement_id": "first_win",
                "achievement_name": "First Victory",
                "user_id": "user_001",
                "user_email": "user***@example.com",
                "unlocked_at": "2024-01-18T10:30:00Z",
                "points": 50,
            },
            {
                "achievement_id": "active_trader",
                "achievement_name": "Active Trader",
                "user_id": "user_002",
                "user_email": "user***@example.com",
                "unlocked_at": "2024-01-18T09:15:00Z",
                "points": 75,
            },
        ]

        return jsonify(
            {
                "recent_achievements": recent_achievements[:limit],
                "count": len(recent_achievements[:limit]),
                "limit": limit,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting recent achievements: {e}")
        return jsonify({"error": "Failed to get recent achievements"}), 500


@api_bp.route("/rewards/categories", methods=["GET"])
def get_achievement_categories():
    """
    Get achievement categories and their statistics.

    Returns information about each achievement category.
    """
    try:
        achievements = rewards_service.achievements

        # Analyze categories
        categories = {}
        for achievement in achievements.values():
            category = achievement["category"]
            if category not in categories:
                categories[category] = {
                    "name": category.title(),
                    "count": 0,
                    "total_points": 0,
                    "avg_rarity": [],
                }

            categories[category]["count"] += 1
            categories[category]["total_points"] += achievement["points"]
            categories[category]["avg_rarity"].append(achievement["rarity"])

        # Calculate averages
        rarity_scores = {
            "common": 1,
            "uncommon": 2,
            "rare": 3,
            "epic": 4,
            "legendary": 5,
        }
        for category_data in categories.values():
            category_data["avg_points"] = round(
                category_data["total_points"] / category_data["count"], 1
            )
            category_data["avg_rarity_score"] = round(
                sum(rarity_scores[r] for r in category_data["avg_rarity"])
                / len(category_data["avg_rarity"]),
                1,
            )
            del category_data["avg_rarity"]

        return jsonify(
            {
                "categories": categories,
                "total_categories": len(categories),
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting achievement categories: {e}")
        return jsonify({"error": "Failed to get achievement categories"}), 500
