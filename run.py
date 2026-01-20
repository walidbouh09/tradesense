#!/usr/bin/env python3
"""
TradeSense AI - Main Application Runner

Professional Flask application entry point with proper initialization,
error handling, and development/production support.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import after path setup
from app import create_app, socketio
from app.config import get_config
from app.models import db
from app.utils.logger import get_logger


def create_tables():
    """Create database tables if they don't exist."""
    try:
        with app.app_context():
            db.create_all()
            print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        sys.exit(1)


def main():
    """Main application entry point."""
    # Get configuration
    config_name = os.getenv("FLASK_ENV", "development")
    print(f"🚀 Starting TradeSense AI in {config_name} mode")

    try:
        # Create Flask application
        global app
        app = create_app(config_name)
        logger = get_logger(__name__)

        # Create database tables
        create_tables()

        # Get server configuration
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", 5000))
        debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

        print(f"🌐 Server will run on http://{host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        print(f"📊 WebSocket support: Enabled")

        # Log startup info
        logger.info(f"TradeSense AI starting on {host}:{port}")
        logger.info(f"Environment: {config_name}")
        logger.info(f"Debug: {debug}")

        # Run with SocketIO support
        socketio.run(
            app, host=host, port=port, debug=debug, use_reloader=debug, log_output=debug
        )

    except KeyboardInterrupt:
        print("\n👋 TradeSense AI shutting down gracefully...")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Failed to start TradeSense AI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
