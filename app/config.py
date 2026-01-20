"""
TradeSense AI - Configuration Management

Professional configuration setup for different environments
with proper security, validation, and environment variable support.
"""

import os
from datetime import timedelta
from typing import Dict, List, Optional, Type

from decouple import config


class Config:
    """Base configuration class with common settings."""

    # Flask Core Settings
    SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-change-in-production")
    FLASK_ENV = config("FLASK_ENV", default="development")

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = config(
        "DATABASE_URL",
        default="postgresql://tradesense:tradesense@localhost:5432/tradesense",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = config("SQL_DEBUG", default=False, cast=bool)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": config("DB_POOL_SIZE", default=10, cast=int),
        "pool_timeout": config("DB_POOL_TIMEOUT", default=20, cast=int),
        "pool_recycle": config("DB_POOL_RECYCLE", default=3600, cast=int),
        "max_overflow": config("DB_MAX_OVERFLOW", default=20, cast=int),
    }

    # Redis Configuration
    REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = config("CACHE_TIMEOUT", default=300, cast=int)

    # JWT Configuration
    JWT_SECRET_KEY = config("JWT_SECRET_KEY", default=SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=config("JWT_ACCESS_HOURS", default=1, cast=int)
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=config("JWT_REFRESH_DAYS", default=30, cast=int)
    )
    JWT_ALGORITHM = "HS256"
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    # CORS Configuration
    CORS_ORIGINS = config(
        "CORS_ORIGINS",
        default="http://localhost:3000,http://localhost:3001,http://localhost:5173",
    )

    # Email Configuration
    MAIL_SERVER = config("MAIL_SERVER", default="smtp.gmail.com")
    MAIL_PORT = config("MAIL_PORT", default=587, cast=int)
    MAIL_USE_TLS = config("MAIL_USE_TLS", default=True, cast=bool)
    MAIL_USE_SSL = config("MAIL_USE_SSL", default=False, cast=bool)
    MAIL_USERNAME = config("MAIL_USERNAME", default="")
    MAIL_PASSWORD = config("MAIL_PASSWORD", default="")
    MAIL_DEFAULT_SENDER = config("MAIL_DEFAULT_SENDER", default="noreply@tradesense.ai")

    # Celery Configuration
    CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
    CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TIMEZONE = "UTC"
    CELERY_ENABLE_UTC = True

    # File Upload Configuration
    MAX_CONTENT_LENGTH = config(
        "MAX_CONTENT_LENGTH", default=16 * 1024 * 1024, cast=int
    )  # 16MB
    UPLOAD_FOLDER = config("UPLOAD_FOLDER", default="uploads")

    # Market Data Configuration
    ALPHA_VANTAGE_API_KEY = config("ALPHA_VANTAGE_API_KEY", default="")
    YAHOO_FINANCE_ENABLED = config("YAHOO_FINANCE_ENABLED", default=True, cast=bool)
    MARKET_DATA_CACHE_TTL = config(
        "MARKET_DATA_CACHE_TTL", default=60, cast=int
    )  # seconds

    # Payment Configuration
    STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")
    STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
    STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

    # Rate Limiting
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    # Logging Configuration
    LOG_LEVEL = config("LOG_LEVEL", default="INFO")
    LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s]: %(message)s"
    LOG_FILE = config("LOG_FILE", default="logs/tradesense.log")

    # Monitoring and Metrics
    SENTRY_DSN = config("SENTRY_DSN", default="")
    PROMETHEUS_METRICS = config("PROMETHEUS_METRICS", default=False, cast=bool)

    # WebSocket Configuration
    SOCKETIO_ASYNC_MODE = "eventlet"
    SOCKETIO_PING_TIMEOUT = config("SOCKETIO_PING_TIMEOUT", default=60, cast=int)
    SOCKETIO_PING_INTERVAL = config("SOCKETIO_PING_INTERVAL", default=25, cast=int)

    # Security Configuration
    WTF_CSRF_ENABLED = config("WTF_CSRF_ENABLED", default=True, cast=bool)
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # API Configuration
    API_TITLE = "TradeSense AI API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.2"
    API_DOCS_URL = "/docs"

    # Trading Configuration
    DEFAULT_LEVERAGE = config("DEFAULT_LEVERAGE", default=1, cast=int)
    MAX_LEVERAGE = config("MAX_LEVERAGE", default=30, cast=int)
    DEFAULT_COMMISSION = config(
        "DEFAULT_COMMISSION", default=0.0001, cast=float
    )  # 0.01%
    MIN_TRADE_AMOUNT = config("MIN_TRADE_AMOUNT", default=10, cast=float)
    MAX_TRADE_AMOUNT = config("MAX_TRADE_AMOUNT", default=100000, cast=float)

    # Risk Management
    DEFAULT_MAX_DAILY_LOSS = config(
        "DEFAULT_MAX_DAILY_LOSS", default=0.05, cast=float
    )  # 5%
    DEFAULT_MAX_TOTAL_LOSS = config(
        "DEFAULT_MAX_TOTAL_LOSS", default=0.10, cast=float
    )  # 10%
    RISK_ASSESSMENT_INTERVAL = config(
        "RISK_ASSESSMENT_INTERVAL", default=3600, cast=int
    )  # 1 hour

    # Challenge Configuration
    MIN_CHALLENGE_DURATION = config(
        "MIN_CHALLENGE_DURATION", default=30, cast=int
    )  # days
    MAX_CHALLENGE_DURATION = config(
        "MAX_CHALLENGE_DURATION", default=365, cast=int
    )  # days
    MIN_CHALLENGE_AMOUNT = config("MIN_CHALLENGE_AMOUNT", default=1000, cast=float)
    MAX_CHALLENGE_AMOUNT = config("MAX_CHALLENGE_AMOUNT", default=1000000, cast=float)
    DEFAULT_PROFIT_SHARE = config(
        "DEFAULT_PROFIT_SHARE", default=0.8, cast=float
    )  # 80%

    # Notification Configuration
    PUSH_NOTIFICATIONS_ENABLED = config(
        "PUSH_NOTIFICATIONS_ENABLED", default=True, cast=bool
    )
    EMAIL_NOTIFICATIONS_ENABLED = config(
        "EMAIL_NOTIFICATIONS_ENABLED", default=True, cast=bool
    )

    # Backup Configuration
    BACKUP_ENABLED = config("BACKUP_ENABLED", default=True, cast=bool)
    BACKUP_INTERVAL = config("BACKUP_INTERVAL", default=24, cast=int)  # hours
    BACKUP_RETENTION = config("BACKUP_RETENTION", default=30, cast=int)  # days

    @staticmethod
    def init_app(app) -> None:
        """Initialize application with this config."""
        pass


class DevelopmentConfig(Config):
    """Development environment configuration."""

    ENV = "development"
    DEBUG = True
    TESTING = False

    # More verbose logging in development
    LOG_LEVEL = "DEBUG"
    SQLALCHEMY_ECHO = True

    # Relaxed security for development
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False

    # Development-specific settings
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)  # Longer tokens for dev

    @classmethod
    def init_app(cls, app) -> None:
        """Development-specific app initialization."""
        Config.init_app(app)

        # Development logging
        import logging

        logging.basicConfig(level=logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)


class TestingConfig(Config):
    """Testing environment configuration."""

    ENV = "testing"
    DEBUG = False
    TESTING = True

    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Fast JWT tokens for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=1)

    # Disable external services in tests
    CELERY_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
    MAIL_SUPPRESS_SEND = True

    # Test-specific Redis
    REDIS_URL = "redis://localhost:6379/15"  # Different DB for tests

    @classmethod
    def init_app(cls, app) -> None:
        """Testing-specific app initialization."""
        Config.init_app(app)

        # Silence logging during tests
        import logging

        logging.disable(logging.CRITICAL)


class ProductionConfig(Config):
    """Production environment configuration."""

    ENV = "production"
    DEBUG = False
    TESTING = False

    # Production security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    WTF_CSRF_ENABLED = True

    # Production database with connection pooling
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "max_overflow": 40,
        "pool_pre_ping": True,
    }

    # Shorter JWT tokens for security
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Production logging
    LOG_LEVEL = "WARNING"

    # Enable monitoring
    PROMETHEUS_METRICS = True

    @classmethod
    def init_app(cls, app) -> None:
        """Production-specific app initialization."""
        Config.init_app(app)

        # Production logging setup
        import logging
        from logging.handlers import RotatingFileHandler, SMTPHandler

        # File handler for errors
        if not app.debug:
            file_handler = RotatingFileHandler(
                cls.LOG_FILE, maxBytes=10485760, backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

            # Email handler for critical errors
            if cls.MAIL_SERVER:
                auth = None
                if cls.MAIL_USERNAME or cls.MAIL_PASSWORD:
                    auth = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
                secure = None
                if cls.MAIL_USE_TLS:
                    secure = ()
                mail_handler = SMTPHandler(
                    mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
                    fromaddr=cls.MAIL_DEFAULT_SENDER,
                    toaddrs=["admin@tradesense.ai"],
                    subject="TradeSense AI Application Error",
                    credentials=auth,
                    secure=secure,
                )
                mail_handler.setLevel(logging.ERROR)
                app.logger.addHandler(mail_handler)

        # Setup Sentry for error tracking
        if cls.SENTRY_DSN:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_sdk.init(
                dsn=cls.SENTRY_DSN,
                integrations=[
                    FlaskIntegration(),
                    SqlalchemyIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=cls.ENV,
            )


class StagingConfig(ProductionConfig):
    """Staging environment configuration."""

    ENV = "staging"
    DEBUG = True  # Enable debug for staging

    # Staging-specific settings
    LOG_LEVEL = "INFO"

    # Longer JWT tokens for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)

    # Enable detailed logging
    SQLALCHEMY_ECHO = True


# Configuration mapping
config_map: Dict[str, Type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name: Optional[str] = None) -> Type[Config]:
    """
    Get configuration class by name.

    Args:
        config_name: Configuration name (development, testing, staging, production)

    Returns:
        Configuration class
    """
    if not config_name:
        config_name = os.getenv("FLASK_ENV", "development")

    return config_map.get(config_name, DevelopmentConfig)


# Export current configuration
current_config = get_config()
