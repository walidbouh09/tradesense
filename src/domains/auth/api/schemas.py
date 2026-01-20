"""Auth API schemas (DTOs)."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterUserRequest(BaseModel):
    """Request schema for user registration."""
    
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=12, description="Password")
    first_name: str = Field(..., min_length=1, max_length=50, description="First name")
    last_name: str = Field(..., min_length=1, max_length=50, description="Last name")


class LoginRequest(BaseModel):
    """Request schema for user login."""
    
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(False, description="Remember login")


class ChangePasswordRequest(BaseModel):
    """Request schema for password change."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=12, description="New password")


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset."""
    
    email: EmailStr = Field(..., description="Email address")


class ConfirmPasswordResetRequest(BaseModel):
    """Request schema for password reset confirmation."""
    
    reset_token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=12, description="New password")


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""
    
    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """Response schema for user information."""
    
    id: UUID
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    kyc_status: str
    email_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Response schema for successful login."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class TokenResponse(BaseModel):
    """Response schema for token operations."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserPermissionsResponse(BaseModel):
    """Response schema for user permissions."""
    
    user_id: UUID
    permissions: List[str]
    roles: List[str]


class MessageResponse(BaseModel):
    """Generic message response."""
    
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response schema."""
    
    error: str
    message: str
    details: Optional[dict] = None


class UserListResponse(BaseModel):
    """Response schema for user list."""
    
    users: List[UserResponse]
    total: int
    limit: int
    offset: int


class LoginAttemptResponse(BaseModel):
    """Response schema for login attempt information."""
    
    ip_address: str
    user_agent: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class UserSecurityResponse(BaseModel):
    """Response schema for user security information."""
    
    user_id: UUID
    two_factor_enabled: bool
    two_factor_method: Optional[str] = None
    login_notifications: bool
    session_timeout_minutes: int
    password_changed_at: datetime
    recent_login_attempts: List[LoginAttemptResponse]
    failed_login_count: int
    account_locked: bool