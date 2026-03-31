"""
KYC Application - Logging Configuration Module

Configures structured JSON logging using loguru with support for
file rotation, log levels, and context-enriched log entries.
"""

import logging
import sys
from pathlib import Path
from typing import Any

from loguru import logger


# =============================================================================
# Loguru Configuration
# =============================================================================

def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = "./logs/kyc_app.log",
    log_rotation: str = "10 MB",
    log_retention: str = "30 days",
) -> None:
    """
    Configure the application logging system using loguru.

    Args:
        log_level: Minimum log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_format: Output format - 'json' for structured or 'text' for human-readable
        log_file: Path to the log file
        log_rotation: File rotation trigger (e.g., "10 MB", "1 day")
        log_retention: How long to retain old log files (e.g., "30 days")
    """
    # Remove default loguru handler
    logger.remove()

    # -------------------------------------------------------------------------
    # Console Handler
    # -------------------------------------------------------------------------
    if log_format.lower() == "json":
        console_format = (
            '{{"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"logger": "{name}", '
            '"message": "{message}", '
            '"file": "{file}:{line}"}}'
        )
    else:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    logger.add(
        sys.stdout,
        level=log_level.upper(),
        format=console_format,
        colorize=(log_format.lower() != "json"),
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe async logging
    )

    # -------------------------------------------------------------------------
    # File Handler
    # -------------------------------------------------------------------------
    log_file_path = Path(log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    if log_format.lower() == "json":
        file_format = (
            '{{"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"logger": "{name}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"message": "{message}"}}'
        )
    else:
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

    logger.add(
        str(log_file_path),
        level=log_level.upper(),
        format=file_format,
        rotation=log_rotation,
        retention=log_retention,
        compression="gz",
        enqueue=True,
        backtrace=True,
        diagnose=False,  # Disable in production files to avoid leaking data
    )

    # -------------------------------------------------------------------------
    # Error File Handler (separate file for errors only)
    # -------------------------------------------------------------------------
    error_log_path = log_file_path.parent / "kyc_errors.log"
    logger.add(
        str(error_log_path),
        level="ERROR",
        format=file_format,
        rotation=log_rotation,
        retention=log_retention,
        compression="gz",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    logger.info(
        "Logging configured",
        level=log_level,
        format=log_format,
        log_file=str(log_file_path),
    )


# =============================================================================
# Standard Library Logging Intercept
# =============================================================================

class InterceptHandler(logging.Handler):
    """
    Intercept standard library logging and redirect to loguru.

    This ensures that third-party libraries using the standard
    logging module also output through loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get the corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find the correct caller frame
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_stdlib_logging_intercept() -> None:
    """
    Set up interception of standard library logging.

    Redirects uvicorn, SQLAlchemy, and other library logs through loguru.
    """
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Configure specific loggers
    for logger_name in [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "asyncio",
        "celery",
        "redis",
    ]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        logging.getLogger(logger_name).propagate = False


# =============================================================================
# Logger Factory
# =============================================================================

def get_logger(name: str) -> Any:
    """
    Get a logger instance bound to the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Loguru logger bound with the module name

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened", key="value")
    """
    return logger.bind(name=name)


# =============================================================================
# Application Logging Initialization
# =============================================================================

def init_logging() -> None:
    """
    Initialize the complete logging system.

    Should be called once at application startup, before any
    other modules create loggers.
    """
    from app.core.config import settings

    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_file=settings.LOG_FILE,
        log_rotation=settings.LOG_ROTATION,
        log_retention=settings.LOG_RETENTION,
    )

    setup_stdlib_logging_intercept()


# Initialize logging when this module is first imported
try:
    from app.core.config import settings
    init_logging()
except Exception:
    # Fallback: configure basic logging if settings aren't available
    configure_logging()
