"""
FastAPI Dependencies

Reusable dependency functions for request authentication, authorization,
and database session injection.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.security import get_current_token_payload
from app.models.user import User, UserRole, UserStatus

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Current User
# ---------------------------------------------------------------------------


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    payload: dict[str, Any] = Depends(get_current_token_payload),
) -> User:
    """
    Dependency: resolve the current authenticated user from the JWT payload.

    Validates:
      - Subject (user ID) present in token
      - User exists in the database

    Raises:
        HTTPException 401: Token missing user ID.
        HTTPException 404: User no longer exists.
    """
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the subject (user ID) claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: ensure the current user's account is active.

    Raises:
        HTTPException 403: Account is not in ACTIVE status.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {current_user.status.value}. Access denied.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Dependency: restrict endpoint access to ADMIN users only.

    Raises:
        HTTPException 403: If the user does not have the ADMIN role.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user


async def require_reviewer(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Dependency: restrict endpoint access to ADMIN or REVIEWER users.

    Raises:
        HTTPException 403: If the user does not have the ADMIN or REVIEWER role.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.REVIEWER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer or administrator access required.",
        )
    return current_user


async def require_analyst(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Dependency: restrict endpoint access to ADMIN, REVIEWER, or ANALYST users.

    Raises:
        HTTPException 403: If the user is a plain CUSTOMER.
    """
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or administrator access required.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Re-export DB dependency for convenience
# ---------------------------------------------------------------------------

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "require_admin",
    "require_reviewer",
    "require_analyst",
]
