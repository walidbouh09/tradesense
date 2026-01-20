#!/usr/bin/env python3
"""
TradeSense AI - Robust Backend Startup Script

A professional startup script that handles all the backend initialization,
error handling, and monitoring for the TradeSense AI trading platform.
"""

import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("backend_startup.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def check_port_available(port, host="localhost"):
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result != 0  # Port is available if connection failed
    except Exception:
        return True  # Assume available if we can't check


def kill_process_on_port(port):
    """Kill any process using the specified port."""
    try:
        import subprocess

        # Try to find and kill process on port
        if os.name == "nt":  # Windows
            subprocess.run(["netstat", "-ano"], capture_output=True)
        else:  # Unix-like
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"], capture_output=True, text=True
                )
                if result.stdout.strip():
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["kill", "-9", pid], capture_output=True)
                    return True
            except FileNotFoundError:
                pass
    except Exception as e:
        print(f"Warning: Could not kill process on port {port}: {e}")
    return False


def start_backend():
    """Start the TradeSense AI backend."""
    logger = setup_logging()

    print("🚀 TradeSense AI Backend Startup")
    print("=" * 50)

    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (
        python_version.major == 3 and python_version.minor < 8
    ):
        logger.error(
            f"Python 3.8+ required, found {python_version.major}.{python_version.minor}"
        )
        sys.exit(1)

    logger.info(
        f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}"
    )

    # Check if backend file exists
    backend_file = project_root / "app_simple.py"
    if not backend_file.exists():
        logger.error(f"❌ Backend file not found: {backend_file}")
        sys.exit(1)

    logger.info(f"✅ Backend file found: {backend_file}")

    # Check port availability
    port = 5000
    if not check_port_available(port):
        logger.warning(f"⚠️  Port {port} is in use, attempting to free it...")
        if kill_process_on_port(port):
            logger.info(f"✅ Freed port {port}")
            time.sleep(2)
        else:
            logger.error(f"❌ Could not free port {port}")
            sys.exit(1)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("🛑 Received shutdown signal, stopping backend...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Change to project directory
    os.chdir(project_root)

    # Import and start the Flask app
    try:
        logger.info("📦 Importing Flask application...")

        # Import the main application
        from app_simple import app, db

        logger.info("✅ Flask application imported successfully")

        # Ensure database is set up
        with app.app_context():
            logger.info("🗄️  Setting up database...")
            db.create_all()
            logger.info("✅ Database setup complete")

        logger.info("🌐 Starting Flask server...")
        logger.info(f"📍 Backend will be available at: http://localhost:{port}")
        logger.info("🔑 Demo Credentials:")
        logger.info("   - Admin: admin@tradesense.ai / admin123456")
        logger.info("   - Demo Trader: demo.trader@tradesense.ai / demo123456")

        print("\n" + "=" * 50)
        print("🎉 TradeSense AI Backend is starting...")
        print(f"🌐 URL: http://localhost:{port}")
        print(f"📊 Health: http://localhost:{port}/health")
        print(f"📚 API Info: http://localhost:{port}/api")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        # Start the Flask application
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,  # Set to False for production-like behavior
            use_reloader=False,  # Disable reloader to avoid issues
            threaded=True,  # Enable threading for better performance
        )

    except ImportError as e:
        logger.error(f"❌ Failed to import Flask application: {e}")
        logger.error("Make sure all dependencies are installed:")
        logger.error("pip install flask flask-cors flask-sqlalchemy marshmallow")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Failed to start backend: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        start_backend()
    except KeyboardInterrupt:
        print("\n🛑 Backend shutdown by user")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
