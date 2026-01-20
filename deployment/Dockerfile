# TradeSense AI Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r tradesense && useradd -r -g tradesense tradesense

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY ../pyproject.toml ../poetry.lock ./
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi \
    && pip uninstall -y poetry

# Copy source code
COPY ../src ./src

# Create logs directory
RUN mkdir -p /app/logs && chown -R tradesense:tradesense /app

# Switch to non-root user
USER tradesense

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "src.main"]