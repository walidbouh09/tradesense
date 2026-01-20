"""Auth API routers."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer

from ....infrastructure.common.context import ExecutionContext
from ....infrastructure.common.exceptions import (
    AuthenticationError,
    BusinessRuleViolationError,
    EntityNotFoundError,
    ValidationError,
)
from ....infrastructure.logging.audit_logger import AuditEventType
from ..application.commands import (
    ChangePasswordCommand,
    LoginUserCommand,
    LogoutUserCommand,
    RegisterUserCommand,
)
from ..application.handlers import (
    ChangePasswordHandler,
    GetUserHandler,
    GetUserPermissionsHandler,
    LoginUserHandler,
    LogoutUserHandler,
    RefreshTokenHandler,
    RegisterUserHandler,
    ValidateTokenHandler,
)
from ..application.queries import (
    GetUserPermissionsQuery,
    GetUserQuery,
    ValidateTokenQuery,
)
from .schemas import (
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshTokenRequest,
    RegisterUserRequest,
    TokenResponse,
    UserPermissionsResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


# Dependency to get current user from token
async def get_current_user_id(
    token: str = Depends(security),
    validate_handler: ValidateTokenHandler = Depends(),
) -> UUID:
    """Get current user ID from JWT token."""
    try:
        query = ValidateTokenQuery(token=token)
        token_payload = await validate_handler.handle(query)
        return token_payload.user_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency to get execution context from request
async def get_execution_context(request: Request) -> ExecutionContext:
    """Create execution context from request."""
    return ExecutionContext.create_for_request(request)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: RegisterUserRequest,
    context: ExecutionContext = Depends(get_execution_context),
    handler: RegisterUserHandler = Depends(),
) -> UserResponse:
    """Register a new user."""
    try:
        command = RegisterUserCommand(
            username=request.username,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )
        
        user_id = await handler.handle(command, context)
        
        # Get user details for response
        get_handler = GetUserHandler(handler.user_repository)
        user = await get_handler.handle(GetUserQuery(user_id=user_id))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User created but could not be retrieved"
            )
        
        return UserResponse(
            id=user.id,
            username=str(user.username),
            email=str(user.email),
            first_name=user._first_name,  # Access private field
            last_name=user._last_name,    # Access private field
            role=user.role.value,
            status=user.status.value,
            kyc_status=user.kyc_status.value,
            email_verified=user.is_email_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    http_request: Request,
    context: ExecutionContext = Depends(get_execution_context),
    handler: LoginUserHandler = Depends(),
) -> LoginResponse:
    """Login user and return tokens."""
    try:
        # Extract client information
        ip_address = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("User-Agent")
        
        command = LoginUserCommand(
            email=request.email,
            password=request.password,
            ip_address=ip_address,
            user_agent=user_agent,
            remember_me=request.remember_me,
        )
        
        access_token, refresh_token, user_info = await handler.handle(command, context)
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,  # 30 minutes
            user=UserResponse(
                id=UUID(user_info["user_id"]),
                username=user_info.get("username", ""),
                email=user_info["email"],
                first_name=user_info.get("first_name", ""),
                last_name=user_info.get("last_name", ""),
                role=user_info["role"],
                status="ACTIVE",  # Assuming active if login successful
                kyc_status="NOT_STARTED",  # Default value
                email_verified=True,  # Assuming verified if login successful
                created_at=context.timestamp,
            ),
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    user_id: UUID = Depends(get_current_user_id),
    context: ExecutionContext = Depends(get_execution_context),
    handler: LogoutUserHandler = Depends(),
) -> MessageResponse:
    """Logout current user."""
    try:
        command = LogoutUserCommand(user_id=user_id)
        await handler.handle(command, context)
        
        return MessageResponse(message="Logged out successfully")
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    context: ExecutionContext = Depends(get_execution_context),
    handler: RefreshTokenHandler = Depends(),
) -> TokenResponse:
    """Refresh access token using refresh token."""
    try:
        access_token, refresh_token = await handler.handle(request.refresh_token, context)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,  # 30 minutes
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    user_id: UUID = Depends(get_current_user_id),
    context: ExecutionContext = Depends(get_execution_context),
    handler: ChangePasswordHandler = Depends(),
) -> MessageResponse:
    """Change user password."""
    try:
        command = ChangePasswordCommand(
            user_id=user_id,
            current_password=request.current_password,
            new_password=request.new_password,
        )
        
        await handler.handle(command, context)
        
        return MessageResponse(message="Password changed successfully")
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password change failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    handler: GetUserHandler = Depends(),
) -> UserResponse:
    """Get current user information."""
    try:
        query = GetUserQuery(user_id=user_id)
        user = await handler.handle(query)
        
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        return UserResponse(
            id=user.id,
            username=str(user.username),
            email=str(user.email),
            first_name=user._first_name,
            last_name=user._last_name,
            role=user.role.value,
            status=user.status.value,
            kyc_status=user.kyc_status.value,
            email_verified=user.is_email_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get user")


@router.get("/me/permissions", response_model=UserPermissionsResponse)
async def get_current_user_permissions(
    user_id: UUID = Depends(get_current_user_id),
    handler: GetUserPermissionsHandler = Depends(),
) -> UserPermissionsResponse:
    """Get current user permissions."""
    try:
        query = GetUserPermissionsQuery(user_id=user_id)
        permissions = await handler.handle(query)
        
        return UserPermissionsResponse(
            user_id=user_id,
            permissions=permissions,
            roles=["trader"],  # Default role, should be fetched from user
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get permissions")


@router.post("/validate-token", response_model=dict)
async def validate_token(
    token: str = Depends(security),
    handler: ValidateTokenHandler = Depends(),
) -> dict:
    """Validate JWT token."""
    try:
        query = ValidateTokenQuery(token=token)
        token_payload = await handler.handle(query)
        
        return {
            "valid": True,
            "user_id": str(token_payload.user_id),
            "expires_at": token_payload.expires_at.isoformat(),
            "permissions": token_payload.permissions,
        }
        
    except ValidationError:
        return {"valid": False}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token validation failed")