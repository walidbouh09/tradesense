"""Auth application commands."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterUserCommand(BaseModel):
    """Command to register a new user."""
    
    email: EmailStr
    password: str = Field(..., min_length=12)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    role: Optional[str] = Field(None, pattern="^(trader|risk_manager|compliance_officer|admin)$")


class LoginUserCommand(BaseModel):
    """Command to login a user."""
    
    email: EmailStr
    password: str
    ip_address: str
    user_agent: Optional[str] = None
    remember_me: bool = False


class LogoutUserCommand(BaseModel):
    """Command to logout a user."""
    
    user_id: UUID
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class ChangePasswordCommand(BaseModel):
    """Command to change user password."""
    
    user_id: UUID
    current_password: str
    new_password: str = Field(..., min_length=12)


class ResetPasswordCommand(BaseModel):
    """Command to reset user password."""
    
    email: EmailStr
    reset_token: str
    new_password: str = Field(..., min_length=12)


class ActivateUserCommand(BaseModel):
    """Command to activate a user account."""
    
    user_id: UUID
    activated_by: UUID
    reason: Optional[str] = None


class DeactivateUserCommand(BaseModel):
    """Command to deactivate a user account."""
    
    user_id: UUID
    deactivated_by: UUID
    reason: str = Field(..., min_length=1)


class AssignRoleCommand(BaseModel):
    """Command to assign role to user."""
    
    user_id: UUID
    role: str = Field(..., pattern="^(trader|risk_manager|compliance_officer|admin)$")
    assigned_by: UUID
    reason: Optional[str] = None