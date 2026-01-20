# TradeSense AI Backend Service - Production Dockerfile
# ====================================================
# Python 3.11 slim for minimal attack surface
FROM python:3.11-slim

# Metadata for container management
LABEL maintainer="TradeSense AI Team"
LABEL description="Flask + SocketIO backend for prop trading platform"
LABEL version="1.0"

# Environment setup for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Flask production settings
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    # Python path for imports
    PYTHONPATH=/app

# Install system dependencies for Python packages
# Keeping it minimal for security and image size
RUN apt-get update && apt-get install -y \
    # Required for some Python packages (if needed)
    build-essential \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r tradesense && useradd -r -g tradesense tradesense

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY backend/requirements.txt ./

# Install Python dependencies
# --no-cache-dir reduces image size
# --only-binary=all ensures no compilation (faster, more secure)
RUN pip install --no-cache-dir --only-binary=all -r requirements.txt

# Copy application code
# Using .dockerignore to exclude unnecessary files
COPY app ./app
COPY src ./src
COPY database ./database

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chown -R tradesense:tradesense /app

# Switch to non-root user
USER tradesense

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Expose port (configurable via environment)
EXPOSE $PORT

# Default command: Gunicorn with eventlet workers for SocketIO
# eventlet required for Flask-SocketIO WebSocket support
CMD gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT --access-logfile /app/logs/access.log --error-logfile /app/logs/error.log --log-level info --timeout 30 --keep-alive 10 app.main:app