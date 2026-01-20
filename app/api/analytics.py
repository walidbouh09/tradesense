"""
Analytics API Endpoints

Provides access to advanced trading analytics and performance metrics.
"""

from flask import current_app, jsonify, request

from app.analytics import analytics_service

from . import api_bp


@api_bp.route("/analytics/portfolio/<user_id>", methods=["GET"])
def get_user_portfolio_analytics(user_id: str):
    """
    Get comprehensive portfolio performance analytics.

    Query parameters:
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'all')

    Returns detailed portfolio metrics, risk analysis, and time series data.
    """
    try:
        timeframe = request.args.get("timeframe", "all")

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        analytics = analytics_service.get_portfolio_performance(user_id, timeframe)

        return (
            jsonify(
                {
                    "analytics": analytics,
                    "timeframe": timeframe,
                    "user_id": user_id,
                    "last_updated": "2024-01-18T10:30:00Z",  # Would be dynamic in real implementation
                    "success": True,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(
            f"Error getting portfolio analytics for {user_id}: {e}"
        )
        return jsonify({"error": "Failed to get portfolio analytics"}), 500


@api_bp.route("/analytics/trades/<user_id>", methods=["GET"])
def get_trade_analytics(user_id: str):
    """
    Get detailed trade analytics and patterns.

    Query parameters:
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'all')

    Returns comprehensive trade analysis including patterns, timing, and distributions.
    """
    try:
        timeframe = request.args.get("timeframe", "all")

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        analytics = analytics_service.get_trade_analytics(user_id, timeframe)

        return jsonify(
            {
                "analytics": analytics,
                "timeframe": timeframe,
                "user_id": user_id,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting trade analytics for {user_id}: {e}")
        return jsonify({"error": "Failed to get trade analytics"}), 500


@api_bp.route("/analytics/market", methods=["GET"])
def get_market_analysis():
    """
    Get market-wide analysis and trends.

    Query parameters:
    - symbols: Comma-separated list of symbols to analyze (optional)

    Returns market sentiment, popular symbols, and platform-wide trends.
    """
    try:
        symbols_param = request.args.get("symbols")
        symbols = symbols_param.split(",") if symbols_param else None

        analysis = analytics_service.get_market_analysis(symbols)

        return jsonify(
            {"market_analysis": analysis, "requested_symbols": symbols, "success": True}
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting market analysis: {e}")
        return jsonify({"error": "Failed to get market analysis"}), 500


@api_bp.route("/analytics/performance/<user_id>", methods=["GET"])
def get_performance_metrics(user_id: str):
    """
    Get key performance indicators and metrics.

    Query parameters:
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'month')
    - metrics: Comma-separated list of metrics to return (optional)

    Returns focused performance metrics for dashboards and reports.
    """
    try:
        timeframe = request.args.get("timeframe", "month")
        metrics_param = request.args.get("metrics")
        requested_metrics = metrics_param.split(",") if metrics_param else None

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        # Get portfolio analytics
        portfolio = analytics_service.get_portfolio_performance(user_id, timeframe)
        trades = analytics_service.get_trade_analytics(user_id, timeframe)

        # Combine and filter metrics
        performance = {
            "portfolio": {
                "total_return_pct": portfolio["overview"]["total_return_pct"],
                "sharpe_ratio": portfolio["performance"]["sharpe_ratio"],
                "win_rate": portfolio["performance"]["win_rate"],
                "max_drawdown": portfolio["risk_metrics"]["max_drawdown"],
                "volatility": portfolio["performance"]["volatility"],
            },
            "trading": {
                "total_trades": trades["summary"]["total_trades"],
                "avg_trade_pnl": trades["summary"]["avg_trade_pnl"],
                "best_symbol": trades["symbols"][0]["symbol"]
                if trades["symbols"]
                else None,
                "best_hour": trades["timing"]["best_hours"][0]["hour"]
                if trades["timing"]["best_hours"]
                else None,
            },
            "risk": {
                "value_at_risk": portfolio["risk_metrics"]["value_at_risk"],
                "expected_shortfall": portfolio["risk_metrics"]["expected_shortfall"],
            },
        }

        # Filter metrics if requested
        if requested_metrics:
            filtered_performance = {}
            for category, metrics in performance.items():
                filtered_performance[category] = {
                    k: v for k, v in metrics.items() if k in requested_metrics
                }
            performance = filtered_performance

        return jsonify(
            {
                "performance": performance,
                "timeframe": timeframe,
                "user_id": user_id,
                "requested_metrics": requested_metrics,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(
            f"Error getting performance metrics for {user_id}: {e}"
        )
        return jsonify({"error": "Failed to get performance metrics"}), 500


@api_bp.route("/analytics/comparison/<user_id>", methods=["GET"])
def get_performance_comparison(user_id: str):
    """
    Compare user's performance with market benchmarks.

    Query parameters:
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'month')

    Returns comparison with market averages and peer performance.
    """
    try:
        timeframe = request.args.get("timeframe", "month")

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        # Get user's performance
        user_portfolio = analytics_service.get_portfolio_performance(user_id, timeframe)
        user_trades = analytics_service.get_trade_analytics(user_id, timeframe)

        # Get market analysis for comparison
        market_analysis = analytics_service.get_market_analysis()

        # Calculate percentiles and comparisons
        user_win_rate = user_trades["summary"]["win_rate"]
        market_avg_win_rate = market_analysis["market_summary"]["market_avg_win_rate"]

        user_return = user_portfolio["overview"]["total_return_pct"]
        # Mock market average return (would be calculated from real data)
        market_avg_return = 12.5

        comparison = {
            "win_rate": {
                "user": user_win_rate,
                "market_avg": market_avg_win_rate,
                "difference": round(user_win_rate - market_avg_win_rate, 1),
                "percentile": self._calculate_percentile(
                    user_win_rate, market_avg_win_rate
                ),
            },
            "return": {
                "user": user_return,
                "market_avg": market_avg_return,
                "difference": round(user_return - market_avg_return, 1),
                "performance": "above_average"
                if user_return > market_avg_return
                else "below_average",
            },
            "trading_frequency": {
                "user_trades": user_trades["summary"]["total_trades"],
                "market_avg_trades": round(
                    market_analysis["market_summary"]["total_market_trades"] / 1000, 0
                ),  # Per user estimate
                "activity_level": self._classify_activity(
                    user_trades["summary"]["total_trades"]
                ),
            },
            "risk_profile": {
                "user_volatility": user_portfolio["performance"]["volatility"],
                "market_avg_volatility": 15.0,  # Mock value
                "risk_level": self._classify_risk(
                    user_portfolio["performance"]["volatility"]
                ),
            },
        }

        return jsonify(
            {
                "comparison": comparison,
                "timeframe": timeframe,
                "user_id": user_id,
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(
            f"Error getting performance comparison for {user_id}: {e}"
        )
        return jsonify({"error": "Failed to get performance comparison"}), 500

    def _calculate_percentile(self, user_value: float, market_avg: float) -> str:
        """Calculate performance percentile."""
        if user_value > market_avg * 1.2:
            return "top_25%"
        elif user_value > market_avg:
            return "top_50%"
        elif user_value > market_avg * 0.8:
            return "bottom_50%"
        else:
            return "bottom_25%"

    def _classify_activity(self, trade_count: int) -> str:
        """Classify trading activity level."""
        if trade_count > 100:
            return "very_active"
        elif trade_count > 50:
            return "active"
        elif trade_count > 20:
            return "moderate"
        else:
            return "low_activity"

    def _classify_risk(self, volatility: float) -> str:
        """Classify risk profile based on volatility."""
        if volatility > 25:
            return "high_risk"
        elif volatility > 15:
            return "moderate_risk"
        elif volatility > 5:
            return "low_risk"
        else:
            return "very_low_risk"


@api_bp.route("/analytics/insights/<user_id>", methods=["GET"])
def get_trading_insights(user_id: str):
    """
    Get AI-powered trading insights and recommendations.

    Query parameters:
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'month')

    Returns personalized insights based on trading patterns.
    """
    try:
        timeframe = request.args.get("timeframe", "month")

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        # Get analytics data
        portfolio = analytics_service.get_portfolio_performance(user_id, timeframe)
        trades = analytics_service.get_trade_analytics(user_id, timeframe)

        insights = []

        # Generate insights based on data
        if trades["summary"]["win_rate"] < 40:
            insights.append(
                {
                    "type": "warning",
                    "title": "Low Win Rate Detected",
                    "message": f"Your win rate of {trades['summary']['win_rate']}% is below the recommended 50%+. Consider reviewing your entry criteria.",
                    "priority": "high",
                    "category": "performance",
                }
            )

        if portfolio["performance"]["volatility"] > 20:
            insights.append(
                {
                    "type": "caution",
                    "title": "High Portfolio Volatility",
                    "message": f"Your portfolio volatility of {portfolio['performance']['volatility']:.1f} indicates high risk. Consider diversifying your trades.",
                    "priority": "medium",
                    "category": "risk",
                }
            )

        if trades["timing"]["best_hours"]:
            best_hour = trades["timing"]["best_hours"][0]["hour"]
            insights.append(
                {
                    "type": "tip",
                    "title": "Optimal Trading Time",
                    "message": f"You perform best at {best_hour}:00. Consider concentrating your trading during this hour.",
                    "priority": "low",
                    "category": "timing",
                }
            )

        if trades["symbols"] and len(trades["symbols"]) > 1:
            best_symbol = trades["symbols"][0]["symbol"]
            insights.append(
                {
                    "type": "opportunity",
                    "title": "Strong Symbol Performance",
                    "message": f"{best_symbol} shows your best performance. Consider focusing more on this symbol.",
                    "priority": "medium",
                    "category": "strategy",
                }
            )

        if portfolio["overview"]["total_return_pct"] > 15:
            insights.append(
                {
                    "type": "achievement",
                    "title": "Excellent Performance",
                    "message": f"Congratulations! Your {portfolio['overview']['total_return_pct']:.1f}% return is outstanding.",
                    "priority": "high",
                    "category": "achievement",
                }
            )

        return jsonify(
            {
                "insights": insights,
                "total_insights": len(insights),
                "timeframe": timeframe,
                "user_id": user_id,
                "generated_at": "2024-01-18T10:30:00Z",
                "success": True,
            }
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error getting trading insights for {user_id}: {e}")
        return jsonify({"error": "Failed to get trading insights"}), 500


@api_bp.route("/analytics/export/<user_id>", methods=["GET"])
def export_analytics_data(user_id: str):
    """
    Export analytics data for external analysis.

    Query parameters:
    - format: 'json', 'csv' (default: 'json')
    - timeframe: 'all', 'month', 'quarter', 'year' (default: 'all')

    Returns analytics data in specified format for download.
    """
    try:
        format_type = request.args.get("format", "json")
        timeframe = request.args.get("timeframe", "all")

        if format_type not in ["json", "csv"]:
            return jsonify({"error": "Invalid format. Must be: json or csv"}), 400

        if timeframe not in ["all", "month", "quarter", "year"]:
            return jsonify(
                {"error": "Invalid timeframe. Must be: all, month, quarter, or year"}
            ), 400

        # Get all analytics data
        portfolio = analytics_service.get_portfolio_performance(user_id, timeframe)
        trades = analytics_service.get_trade_analytics(user_id, timeframe)

        export_data = {
            "user_id": user_id,
            "timeframe": timeframe,
            "exported_at": "2024-01-18T10:30:00Z",
            "portfolio_analytics": portfolio,
            "trade_analytics": trades,
        }

        if format_type == "csv":
            # In a real implementation, would generate CSV format
            return jsonify(
                {"message": "CSV export not yet implemented", "data_available": True}
            ), 501

        return jsonify(
            {"export_data": export_data, "format": format_type, "success": True}
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error exporting analytics data for {user_id}: {e}")
        return jsonify({"error": "Failed to export analytics data"}), 500
