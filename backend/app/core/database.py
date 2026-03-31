"""
KYC Application - Database Module

Configures the async SQLAlchemy 2.0 engine, session factory,
and provides dependency injection helpers for FastAPI.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Declarative Base
# =============================================================================

class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base class for all models.

    All ORM models should inherit from this class.
    Provides common configuration and type annotation support.
    """

    # Enable native enum handling
    type_annotation_map: dict[Any, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """Provide a useful string representation."""
        pk_cols = [col.name for col in self.__table__.primary_key.columns]
        pk_vals = {col: getattr(self, col, None) for col in pk_cols}
        return f"<{self.__class__.__name__} {pk_vals}>"


# =============================================================================
# Engine Configuration
# =============================================================================

def _build_engine_kwargs() -> dict[str, Any]:
    """Build SQLAlchemy engine keyword arguments from settings."""
    kwargs: dict[str, Any] = {
        "echo": settings.DEBUG,
        "echo_pool": settings.DEBUG,
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
    }

    # Use NullPool for testing (prevents connection pooling issues)
    if settings.ENVIRONMENT == "testing":
        kwargs["poolclass"] = NullPool
    else:
        kwargs["poolclass"] = AsyncAdaptedQueuePool
        kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT

    # Connection arguments for asyncpg
    kwargs["connect_args"] = {
        "statement_cache_size": 0,  # Disable statement caching for pgbouncer compatibility
        "prepared_statement_cache_size": 0,
        "server_settings": {
            "application_name": settings.APP_NAME,
            "jit": "off",  # Disable JIT for consistent query plans
        },
    }

    return kwargs


# Create the async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **_build_engine_kwargs(),
)


# =============================================================================
# Session Factory
# =============================================================================

# Create the async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Don't expire objects after commit (important for async)
)


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.

    Handles session lifecycle including rollback on exceptions
    and proper cleanup.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a session within an explicit transaction.

    Use this when you need explicit transaction control (e.g., complex
    multi-step operations that must succeed or fail atomically).
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


# =============================================================================
# Database Utilities
# =============================================================================

async def init_db() -> None:
    """
    Initialize the database by creating all tables.

    Should be called during application startup.
    In production, prefer using Alembic migrations instead.
    """
    logger.info("Initializing database tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully")


async def drop_all_tables() -> None:
    """
    Drop all database tables.

    WARNING: This will destroy all data. Use only in testing.
    """
    if settings.ENVIRONMENT not in ("testing", "development"):
        raise RuntimeError("drop_all_tables() can only be called in testing/development")

    logger.warning("Dropping all database tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")


async def check_db_connection() -> bool:
    """
    Check if the database connection is healthy.

    Returns True if connected, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection check failed", error=str(e))
        return False


class DatabaseManager:
    """
    Context manager for managing database sessions in non-FastAPI contexts
    (e.g., background tasks, scripts, CLI commands).

    Usage:
        async with DatabaseManager() as db:
            result = await db.execute(select(User))
    """

    def __init__(self):
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self._session = AsyncSessionLocal()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is not None:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
            await self._session.close()
            self._session = None
