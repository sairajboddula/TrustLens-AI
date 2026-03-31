"""
KYC Application - Security Module

Implements JWT token creation/validation, password hashing/verification,
and authentication dependency injection for FastAPI.

Python 3.13 compatibility notes:
- Uses PyJWT instead of python-jose (python-jose is unmaintained and
  incompatible with Python 3.13 due to removed stdlib modules).
- Uses bcrypt directly instead of passlib (passlib is unmaintained since
  2023 and broken with bcrypt>=4.x on Python 3.12+).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import bcrypt
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.redis_client import RedisClient, get_redis

logger = get_logger(__name__)


# =============================================================================
# Password Hashing  (bcrypt 4.x direct API)
# =============================================================================

_BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The plain-text password to hash.

    Returns:
        Bcrypt hash string (UTF-8 decoded).
    """
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain_password:  The plain-text candidate password.
        hashed_password: The stored bcrypt hash.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        # Malformed hash or encoding error — treat as mismatch
        return False


def is_password_strong(password: str) -> tuple[bool, list[str]]:
    """
    Check whether a password meets the application strength requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Returns:
        Tuple of (is_strong: bool, list of unmet requirement messages).
    """
    failures: list[str] = []

    if len(password) < 8:
        failures.append("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        failures.append("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        failures.append("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        failures.append("Password must contain at least one digit")

    special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
    if not any(c in special_chars for c in password):
        failures.append("Password must contain at least one special character")

    return len(failures) == 0, failures


# =============================================================================
# JWT Token Management  (PyJWT 2.x)
# =============================================================================

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def create_access_token(
    subject: str | UUID,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:           Token subject — typically the user's UUID.
        additional_claims: Optional extra claims merged into the payload.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": ACCESS_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(16),
    }

    if additional_claims:
        payload.update(additional_claims)

    token: str = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    logger.debug(
        "Access token created",
        subject=str(subject),
        expires_at=expire.isoformat(),
    )

    return token


def create_refresh_token(
    subject: str | UUID,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT refresh token with longer expiry.

    Args:
        subject:           Token subject — typically the user's UUID.
        additional_claims: Optional extra claims merged into the payload.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": REFRESH_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(16),
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Dictionary of decoded token claims.

    Raises:
        HTTPException 401: Token expired, invalid signature, or malformed.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as exc:
        logger.warning("Invalid token", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_token_subject(token: str) -> str:
    """
    Extract the subject claim from a token without validating expiry.

    Useful for identifying tokens that need to be revoked even after they
    have expired.

    Returns:
        Subject string, or empty string if extraction fails.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        return payload.get("sub", "")
    except InvalidTokenError:
        return ""


# =============================================================================
# Security Schemes
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="OAuth2PasswordBearer",
)

http_bearer = HTTPBearer(auto_error=True)


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    FastAPI dependency — validates the Bearer token and returns its payload.

    Checks performed:
    1. JWT signature and structure
    2. Token expiry
    3. Token type must be ``access``
    4. Token JTI not present in Redis revocation blocklist

    Raises:
        HTTPException 401: Token is invalid, expired, wrong type, or revoked.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti", "")
    if jti and await redis.is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(get_current_token_payload),
) -> str:
    """
    FastAPI dependency — returns the authenticated user's ID string.

    Raises:
        HTTPException 401: Subject claim is missing from the token.
    """
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def require_roles(*required_roles: str):
    """
    FastAPI dependency factory for role-based access control (RBAC).

    Args:
        *required_roles: Role names permitted to call the decorated endpoint.

    Returns:
        A FastAPI dependency that validates the caller's role.

    Example::

        @router.get("/admin", dependencies=[Depends(require_roles("admin"))])
        async def admin_only():
            ...
    """
    async def role_checker(
        payload: dict[str, Any] = Depends(get_current_token_payload),
    ) -> dict[str, Any]:
        user_role = payload.get("role", "")
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(required_roles)}",
            )
        return payload

    return role_checker


# =============================================================================
# Token Generation Utilities
# =============================================================================


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random URL-safe token."""
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    """Generate a numeric one-time password of the given length."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))
