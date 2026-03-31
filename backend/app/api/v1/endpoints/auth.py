"""
Authentication Endpoints

POST /auth/register       – Create a new user account
POST /auth/login          – Obtain JWT token pair
POST /auth/refresh        – Refresh access token
POST /auth/logout         – Revoke current access token
POST /auth/change-password – Change authenticated user's password
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.redis_client import get_redis, RedisClient
from app.core.security import decode_token, get_current_token_payload
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    PasswordChangeRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import (
    authenticate_user,
    change_password,
    create_tokens,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
http_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new customer account. "
        "Password must be at least 8 characters and include uppercase, lowercase, "
        "a digit, and a special character."
    ),
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Register a new user, issue tokens, and return combined auth response."""
    user = await register_user(db, user_data)
    tokens = create_tokens(user_id=str(user.id), role=user.role.value)
    # Build response BEFORE commit so user attributes are still loaded in session
    user_response = UserResponse.from_model(user)
    await db.commit()

    logger.info("User registered", user_id=str(user_response.id), email=user_response.email)

    return {
        "user": user_response,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=dict,
    summary="Authenticate and obtain JWT tokens",
    description=(
        "Submit email + password to receive an access token and a refresh token. "
        "Accounts are locked after 5 consecutive failed attempts."
    ),
)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Authenticate user and return combined auth response with tokens and user profile."""
    user = await authenticate_user(db, credentials.email, credentials.password)
    tokens = create_tokens(user_id=str(user.id), role=user.role.value)
    # Build response BEFORE commit so user attributes are still loaded in session
    user_response = UserResponse.from_model(user)
    await db.commit()

    logger.info(
        "User login",
        user_id=str(user_response.id),
        client_ip=request.client.host if request.client else "unknown",
    )

    return {
        "user": user_response,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=dict,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access token.",
)
async def refresh(
    body: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Issue a new access token using the provided refresh token."""
    result = await refresh_access_token(db, body.refresh_token)
    return {
        **result,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke current access token",
    description=(
        "Add the current access token to the revocation blocklist. "
        "The token will be invalid for future requests."
    ),
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    payload: dict[str, Any] = Depends(get_current_token_payload),
    redis: RedisClient = Depends(get_redis),
) -> LogoutResponse:
    """Revoke the current JWT access token."""
    jti = payload.get("jti", "")
    exp = payload.get("exp")

    if jti and exp:
        import time  # noqa: PLC0415

        ttl = max(0, int(exp - time.time()))
        await redis.add_to_blocklist(jti, ttl)
        logger.info("Token revoked", jti=jti, user_id=payload.get("sub"))

    return LogoutResponse(message="Successfully logged out.")


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change authenticated user's password",
    description=(
        "Change the current user's password. Requires the existing password "
        "and a new password meeting strength requirements."
    ),
)
async def change_user_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Change the password for the currently authenticated user."""
    await change_password(
        db=db,
        user_id=current_user.id,
        old_password=body.current_password,
        new_password=body.new_password,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Current user profile
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Return the profile of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse.from_model(current_user)
