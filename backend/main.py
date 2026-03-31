"""
KYC Verification System - FastAPI Application Entry Point

This module initializes the FastAPI application with all middleware,
routers, startup/shutdown events, and exception handlers.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)


# =============================================================================
# Application Lifespan (Startup / Shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # -------------------------------------------------------------------------
    # Startup
    # -------------------------------------------------------------------------
    logger.info("Starting KYC Verification System", version=settings.APP_VERSION)

    # Verify database connectivity (schema is managed exclusively by Alembic)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.warning("Database not yet ready — will retry on first request", error=str(e))

    # Initialize Redis connection
    try:
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.warning("Redis connection failed - caching disabled", error=str(e))

    logger.info(
        "Application startup complete",
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )

    yield

    # -------------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------------
    logger.info("Shutting down KYC Verification System")

    # Close Redis connection
    try:
        await redis_client.close()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.warning("Error closing Redis connection", error=str(e))

    # Dispose database engine
    try:
        await engine.dispose()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.warning("Error disposing database engine", error=str(e))

    logger.info("Application shutdown complete")


# =============================================================================
# Create FastAPI Application
# =============================================================================

def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## KYC Verification System API

A production-grade Know Your Customer (KYC) verification platform with:
- **AI-powered document verification** using LangGraph agents
- **Multi-document support**: Passport, National ID, Driver's License
- **Real-time status updates** via WebSocket
- **Role-based access control**: Admin, Reviewer, Customer
- **Complete audit trail** for compliance
        """,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # -------------------------------------------------------------------------
    # Register Middleware
    # -------------------------------------------------------------------------
    _register_middleware(app)

    # -------------------------------------------------------------------------
    # Register Exception Handlers
    # -------------------------------------------------------------------------
    _register_exception_handlers(app)

    # -------------------------------------------------------------------------
    # Register Routers
    # -------------------------------------------------------------------------
    _register_routers(app)

    return app


# =============================================================================
# Middleware Configuration
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add a unique request ID to every request."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        logger.info(
            "Request processed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=round(process_time * 1000, 2),
            client_ip=request.client.host if request.client else "unknown",
        )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response


def _register_middleware(app: FastAPI) -> None:
    """Register all middleware with the application."""

    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request ID tracking
    app.add_middleware(RequestIDMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # Trusted hosts (production only)
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts_list,
        )


# =============================================================================
# Exception Handlers
# =============================================================================

def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(
            "HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "Validation error",
            errors=exc.errors(),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": 422,
                    "message": "Validation error",
                    "details": exc.errors(),
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )


# =============================================================================
# Router Registration
# =============================================================================

def _register_routers(app: FastAPI) -> None:
    """Register all API routers."""

    # Import routers here to avoid circular imports
    from app.api.v1 import api_router

    # Mount v1 API router
    app.include_router(api_router, prefix="/api/v1")

    # Health check endpoint (no prefix)
    @app.get("/health", tags=["Health"], summary="Health Check")
    async def health_check() -> dict[str, Any]:
        """
        Application health check endpoint.

        Returns the current status of the application and its dependencies.
        """
        health_status: dict[str, Any] = {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

        # Check database
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            health_status["database"] = "healthy"
        except Exception as e:
            health_status["database"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.error("Database health check failed", error=str(e))

        # Check Redis
        try:
            await redis_client.ping()
            health_status["redis"] = "healthy"
        except Exception as e:
            health_status["redis"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.warning("Redis health check failed", error=str(e))

        return health_status

    @app.get("/", tags=["Root"], summary="API Root")
    async def root() -> dict[str, str]:
        """API root endpoint."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }


# =============================================================================
# Application Instance
# =============================================================================

app = create_application()


# =============================================================================
# Development Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )
