"""SQLAlchemy models for auth domain."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserModel(Base):
    """SQLAlchemy model for User aggregate."""
    
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    
    # User attributes
    role = Column(String(20), nullable=False, default="USER", index=True)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    kyc_status = Column(String(20), nullable=False, default="NOT_STARTED")
    
    # Email verification
    email_verified = Column(Boolean, nullable=False, default=False)
    
    # Security tracking
    failed_login_count = Column(Integer, nullable=False, default=0)
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, username={self.username}, email={self.email})>"


class LoginAttemptModel(Base):
    """SQLAlchemy model for login attempts."""
    
    __tablename__ = "login_attempts"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(String(255), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self) -> str:
        return f"<LoginAttemptModel(user_id={self.user_id}, success={self.success}, timestamp={self.timestamp})>"


class UserSessionModel(Base):
    """SQLAlchemy model for user sessions."""
    
    __tablename__ = "user_sessions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<UserSessionModel(user_id={self.user_id}, session_id={self.session_id[:8]}...)>"