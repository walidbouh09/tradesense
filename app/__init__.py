"""
TradeSense AI - Professional Flask Application Factory

A production-ready trading platform with comprehensive features:
- JWT Authentication & Authorization
- Real-time WebSocket connections
- Market data integration
- Risk management system
- Challenge-based trading
- Payment processing
- Admin dashboard
"""

import logging
import os
from datetime import timedelta
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.models import db, init_db
from app.utils.exceptions import register_error_handlers
from app.utils.logger import setup_logging
from app.utils.middleware import setup_middleware

# Global instances
socketio = SocketIO()
jwt = JWTManager()
mail = Mail()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]
)


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Create and configure Flask application.

    Args:
        config_name: Configuration environment (development, production, testing)

    Returns:
        Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__)

    # Load configuration
    config_obj = get_config(config_name or os.getenv("FLASK_ENV", "development"))
    app.config.from_object(config_obj)

    # Setup logging
    setup_logging(app)
    app.logger.info(f"Starting TradeSense AI in {config_obj.ENV} mode")

    # Initialize extensions
    _init_extensions(app)

    # Setup middleware
    setup_middleware(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Setup JWT callbacks
    _setup_jwt_callbacks(app)

    # Initialize database
    with app.app_context():
        init_db(app)

    # Setup WebSocket events
    _setup_websocket_events()

    app.logger.info("TradeSense AI application created successfully")

    return app


def _init_extensions(app: Flask) -> None:
    """Initialize Flask extensions."""

    # Database
    db.init_app(app)
    migrate.init_app(app, db)

    # CORS configuration
    cors_origins = (
        app.config.get("CORS_ORIGINS", []).split(",")
        if isinstance(app.config.get("CORS_ORIGINS"), str)
        else app.config.get("CORS_ORIGINS", [])
    )
    CORS(
        app,
        origins=cors_origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    )

    # JWT Authentication
    jwt.init_app(app)

    # Rate limiting
    limiter.init_app(app)

    # Email
    mail.init_app(app)

    # WebSocket with proper configuration
    socketio.init_app(
        app,
        cors_allowed_origins=cors_origins,
        async_mode="eventlet",
        logger=app.debug,
        engineio_logger=app.debug,
        ping_timeout=60,
        ping_interval=25,
    )

    # Handle reverse proxy headers
    if app.config.get("PROXY_FIX"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def _register_blueprints(app: Flask) -> None:
    """Register application blueprints."""

    from app.api.admin import admin_bp
    from app.api.analytics import analytics_bp
    from app.api.auth import auth_bp
    from app.api.challenges import challenges_bp
    from app.api.market_data import market_data_bp
    from app.api.notifications import notifications_bp
    from app.api.payments import payments_bp
    from app.api.portfolios import portfolios_bp
    from app.api.risk import risk_bp
    from app.api.trades import trades_bp
    from app.api.users import users_bp
    from app.api.websocket import websocket_bp

    # API v1 blueprints
    api_prefix = "/api/v1"
    app.register_blueprint(auth_bp, url_prefix=f"{api_prefix}/auth")
    app.register_blueprint(users_bp, url_prefix=f"{api_prefix}/users")
    app.register_blueprint(portfolios_bp, url_prefix=f"{api_prefix}/portfolios")
    app.register_blueprint(trades_bp, url_prefix=f"{api_prefix}/trades")
    app.register_blueprint(challenges_bp, url_prefix=f"{api_prefix}/challenges")
    app.register_blueprint(payments_bp, url_prefix=f"{api_prefix}/payments")
    app.register_blueprint(market_data_bp, url_prefix=f"{api_prefix}/market")
    app.register_blueprint(risk_bp, url_prefix=f"{api_prefix}/risk")
    app.register_blueprint(analytics_bp, url_prefix=f"{api_prefix}/analytics")
    app.register_blueprint(notifications_bp, url_prefix=f"{api_prefix}/notifications")
    app.register_blueprint(admin_bp, url_prefix=f"{api_prefix}/admin")
    app.register_blueprint(websocket_bp, url_prefix="/ws")

    # Health check endpoint
    @app.route("/health")
    @limiter.exempt
    def health_check():
        """Health check endpoint for load balancers."""
        return jsonify(
            {
                "status": "healthy",
                "version": app.config.get("VERSION", "1.0.0"),
                "environment": app.config.get("ENV", "unknown"),
                "database": "connected",
                "websocket": "enabled",
            }
        ), 200

    # API info endpoint
    @app.route("/api")
    @limiter.exempt
    def api_info():
        """API information endpoint."""
        return jsonify(
            {
                "name": "TradeSense AI API",
                "version": "v1",
                "description": "Professional prop trading platform API",
                "endpoints": {
                    "auth": f"{api_prefix}/auth",
                    "users": f"{api_prefix}/users",
                    "portfolios": f"{api_prefix}/portfolios",
                    "trades": f"{api_prefix}/trades",
                    "challenges": f"{api_prefix}/challenges",
                    "market": f"{api_prefix}/market",
                    "websocket": "/ws",
                },
            }
        )


def _setup_jwt_callbacks(app: Flask) -> None:
    """Setup JWT callback functions."""

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "token_expired", "message": "Token has expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"error": "invalid_token", "message": "Invalid token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify(
            {
                "error": "authorization_required",
                "message": "Authorization token is required",
            }
        ), 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return jsonify(
            {"error": "fresh_token_required", "message": "Fresh token required"}
        ), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify(
            {"error": "token_revoked", "message": "Token has been revoked"}
        ), 401

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """Return user ID for JWT identity."""
        return str(user.id) if hasattr(user, "id") else str(user)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Load user from JWT payload."""
        from app.models import User

        identity = jwt_data["sub"]
        return User.query.filter_by(id=identity).one_or_none()


def _setup_websocket_events() -> None:
    """Setup WebSocket event handlers."""

    from flask_jwt_extended import decode_token, get_jwt_identity
    from flask_socketio import emit, join_room, leave_room

    from app.services.websocket_service import WebSocketService

    ws_service = WebSocketService()

    @socketio.on("connect")
    def handle_connect(auth):
        """Handle client connection."""
        try:
            # Authenticate user via token
            if auth and "token" in auth:
                token_data = decode_token(auth["token"])
                user_id = token_data["sub"]

                # Join user-specific room for private messages
                join_room(f"user_{user_id}")

                # Join market data room for real-time updates
                join_room("market_updates")

                app.logger.info(f"User {user_id} connected via WebSocket")

                # Send connection confirmation
                emit(
                    "connected",
                    {
                        "status": "connected",
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

                # Send initial portfolio data
                ws_service.send_portfolio_update(user_id)

            else:
                emit("error", {"message": "Authentication required"})
                return False

        except Exception as e:
            app.logger.error(f"WebSocket connection error: {str(e)}")
            emit("error", {"message": "Connection failed"})
            return False

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection."""
        app.logger.info("Client disconnected from WebSocket")

    @socketio.on("join_challenge")
    def handle_join_challenge(data):
        """Handle joining challenge room for updates."""
        challenge_id = data.get("challenge_id")
        if challenge_id:
            join_room(f"challenge_{challenge_id}")
            emit("joined_challenge", {"challenge_id": challenge_id})

    @socketio.on("leave_challenge")
    def handle_leave_challenge(data):
        """Handle leaving challenge room."""
        challenge_id = data.get("challenge_id")
        if challenge_id:
            leave_room(f"challenge_{challenge_id}")
            emit("left_challenge", {"challenge_id": challenge_id})

    @socketio.on("subscribe_symbol")
    def handle_subscribe_symbol(data):
        """Handle market data subscription."""
        symbol = data.get("symbol")
        if symbol:
            join_room(f"symbol_{symbol}")
            emit("subscribed", {"symbol": symbol})

            # Send latest market data
            ws_service.send_market_data(symbol)

    @socketio.on("unsubscribe_symbol")
    def handle_unsubscribe_symbol(data):
        """Handle market data unsubscription."""
        symbol = data.get("symbol")
        if symbol:
            leave_room(f"symbol_{symbol}")
            emit("unsubscribed", {"symbol": symbol})


# Global app instance for production deployment
app = create_app()


if __name__ == "__main__":
    # Development server
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug,
        log_output=debug,
    )
