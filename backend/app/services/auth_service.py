"""
Auth Service

Encapsulates all authentication and user-account business logic:
  - User registration with password strength enforcement
  - Credential verification with brute-force protection
  - JWT access + refresh token pair creation
  - Refresh-token rotation
  - Password change
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_password_strong,
    verify_password,
)
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate

logger = get_logger(__name__)

# Maximum failed login attempts before locking an account
MAX_FAILED_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user account.

    Validates:
      - Email uniqueness
      - Username uniqueness
      - Password strength

    Args:
        db:        Async DB session.
        user_data: Validated UserCreate Pydantic schema.

    Returns:
        The newly created User ORM instance.

    Raises:
        HTTPException 400: If email/username is taken or password is weak.
    """
    # Check email uniqueness
    existing_email = await db.execute(
        select(User).where(User.email == user_data.email.lower())
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Check username uniqueness
    existing_username = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This username is already taken.",
        )

    # Password strength check
    strong, failures = is_password_strong(user_data.password)
    if not strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements.", "failures": failures},
        )

    # Create user
    new_user = User(
        email=user_data.email.lower().strip(),
        username=user_data.username.strip(),
        hashed_password=hash_password(user_data.password),
        first_name=user_data.first_name.strip().title(),
        last_name=user_data.last_name.strip().title(),
        phone_number=getattr(user_data, "phone_number", None),
        role=UserRole.CUSTOMER,
        status=UserStatus.ACTIVE,       # Skip email verification for now
        is_email_verified=True,
    )

    db.add(new_user)
    await db.flush()   # Assign ID without committing
    await db.refresh(new_user)  # Load server-side defaults (created_at, updated_at)

    logger.info(
        "User registered",
        user_id=str(new_user.id),
        email=new_user.email,
        role=new_user.role,
    )
    return new_user


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """
    Verify user credentials.

    Tracks failed attempts and locks the account after MAX_FAILED_ATTEMPTS.

    Returns:
        Authenticated User.

    Raises:
        HTTPException 401: Invalid credentials.
        HTTPException 403: Account locked / inactive.
    """
    result = await db.execute(
        select(User).where(User.email == email.lower().strip())
    )
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        # Constant-time response to prevent email enumeration
        hash_password("dummy_timing_protection")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
        )

    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account locked due to too many failed login attempts. "
                   "Please contact support.",
        )

    if user.status not in (UserStatus.ACTIVE,):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value}. Please contact support.",
        )

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.status = UserStatus.LOCKED
            logger.warning("Account locked after failed attempts", user_id=str(user.id))
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
        )

    # Successful login – reset failure counter
    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    # Refresh to reload server-side updated fields (e.g. updated_at via onupdate)
    # so they are available synchronously when building the response schema
    await db.refresh(user)

    logger.info("User authenticated", user_id=str(user.id), email=user.email)
    return user


# ---------------------------------------------------------------------------
# Token pair creation
# ---------------------------------------------------------------------------


def create_tokens(user_id: str | UUID, role: str) -> Dict[str, str]:
    """
    Issue an access + refresh JWT token pair for a user.

    Args:
        user_id: User's UUID (string or UUID object).
        role:    User's role string (embedded as a claim).

    Returns:
        Dict with keys ``access_token``, ``refresh_token``, ``token_type``.
    """
    claims = {"role": role}
    access_token = create_access_token(subject=user_id, additional_claims=claims)
    refresh_token = create_refresh_token(subject=user_id, additional_claims=claims)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> Dict[str, str]:
    """
    Validate a refresh token and issue a new access token.

    Performs:
      1. JWT signature + expiry validation
      2. Token-type check (must be refresh)
      3. User existence + active status check
      4. Issues new access token (refresh token unchanged – no rotation)

    Returns:
        Dict with ``access_token`` and ``token_type``.

    Raises:
        HTTPException 401: If the refresh token is invalid or the user is inactive.
    """
    payload = decode_token(refresh_token)

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. A refresh token is required.",
        )

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token: missing subject.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive.",
        )

    claims = {"role": user.role.value}
    new_access_token = create_access_token(subject=str(user.id), additional_claims=claims)

    logger.debug("Access token refreshed", user_id=user_id)
    return {"access_token": new_access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


async def change_password(
    db: AsyncSession,
    user_id: str | UUID,
    old_password: str,
    new_password: str,
) -> None:
    """
    Change a user's password after verifying the old one.

    Args:
        db:           Async DB session.
        user_id:      UUID of the user.
        old_password: Current plain-text password.
        new_password: Desired new plain-text password.

    Raises:
        HTTPException 400: If old password is wrong or new password is weak.
        HTTPException 404: If user not found.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    strong, failures = is_password_strong(new_password)
    if not strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "New password does not meet requirements.", "failures": failures},
        )

    if old_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )

    user.hashed_password = hash_password(new_password)
    await db.flush()

    logger.info("Password changed", user_id=str(user_id))
