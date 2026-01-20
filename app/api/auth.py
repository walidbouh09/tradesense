"""
TradeSense AI - Authentication API

Professional authentication endpoints with JWT tokens, proper security,
rate limiting, and comprehensive user management for the trading platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, ValidationError, fields, validate
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, UserStatus, db
from app.utils.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.utils.exceptions import ValidationError as CustomValidationError
from app.utils.logger import get_logger, log_security_event

# Create blueprint
auth_bp = Blueprint("auth", __name__)
logger = get_logger(__name__)

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)


# Validation Schemas
class RegisterSchema(Schema):
    """Schema for user registration."""

    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    phone = fields.Str(validate=validate.Length(max=20))
    country = fields.Str(validate=validate.Length(max=50))
    experience_level = fields.Str(
        validate=validate.OneOf(["beginner", "intermediate", "advanced"])
    )
    terms_accepted = fields.Bool(required=True, validate=validate.Equal(True))

    def validate_passwords_match(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError(
                "Passwords do not match", field_name="confirm_password"
            )


class LoginSchema(Schema):
    """Schema for user login."""

    email = fields.Email(required=True)
    password = fields.Str(required=True)
    remember_me = fields.Bool(missing=False)


class PasswordResetRequestSchema(Schema):
    """Schema for password reset request."""

    email = fields.Email(required=True)


class PasswordResetSchema(Schema):
    """Schema for password reset."""

    token = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    confirm_password = fields.Str(required=True)

    def validate_passwords_match(self, data, **kwargs):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError(
                "Passwords do not match", field_name="confirm_password"
            )


class ChangePasswordSchema(Schema):
    """Schema for password change."""

    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    confirm_password = fields.Str(required=True)

    def validate_passwords_match(self, data, **kwargs):
        if data.get("new_password") != data.get("confirm_password"):
            raise ValidationError(
                "Passwords do not match", field_name="confirm_password"
            )


class UpdateProfileSchema(Schema):
    """Schema for profile updates."""

    first_name = fields.Str(validate=validate.Length(min=2, max=100))
    last_name = fields.Str(validate=validate.Length(min=2, max=100))
    phone = fields.Str(validate=validate.Length(max=20))
    country = fields.Str(validate=validate.Length(max=50))
    city = fields.Str(validate=validate.Length(max=100))
    experience_level = fields.Str(
        validate=validate.OneOf(["beginner", "intermediate", "advanced"])
    )


# Helper Functions
def validate_password_strength(password: str) -> bool:
    """
    Validate password strength.

    Requirements:
    - At least 8 characters
    - Contains uppercase and lowercase letters
    - Contains at least one number
    - Contains at least one special character
    """
    import re

    if len(password) < 8:
        return False

    if not re.search(r"[A-Z]", password):
        return False

    if not re.search(r"[a-z]", password):
        return False

    if not re.search(r"\d", password):
        return False

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False

    return True


def create_tokens_for_user(user: User, remember_me: bool = False) -> Dict[str, str]:
    """Create access and refresh tokens for user."""
    additional_claims = {
        "user_role": user.role.value,
        "user_status": user.status.value,
        "is_verified": user.is_verified,
    }

    # Set token expiration based on remember_me
    access_expires = timedelta(hours=24) if remember_me else timedelta(hours=1)
    refresh_expires = timedelta(days=30) if remember_me else timedelta(days=7)

    access_token = create_access_token(
        identity=user.id,
        additional_claims=additional_claims,
        expires_delta=access_expires,
    )

    refresh_token = create_refresh_token(
        identity=user.id, expires_delta=refresh_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": int(access_expires.total_seconds()),
    }


# Authentication Routes
@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    """
    Register a new user account.

    Rate limited to 5 attempts per minute to prevent abuse.
    """
    try:
        # Validate input data
        schema = RegisterSchema()
        data = schema.load(request.get_json())

        # Check password strength
        if not validate_password_strength(data["password"]):
            raise CustomValidationError(
                message="Password does not meet security requirements",
                details={
                    "requirements": [
                        "At least 8 characters",
                        "Contains uppercase and lowercase letters",
                        "Contains at least one number",
                        "Contains at least one special character",
                    ]
                },
            )

        # Check if user already exists
        existing_user = User.query.filter_by(email=data["email"].lower()).first()
        if existing_user:
            raise ConflictError(
                message="User with this email already exists",
                details={"email": data["email"]},
            )

        # Create new user
        user = User(
            email=data["email"].lower(),
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data.get("phone"),
            country=data.get("country"),
            experience_level=data.get("experience_level", "beginner"),
        )
        user.set_password(data["password"])

        # Save to database
        db.session.add(user)
        db.session.commit()

        # Log security event
        log_security_event(
            event_type="user_registration",
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            email=user.email,
        )

        # Create tokens
        tokens = create_tokens_for_user(user)

        logger.info(f"New user registered: {user.email}")

        return jsonify(
            {
                "message": "User registered successfully",
                "user": user.to_dict(),
                "tokens": tokens,
            }
        ), 201

    except ValidationError as e:
        logger.warning(f"Registration validation error: {e.messages}")
        raise CustomValidationError(
            message="Registration data is invalid",
            details={"validation_errors": e.messages},
        )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.session.rollback()
        raise


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    """
    Authenticate user and return JWT tokens.

    Rate limited to 10 attempts per minute to prevent brute force attacks.
    """
    try:
        # Validate input data
        schema = LoginSchema()
        data = schema.load(request.get_json())

        # Find user by email
        user = User.query.filter_by(email=data["email"].lower()).first()

        if not user or not user.check_password(data["password"]):
            # Log failed login attempt
            log_security_event(
                event_type="login_failed",
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                email=data["email"],
                reason="invalid_credentials",
            )

            raise AuthenticationError(
                message="Invalid email or password", details={"email": data["email"]}
            )

        # Check user status
        if user.status != UserStatus.ACTIVE:
            log_security_event(
                event_type="login_blocked",
                user_id=str(user.id),
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                reason=f"user_status_{user.status.value}",
            )

            raise AuthenticationError(
                message=f"Account is {user.status.value}. Please contact support.",
                details={"status": user.status.value},
            )

        # Update user login information
        user.last_login = datetime.utcnow()
        user.login_count += 1
        db.session.commit()

        # Create tokens
        tokens = create_tokens_for_user(user, data.get("remember_me", False))

        # Log successful login
        log_security_event(
            event_type="login_success",
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            email=user.email,
        )

        logger.info(f"User logged in: {user.email}")

        return jsonify(
            {"message": "Login successful", "user": user.to_dict(), "tokens": tokens}
        ), 200

    except ValidationError as e:
        logger.warning(f"Login validation error: {e.messages}")
        raise CustomValidationError(
            message="Login data is invalid", details={"validation_errors": e.messages}
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.status != UserStatus.ACTIVE:
            raise AuthenticationError(
                message="User not found or inactive",
                details={"user_id": current_user_id},
            )

        # Create new access token
        additional_claims = {
            "user_role": user.role.value,
            "user_status": user.status.value,
            "is_verified": user.is_verified,
        }

        access_token = create_access_token(
            identity=user.id, additional_claims=additional_claims
        )

        logger.info(f"Token refreshed for user: {user.email}")

        return jsonify(
            {
                "access_token": access_token,
                "expires_in": int(timedelta(hours=1).total_seconds()),
            }
        ), 200

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Logout user and invalidate tokens.
    """
    try:
        user_id = get_jwt_identity()
        jti = get_jwt()["jti"]

        # In a production system, you would add the JTI to a blacklist
        # For now, we'll just log the logout event

        log_security_event(
            event_type="logout",
            user_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            token_jti=jti,
        )

        logger.info(f"User logged out: {user_id}")

        return jsonify({"message": "Logout successful"}), 200

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """
    Get current user information.
    """
    try:
        user = current_user

        if not user:
            raise NotFoundError("User not found")

        return jsonify({"user": user.to_dict()}), 200

    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_profile():
    """
    Update current user profile.
    """
    try:
        user = current_user

        if not user:
            raise NotFoundError("User not found")

        # Validate input data
        schema = UpdateProfileSchema()
        data = schema.load(request.get_json())

        # Update user fields
        for field, value in data.items():
            if hasattr(user, field) and value is not None:
                setattr(user, field, value)

        db.session.commit()

        logger.info(f"User profile updated: {user.email}")

        return jsonify(
            {"message": "Profile updated successfully", "user": user.to_dict()}
        ), 200

    except ValidationError as e:
        logger.warning(f"Profile update validation error: {e.messages}")
        raise CustomValidationError(
            message="Profile update data is invalid",
            details={"validation_errors": e.messages},
        )

    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        db.session.rollback()
        raise


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
@limiter.limit("3 per hour")
def change_password():
    """
    Change user password.

    Rate limited to 3 attempts per hour for security.
    """
    try:
        user = current_user

        if not user:
            raise NotFoundError("User not found")

        # Validate input data
        schema = ChangePasswordSchema()
        data = schema.load(request.get_json())

        # Verify current password
        if not user.check_password(data["current_password"]):
            log_security_event(
                event_type="password_change_failed",
                user_id=str(user.id),
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                reason="invalid_current_password",
            )

            raise AuthenticationError(message="Current password is incorrect")

        # Check new password strength
        if not validate_password_strength(data["new_password"]):
            raise CustomValidationError(
                message="New password does not meet security requirements",
                details={
                    "requirements": [
                        "At least 8 characters",
                        "Contains uppercase and lowercase letters",
                        "Contains at least one number",
                        "Contains at least one special character",
                    ]
                },
            )

        # Update password
        user.set_password(data["new_password"])
        db.session.commit()

        # Log password change
        log_security_event(
            event_type="password_changed",
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

        logger.info(f"Password changed for user: {user.email}")

        return jsonify({"message": "Password changed successfully"}), 200

    except ValidationError as e:
        logger.warning(f"Password change validation error: {e.messages}")
        raise CustomValidationError(
            message="Password change data is invalid",
            details={"validation_errors": e.messages},
        )

    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        db.session.rollback()
        raise


@auth_bp.route("/verify-email", methods=["POST"])
@jwt_required()
def verify_email():
    """
    Send email verification.
    """
    try:
        user = current_user

        if not user:
            raise NotFoundError("User not found")

        if user.is_verified:
            return jsonify({"message": "Email is already verified"}), 200

        # In a production system, you would send an actual email
        # For now, we'll just mark as verified for demo purposes
        user.is_verified = True
        db.session.commit()

        log_security_event(
            event_type="email_verified",
            user_id=str(user.id),
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            email=user.email,
        )

        logger.info(f"Email verified for user: {user.email}")

        return jsonify({"message": "Email verified successfully"}), 200

    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        db.session.rollback()
        raise


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("3 per hour")
def forgot_password():
    """
    Request password reset.

    Rate limited to 3 attempts per hour to prevent abuse.
    """
    try:
        # Validate input data
        schema = PasswordResetRequestSchema()
        data = schema.load(request.get_json())

        user = User.query.filter_by(email=data["email"].lower()).first()

        # Always return success to prevent email enumeration
        # In production, send email only if user exists

        if user:
            log_security_event(
                event_type="password_reset_requested",
                user_id=str(user.id),
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                email=user.email,
            )

            logger.info(f"Password reset requested for user: {user.email}")

        return jsonify(
            {
                "message": "If your email exists in our system, you will receive password reset instructions"
            }
        ), 200

    except ValidationError as e:
        logger.warning(f"Password reset validation error: {e.messages}")
        raise CustomValidationError(
            message="Password reset request data is invalid",
            details={"validation_errors": e.messages},
        )

    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        raise


# Error handlers for the blueprint
@auth_bp.errorhandler(AuthenticationError)
def handle_auth_error(error):
    """Handle authentication errors."""
    return jsonify(
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        }
    ), error.status_code


@auth_bp.errorhandler(CustomValidationError)
def handle_validation_error(error):
    """Handle validation errors."""
    return jsonify(
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        }
    ), error.status_code


# Health check for auth service
@auth_bp.route("/health", methods=["GET"])
def auth_health():
    """Authentication service health check."""
    return jsonify(
        {
            "status": "healthy",
            "service": "authentication",
            "timestamp": datetime.utcnow().isoformat(),
        }
    ), 200
