"""
Alembic Environment Configuration

Supports both:
  1. Async online migration (normal alembic upgrade/downgrade commands)
  2. Synchronous offline migration (alembic upgrade --sql for dry-run scripts)

The async engine is built from the app's DATABASE_URL setting so that
connection parameters are consistent across the application and migrations.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object (provides access to alembic.ini values)
# ---------------------------------------------------------------------------

config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import app models so Alembic autogenerate can detect table changes
# ---------------------------------------------------------------------------

# Ensure the app package is importable when running alembic from the
# backend/ directory.
import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base  # noqa: E402 – must be after sys.path patch
# Import all models so their tables are registered in Base.metadata
from app.models.audit_log import AuditLog  # noqa: F401, E402
from app.models.document import Document  # noqa: F401, E402
from app.models.kyc import KYCSubmission  # noqa: F401, E402
from app.models.user import User  # noqa: F401, E402

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Database URL resolution
# ---------------------------------------------------------------------------


def get_database_url() -> str:
    """
    Resolve the database URL from:
    1. ALEMBIC_DB_URL environment variable (highest priority)
    2. DATABASE_URL environment variable
    3. alembic.ini sqlalchemy.url value
    """
    return (
        os.environ.get("ALEMBIC_DB_URL")
        or os.environ.get("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url", "")
    )


# ---------------------------------------------------------------------------
# Offline migration (generates SQL script without a live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    No DBAPI connection is made – a literal SQL script is emitted instead.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration (async)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Execute the migration with an active synchronous-compatible connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async SQLAlchemy engine.

    asyncpg does not support the sync connection interface Alembic expects,
    so we use ``run_sync()`` to bridge into sync territory.
    """
    url = get_database_url()

    # Build async engine configuration
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    async_engine = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling for migrations
    )

    async with async_engine.connect() as conn:
        await conn.run_sync(do_run_migrations)

    await async_engine.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Detects whether there is a running event loop and either re-uses it
    (for invocation from within an async context) or creates a new one.
    """
    try:
        loop = asyncio.get_running_loop()
        # Already inside a running loop (e.g. called from a FastAPI lifespan)
        loop.run_until_complete(run_async_migrations())
    except RuntimeError:
        # No running loop – create a fresh one
        asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
