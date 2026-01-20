"""
TradeSense Pro - Configuration Management

Production-ready configuration management with:
- Environment-based settings
- Type validation with Pydantic
- Secret management
- Database configuration
- Redis configuration
- Security settings
- Logging configuration
"""

import secrets
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, BaseSettings, EmailStr, PostgresDsn, validator


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """

    # Project Information
    PROJECT_NAME: str = "TradeSense Pro"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Professional Proprietary Trading Platform"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    TESTING: bool = False

    # API Configuration
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Trusted Hosts (Security)
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "tradesense"
    POSTGRES_PASSWORD: str = "tradesense_password"
    POSTGRES_DB: str = "tradesense_pro"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[PostgresDsn] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v

        password = values.get("REDIS_PASSWORD")
        auth = f":{password}@" if password else ""

        return f"redis://{auth}{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/{values.get('REDIS_DB')}"

    # Celery Configuration (Background Tasks)
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @validator("CELERY_BROKER_URL", pre=True)
    def assemble_celery_broker(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        return values.get("REDIS_URL", "redis://localhost:6379/0")

    @validator("CELERY_RESULT_BACKEND", pre=True)
    def assemble_celery_result_backend(
        cls, v: Optional[str], values: Dict[str, Any]
    ) -> str:
        if isinstance(v, str):
            return v
        return values.get("REDIS_URL", "redis://localhost:6379/0")

    # Security Configuration
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12
    PASSWORD_MIN_LENGTH: int = 8

    # Email Configuration
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    @validator("EMAILS_FROM_NAME")
    def get_project_name(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if not v:
            return values["PROJECT_NAME"]
        return v

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48
    EMAIL_TEMPLATES_DIR: str = "app/email-templates/build"
    EMAILS_ENABLED: bool = False

    @validator("EMAILS_ENABLED", pre=True)
    def get_emails_enabled(cls, v: bool, values: Dict[str, Any]) -> bool:
        return bool(
            values.get("SMTP_HOST")
            and values.get("SMTP_PORT")
            and values.get("EMAILS_FROM_EMAIL")
        )

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # Market Data Configuration
    MARKET_DATA_PROVIDER: str = "alpha_vantage"  # alpha_vantage, yahoo, polygon
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    POLYGON_API_KEY: Optional[str] = None

    # Trading Configuration
    DEFAULT_LEVERAGE: float = 1.0
    MAX_LEVERAGE: float = 100.0
    MIN_TRADE_AMOUNT: float = 0.01
    MAX_TRADE_AMOUNT: float = 1000000.0

    # Challenge Configuration
    DEFAULT_CHALLENGE_DURATION_DAYS: int = 30
    MAX_DAILY_DRAWDOWN: float = 0.05  # 5%
    MAX_TOTAL_DRAWDOWN: float = 0.10  # 10%
    PROFIT_TARGET: float = 0.10  # 10%

    # Payment Configuration
    PAYMENT_PROVIDER: str = "stripe"  # stripe, paypal, mock
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_WEBHOOK_ID: Optional[str] = None
    PAYPAL_SANDBOX: bool = True

    # Monitoring Configuration
    SENTRY_DSN: Optional[str] = None

    @validator("SENTRY_DSN", pre=True)
    def sentry_dsn_can_be_blank(cls, v: str) -> Optional[str]:
        if len(v) == 0:
            return None
        return v

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # WebSocket Configuration
    WEBSOCKET_ENABLED: bool = True
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30

    # Cache Configuration
    CACHE_TTL: int = 300  # 5 minutes
    CACHE_ENABLED: bool = True

    # Feature Flags
    FEATURE_SOCIAL_TRADING: bool = False
    FEATURE_COPY_TRADING: bool = False
    FEATURE_ADVANCED_ANALYTICS: bool = True
    FEATURE_MOBILE_APP: bool = False

    # Admin Configuration
    FIRST_SUPERUSER_EMAIL: EmailStr = "admin@tradesense.ma"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"  # Change in production!

    # Internationalization
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: List[str] = ["en", "fr", "ar"]
    TIMEZONE: str = "Africa/Casablanca"

    # Business Configuration
    COMPANY_NAME: str = "TradeSense Morocco"
    COMPANY_ADDRESS: str = "Casablanca, Morocco"
    COMPANY_EMAIL: EmailStr = "contact@tradesense.ma"
    COMPANY_PHONE: str = "+212 522 123 456"

    # Compliance
    KYC_ENABLED: bool = True
    AML_ENABLED: bool = True
    GDPR_COMPLIANCE: bool = True

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


class DevelopmentSettings(Settings):
    """Development environment settings."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    POSTGRES_DB: str = "tradesense_dev"

    # CORS - Allow all origins in development
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Email - Use console backend in development
    EMAILS_ENABLED: bool = False

    # Logging
    LOG_LEVEL: str = "DEBUG"

    # Security - Weaker settings for development
    BCRYPT_ROUNDS: int = 4
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Payment - Use sandbox/test mode
    PAYPAL_SANDBOX: bool = True
    PAYMENT_PROVIDER: str = "mock"


class TestingSettings(Settings):
    """Testing environment settings."""

    ENVIRONMENT: str = "testing"
    TESTING: bool = True
    DEBUG: bool = True

    # Database - Use separate test database
    POSTGRES_DB: str = "tradesense_test"

    # Redis - Use separate test database
    REDIS_DB: int = 1

    # Disable external services
    EMAILS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    # Fast password hashing for tests
    BCRYPT_ROUNDS: int = 1

    # Short token expiry for testing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5

    # Mock payment provider
    PAYMENT_PROVIDER: str = "mock"


class ProductionSettings(Settings):
    """Production environment settings."""

    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # Security
    TRUSTED_HOSTS: List[str] = ["tradesense.ma", "api.tradesense.ma"]

    # Strong password hashing
    BCRYPT_ROUNDS: int = 15

    # Shorter token expiry in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Enable all security features
    RATE_LIMIT_ENABLED: bool = True
    KYC_ENABLED: bool = True
    AML_ENABLED: bool = True

    # Logging
    LOG_LEVEL: str = "WARNING"

    # Disable debug features
    FEATURE_MOBILE_APP: bool = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings based on environment.

    Uses LRU cache to avoid re-reading environment variables.

    Returns:
        Settings: Application settings instance
    """
    import os

    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment == "production":
        return ProductionSettings()
    elif environment == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Export settings instance for easy importing
settings = get_settings()
