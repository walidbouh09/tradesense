"""Auth application queries."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class GetUserQuery(BaseModel):
    """Query to get a user by ID."""
    
    user_id: UUID


class GetUserByEmailQuery(BaseModel):
    """Query to get a user by email."""
    
    email: EmailStr


class GetUserPermissionsQuery(BaseModel):
    """Query to get user permissions."""
    
    user_id: UUID


class ValidateTokenQuery(BaseModel):
    """Query to validate a JWT token."""
    
    token: str


class GetUserSessionsQuery(BaseModel):
    """Query to get active user sessions."""
    
    user_id: UUID


class SearchUsersQuery(BaseModel):
    """Query to search users."""
    
    email_pattern: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0