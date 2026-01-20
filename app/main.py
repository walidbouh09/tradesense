"""
TradeSense AI Flask Application with SocketIO Integration

Core application factory with WebSocket support for real-time updates.
Separated from routes to maintain clean architecture - WebSocket is output only.
"""

import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

# Global SocketIO instance - accessible throughout the application
# This is the OUTPUT CHANNEL for real-time updates, not business logic
socketio = SocketIO()

# CORS origins for frontend
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173')


def create_app(config_object=None):
    """
    Flask application factory with SocketIO integration.

    Returns a fully configured Flask app with WebSocket support.

    Why SocketIO is initialized here (not in routes):
    - SocketIO is infrastructure, not business logic
    - Routes handle HTTP API, SocketIO handles real-time output
    - Clean separation: domain events → event bus → SocketIO → frontend
    - Event bus can emit to SocketIO without importing Flask context
    """
    app = Flask(__name__)

    # Load configuration
    if config_object:
        app.config.from_object(config_object)
    else:
        # Default configuration
        app.config.update(
            SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
            DEBUG=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        )

    # Initialize CORS for frontend integration
    # Allows React app to connect from different origin
    CORS(app, origins=CORS_ORIGINS.split(','))

    # Initialize SocketIO with eventlet for production performance
    # async_mode='eventlet' provides better scalability than threading
    socketio.init_app(
        app,
        cors_allowed_origins=CORS_ORIGINS.split(','),
        async_mode='eventlet',  # Production-grade async handling
        logger=app.config['DEBUG'],
        engineio_logger=app.config['DEBUG'],
    )

    # Register blueprints (routes)
    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register SocketIO event handlers
    # These are separate from HTTP routes for clean architecture
    from app.websocket import register_socketio_handlers, setup_event_bus_forwarding
    register_socketio_handlers(socketio)

    # Set up event bus forwarding to WebSocket
    # This connects domain events to real-time client updates
    setup_event_bus_forwarding()

    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers."""
        return {'status': 'healthy', 'websocket': 'enabled'}

    return app


# Global reference for running the application
# Used by gunicorn/eventlet in production
app = create_app()

if __name__ == '__main__':
    # Development mode with debug
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)