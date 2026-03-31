"""
KYC Application - User Repository

Data access layer for User model operations including authentication
queries, role lookups, and account management.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update

from app.core.logging_config import get_logger
from app.models.user import User, UserRole, UserStatus
from app.repositories.base import BaseRepository

logger = get_logger(__name__)


class UserRepository(BaseRepository[User]):
    """
    Repository for User model database operations.

    Extends BaseRepository with user-specific queries for
    authentication, profile management, and admin operations.
    """

    def __init__(self, session):
        super().__init__(User, session)

    # =========================================================================
    # Authentication Queries
    # =========================================================================

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address (case-insensitive).

        Args:
            email: Email address to look up

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(
            func.lower(User.email) == func.lower(email)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username (case-insensitive).

        Args:
            username: Username to look up

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(
            func.lower(User.username) == func.lower(username)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email_or_username(self, identifier: str) -> Optional[User]:
        """
        Get a user by email OR username. Used for flexible login.

        Args:
            identifier: Email address or username

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(
            or_(
                func.lower(User.email) == func.lower(identifier),
                func.lower(User.username) == func.lower(identifier),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_by_email(self, email: str) -> Optional[User]:
        """
        Get an active (non-deleted, non-suspended) user by email.

        Args:
            email: Email address

        Returns:
            Active User if found, None otherwise
        """
        stmt = select(User).where(
            and_(
                func.lower(User.email) == func.lower(email),
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_verification_token(self, token: str) -> Optional[User]:
        """
        Get a user by email verification token.

        Args:
            token: Email verification token

        Returns:
            User if token matches, None otherwise
        """
        stmt = select(User).where(User.email_verification_token == token)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_password_reset_token(self, token: str) -> Optional[User]:
        """
        Get a user by password reset token (only if not expired).

        Args:
            token: Password reset token

        Returns:
            User if valid token found, None if expired or not found
        """
        now = datetime.now(timezone.utc)
        stmt = select(User).where(
            and_(
                User.password_reset_token == token,
                User.password_reset_expires > now,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # =========================================================================
    # Creation
    # =========================================================================

    async def create_user(
        self,
        email: str,
        username: str,
        hashed_password: str,
        first_name: str,
        last_name: str,
        role: UserRole = UserRole.CUSTOMER,
        **kwargs,
    ) -> User:
        """
        Create a new user account.

        Args:
            email: Email address (unique)
            username: Display username (unique)
            hashed_password: Pre-hashed bcrypt password
            first_name: First name
            last_name: Last name
            role: User role (default: CUSTOMER)
            **kwargs: Additional user fields

        Returns:
            Newly created User instance
        """
        data = {
            "email": email.lower(),
            "username": username.lower(),
            "hashed_password": hashed_password,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "status": UserStatus.PENDING_VERIFY,
            **kwargs,
        }
        user = await self.create(data)
        logger.info("User created", user_id=str(user.id), email=email, role=role)
        return user

    # =========================================================================
    # Authentication State Management
    # =========================================================================

    async def record_login_success(self, user_id: UUID, ip_address: str) -> None:
        """
        Update user record after successful login.

        Args:
            user_id: User ID
            ip_address: Client IP address
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                last_login_at=datetime.now(timezone.utc),
                last_login_ip=ip_address,
                failed_login_attempts=0,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def record_login_failure(self, user_id: UUID) -> int:
        """
        Increment failed login attempts counter.

        Args:
            user_id: User ID

        Returns:
            Updated failed_login_attempts count
        """
        user = await self.get_by_id(user_id)
        if user is None:
            return 0

        new_attempts = user.failed_login_attempts + 1
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(failed_login_attempts=new_attempts)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return new_attempts

    async def lock_account(self, user_id: UUID) -> bool:
        """
        Lock a user account due to too many failed login attempts.

        Args:
            user_id: User ID

        Returns:
            True if account was locked
        """
        result = await self.update(user_id, {"status": UserStatus.LOCKED})
        if result:
            logger.warning("User account locked", user_id=str(user_id))
        return result is not None

    async def verify_email(self, user_id: UUID) -> bool:
        """
        Mark a user's email as verified and activate the account.

        Args:
            user_id: User ID

        Returns:
            True if user was updated
        """
        result = await self.update(
            user_id,
            {
                "is_email_verified": True,
                "email_verification_token": None,
                "status": UserStatus.ACTIVE,
            },
        )
        return result is not None

    async def set_password_reset_token(
        self,
        user_id: UUID,
        token: str,
        expires_hours: int = 1,
    ) -> None:
        """
        Store a password reset token with expiry.

        Args:
            user_id: User ID
            token: Secure reset token
            expires_hours: Token validity in hours
        """
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        await self.update(
            user_id,
            {
                "password_reset_token": token,
                "password_reset_expires": expires_at,
            },
        )

    async def clear_password_reset_token(self, user_id: UUID) -> None:
        """Remove password reset token after use."""
        await self.update(
            user_id,
            {
                "password_reset_token": None,
                "password_reset_expires": None,
            },
        )

    async def update_password(self, user_id: UUID, hashed_password: str) -> bool:
        """
        Update a user's hashed password.

        Args:
            user_id: User ID
            hashed_password: New bcrypt hash

        Returns:
            True if password was updated
        """
        result = await self.update(
            user_id,
            {"hashed_password": hashed_password},
        )
        return result is not None

    # =========================================================================
    # Admin Queries
    # =========================================================================

    async def get_paginated(
        self,
        page: int = 1,
        size: int = 20,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        search: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """
        Get paginated list of users with optional filters.

        Args:
            page: Page number (1-indexed)
            size: Items per page
            role: Filter by role
            status: Filter by status
            search: Search by name or email (partial match)
            include_deleted: Include soft-deleted users

        Returns:
            Paginated result dictionary
        """
        stmt = select(User)

        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))

        if role:
            stmt = stmt.where(User.role == role)

        if status:
            stmt = stmt.where(User.status == status)

        if search:
            search_term = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.email).like(search_term),
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term),
                    func.lower(User.username).like(search_term),
                )
            )

        stmt = stmt.order_by(User.created_at.desc())
        return await self.paginate(stmt, page=page, size=size)

    async def count_by_role(self) -> Dict[str, int]:
        """Get user counts grouped by role."""
        stmt = select(User.role, func.count(User.id)).group_by(User.role)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_reviewers(self) -> List[User]:
        """Get all active reviewers and admins."""
        stmt = select(User).where(
            and_(
                User.role.in_([UserRole.REVIEWER, UserRole.ADMIN]),
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Existence Checks
    # =========================================================================

    async def email_exists(self, email: str, exclude_id: Optional[UUID] = None) -> bool:
        """
        Check if an email address is already in use.

        Args:
            email: Email to check
            exclude_id: Optionally exclude a specific user ID from the check

        Returns:
            True if email is taken
        """
        stmt = select(func.count(User.id)).where(
            func.lower(User.email) == func.lower(email)
        )
        if exclude_id:
            stmt = stmt.where(User.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def username_exists(
        self, username: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if a username is already taken.

        Args:
            username: Username to check
            exclude_id: Optionally exclude a specific user ID

        Returns:
            True if username is taken
        """
        stmt = select(func.count(User.id)).where(
            func.lower(User.username) == func.lower(username)
        )
        if exclude_id:
            stmt = stmt.where(User.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0
