"""Environment-based configuration management with financial compliance validation."""

import os
from typing import List, Optional, Set
from pathlib import Path

from pydantic import BaseSettings, Field, SecretStr, validator
from pydantic.env_settings import SettingsSourceCallable


class DatabaseConfig(BaseSettings):
    """Database configuration with connection pooling and security."""
    
    host: str = Field("localhost", description="Database host")
    port: int = Field(5432, description="Database port", ge=1, le=65535)
    username: str = Field(..., description="Database username")
    password: SecretStr = Field(..., description="Database password")
    database: str = Field(..., description="Database name")
    
    # Connection pool settings
    pool_size: int = Field(20, description="Connection pool size", ge=5, le=100)
    max_overflow: int = Field(30, description="Max pool overflow", ge=0, le=100)
    pool_timeout: int = Field(30, description="Pool timeout seconds", ge=5, le=300)
    pool_recycle: int = Field(3600, description="Pool recycle seconds", ge=300)
    
    # SSL settings
    ssl_mode: str = Field("require", description="SSL mode")
    ssl_cert_path: Optional[str] = Field(None, description="SSL certificate path")
    ssl_key_path: Optional[str] = Field(None, description="SSL key path")
    ssl_ca_path: Optional[str] = Field(None, description="SSL CA path")
    
    @property
    def connection_url(self) -> str:
        """Build database connection URL with SSL parameters."""
        base_url = f"postgresql+asyncpg://{self.username}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"
        
        ssl_params = []
        if self.ssl_mode != "disable":
            ssl_params.append(f"sslmode={self.ssl_mode}")
        if self.ssl_cert_path:
            ssl_params.append(f"sslcert={self.ssl_cert_path}")
        if self.ssl_key_path:
            ssl_params.append(f"sslkey={self.ssl_key_path}")
        if self.ssl_ca_path:
            ssl_params.append(f"sslrootcert={self.ssl_ca_path}")
        
        if ssl_params:
            base_url += "?" + "&".join(ssl_params)
        
        return base_url
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate database password meets security requirements."""
        password = v.get_secret_value()
        if len(password) < 12:
            raise ValueError("Database password must be at least 12 characters")
        return v
    
    class Config:
        env_prefix = "DB_"


class SecurityConfig(BaseSettings):
    """Security configuration for JWT, encryption, and hashing."""
    
    # JWT Configuration
    jwt_secret_key: SecretStr = Field(..., description="JWT signing secret")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expiry", ge=5, le=1440)
    refresh_token_expire_days: int = Field(7, description="Refresh token expiry", ge=1, le=30)
    
    # Password Hashing
    password_salt_rounds: int = Field(12, description="Bcrypt salt rounds", ge=10, le=15)
    password_pepper: SecretStr = Field(..., description="Global password pepper")
    
    # Encryption
    encryption_key: SecretStr = Field(..., description="AES encryption key")
    key_rotation_days: int = Field(90, description="Key rotation interval", ge=30, le=365)
    
    # Session Management
    session_timeout_minutes: int = Field(60, description="Session timeout", ge=15, le=480)
    max_concurrent_sessions: int = Field(5, description="Max concurrent sessions", ge=1, le=20)
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(100, description="Rate limit per minute", ge=10, le=1000)
    rate_limit_burst_size: int = Field(20, description="Rate limit burst", ge=5, le=100)
    
    @validator('jwt_secret_key')
    def validate_jwt_secret(cls, v):
        """Validate JWT secret key strength."""
        secret = v.get_secret_value()
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        return v
    
    @validator('encryption_key')
    def validate_encryption_key(cls, v):
        """Validate encryption key format."""
        key = v.get_secret_value()
        if len(key) != 32:  # 256-bit key
            raise ValueError("Encryption key must be exactly 32 bytes (256 bits)")
        return v
    
    class Config:
        env_prefix = "SECURITY_"


class LoggingConfig(BaseSettings):
    """Logging configuration with audit and compliance features."""
    
    # Basic logging
    level: str = Field("INFO", description="Log level")
    format: str = Field("json", description="Log format")
    
    # Audit logging
    audit_enabled: bool = Field(True, description="Enable audit logging")
    audit_retention_days: int = Field(2555, description="Audit retention (7 years)", ge=365)
    audit_encryption_enabled: bool = Field(True, description="Encrypt audit logs")
    
    # Sensitive data handling
    sensitive_fields: List[str] = Field(
        default=[
            "password", "ssn", "account_number", "routing_number",
            "credit_card", "bank_account", "api_key", "token"
        ],
        description="Fields to mask in logs"
    )
    
    # Log destinations
    console_enabled: bool = Field(True, description="Enable console logging")
    file_enabled: bool = Field(True, description="Enable file logging")
    syslog_enabled: bool = Field(False, description="Enable syslog")
    
    # File logging settings
    log_file_path: str = Field("logs/tradesense.log", description="Log file path")
    log_file_max_size: int = Field(100, description="Max log file size (MB)", ge=10, le=1000)
    log_file_backup_count: int = Field(10, description="Log file backup count", ge=1, le=100)
    
    # Correlation and tracing
    correlation_id_header: str = Field("X-Correlation-ID", description="Correlation ID header")
    trace_sampling_rate: float = Field(0.1, description="Trace sampling rate", ge=0.0, le=1.0)
    
    @validator('level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    class Config:
        env_prefix = "LOG_"


class MessagingConfig(BaseSettings):
    """Messaging and event bus configuration."""
    
    # Event bus type
    event_bus_type: str = Field("in_memory", description="Event bus implementation")
    
    # Redis configuration (for Redis event bus)
    redis_host: str = Field("localhost", description="Redis host")
    redis_port: int = Field(6379, description="Redis port", ge=1, le=65535)
    redis_db: int = Field(0, description="Redis database", ge=0, le=15)
    redis_password: Optional[SecretStr] = Field(None, description="Redis password")
    redis_ssl: bool = Field(False, description="Use Redis SSL")
    
    # Event processing
    event_batch_size: int = Field(100, description="Event batch size", ge=1, le=1000)
    event_retry_attempts: int = Field(3, description="Event retry attempts", ge=1, le=10)
    event_retry_delay_seconds: int = Field(5, description="Event retry delay", ge=1, le=300)
    
    # Outbox pattern
    outbox_enabled: bool = Field(True, description="Enable outbox pattern")
    outbox_batch_size: int = Field(50, description="Outbox batch size", ge=1, le=500)
    outbox_processing_interval_seconds: int = Field(10, description="Outbox processing interval", ge=1, le=300)
    
    @validator('event_bus_type')
    def validate_event_bus_type(cls, v):
        """Validate event bus type."""
        valid_types = {"in_memory", "redis", "rabbitmq", "kafka"}
        if v not in valid_types:
            raise ValueError(f"Event bus type must be one of {valid_types}")
        return v
    
    class Config:
        env_prefix = "MESSAGING_"


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""
    
    # Health checks
    health_check_enabled: bool = Field(True, description="Enable health checks")
    health_check_interval_seconds: int = Field(30, description="Health check interval", ge=10, le=300)
    
    # Metrics
    metrics_enabled: bool = Field(True, description="Enable metrics collection")
    metrics_port: int = Field(9090, description="Metrics port", ge=1024, le=65535)
    
    # Alerting
    alerting_enabled: bool = Field(True, description="Enable alerting")
    alert_webhook_url: Optional[str] = Field(None, description="Alert webhook URL")
    
    # Performance monitoring
    slow_query_threshold_ms: int = Field(1000, description="Slow query threshold", ge=100, le=10000)
    request_timeout_seconds: int = Field(30, description="Request timeout", ge=5, le=300)
    
    class Config:
        env_prefix = "MONITORING_"


class AppSettings(BaseSettings):
    """Main application settings with all subsystem configurations."""
    
    # Application metadata
    app_name: str = Field("TradeSense AI", description="Application name")
    app_version: str = Field("0.1.0", description="Application version")
    environment: str = Field("development", description="Environment name")
    debug: bool = Field(False, description="Debug mode")
    
    # API settings
    api_host: str = Field("0.0.0.0", description="API host")
    api_port: int = Field(8000, description="API port", ge=1024, le=65535)
    api_workers: int = Field(1, description="API workers", ge=1, le=32)
    
    # CORS settings
    cors_origins: List[str] = Field(["*"], description="CORS allowed origins")
    cors_credentials: bool = Field(True, description="CORS allow credentials")
    
    # Subsystem configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment name."""
        valid_envs = {"development", "testing", "staging", "production"}
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v
    
    def validate_financial_compliance(self) -> None:
        """Validate configuration meets financial compliance requirements."""
        errors = []
        
        # Production environment checks
        if self.environment == "production":
            if self.debug:
                errors.append("Debug mode must be disabled in production")
            
            if self.security.access_token_expire_minutes > 60:
                errors.append("Access token expiry must be <= 60 minutes in production")
            
            if self.logging.audit_retention_days < 2555:  # 7 years
                errors.append("Audit retention must be at least 7 years for financial compliance")
            
            if not self.logging.audit_encryption_enabled:
                errors.append("Audit log encryption must be enabled in production")
            
            if self.database.ssl_mode == "disable":
                errors.append("Database SSL must be enabled in production")
        
        # Security checks
        if self.security.password_salt_rounds < 12:
            errors.append("Password salt rounds must be at least 12 for financial security")
        
        if not self.messaging.outbox_enabled:
            errors.append("Outbox pattern must be enabled for financial transaction reliability")
        
        if errors:
            raise ValueError(f"Financial compliance validation failed: {'; '.join(errors)}")
    
    def get_secrets_summary(self) -> Set[str]:
        """Get summary of configured secrets (for audit purposes)."""
        secrets = set()
        
        if self.database.password:
            secrets.add("database_password")
        if self.security.jwt_secret_key:
            secrets.add("jwt_secret_key")
        if self.security.password_pepper:
            secrets.add("password_pepper")
        if self.security.encryption_key:
            secrets.add("encryption_key")
        if self.messaging.redis_password:
            secrets.add("redis_password")
        
        return secrets
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """Customize settings sources priority."""
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )


# Global settings instance
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get application settings singleton."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
        _settings.validate_financial_compliance()
    return _settings


def reload_settings() -> AppSettings:
    """Reload settings from environment (for hot-reload)."""
    global _settings
    _settings = AppSettings()
    _settings.validate_financial_compliance()
    return _settings