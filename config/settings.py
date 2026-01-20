"""Application settings and configuration."""

from typing import Optional

from pydantic import Fieldgit
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    host: str = Field("localhost", description="Database host")
    port: int = Field(5432, description="Database port")
    username: str = Field("tradesense", description="Database username")
    password: str = Field("password", description="Database password")
    database: str = Field("tradesense", description="Database name")
    
    @property
    def url(self) -> str:
        """Get database URL."""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    host: str = Field("localhost", description="Redis host")
    port: int = Field(6379, description="Redis port")
    db: int = Field(0, description="Redis database number")
    password: Optional[str] = Field(None, description="Redis password")
    
    class Config:
        env_prefix = "REDIS_"


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    secret_key: str = Field("your-secret-key-change-in-production", description="JWT secret key")
    algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(30, description="Access token expiration in minutes")
    
    class Config:
        env_prefix = "SECURITY_"


class AppSettings(BaseSettings):
    """Application configuration settings."""
    
    title: str = Field("TradeSense AI", description="Application title")
    description: str = Field("FinTech Prop Trading SaaS Backend", description="Application description")
    version: str = Field("0.1.0", description="Application version")
    debug: bool = Field(False, description="Debug mode")
    
    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    
    class Config:
        env_prefix = "APP_"


# Global settings instance
settings = AppSettings()