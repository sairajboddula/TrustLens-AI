"""
KYC Application - Configuration Module

Centralizes all application settings using Pydantic BaseSettings.
Settings are loaded from environment variables and .env files.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Uses pydantic-settings for type validation and .env file support.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    APP_NAME: str = Field(default="KYC Verification System", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    ENVIRONMENT: str = Field(default="development", description="Deployment environment")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    SECRET_KEY: str = Field(
        default="change-this-super-secret-key-in-production-min-32-chars",
        description="Application secret key (min 32 chars)",
        min_length=32,
    )
    ALLOWED_HOSTS: str = Field(
        default="localhost,127.0.0.1",
        description="Comma-separated list of allowed hosts",
    )
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        description="Comma-separated list of allowed CORS origins",
    )

    # -------------------------------------------------------------------------
    # Server Settings
    # -------------------------------------------------------------------------
    HOST: str = Field(default="0.0.0.0", description="Server bind host")
    PORT: int = Field(default=8000, description="Server bind port", ge=1, le=65535)
    WORKERS: int = Field(default=4, description="Number of worker processes", ge=1)
    RELOAD: bool = Field(default=False, description="Enable auto-reload (development only)")

    # -------------------------------------------------------------------------
    # Database Settings
    # -------------------------------------------------------------------------
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port", ge=1, le=65535)
    POSTGRES_DB: str = Field(default="kyc_db", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="kyc_user", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="kyc_password", description="PostgreSQL password")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://kyc_user:kyc_password@localhost:5432/kyc_db",
        description="Full async database connection URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=10, description="Connection pool size", ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, description="Max pool overflow", ge=0)
    DATABASE_POOL_TIMEOUT: int = Field(default=30, description="Pool timeout in seconds", ge=1)
    DATABASE_POOL_RECYCLE: int = Field(default=3600, description="Connection recycle time", ge=60)

    # -------------------------------------------------------------------------
    # Redis Settings
    # -------------------------------------------------------------------------
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port", ge=1, le=65535)
    REDIS_DB: int = Field(default=0, description="Redis database number", ge=0)
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Full Redis connection URL",
    )
    REDIS_MAX_CONNECTIONS: int = Field(default=10, description="Max Redis connections", ge=1)
    CACHE_TTL: int = Field(default=3600, description="Default cache TTL in seconds", ge=0)

    # -------------------------------------------------------------------------
    # JWT Authentication
    # -------------------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(
        default="change-this-jwt-secret-key-in-production-min-32-chars",
        description="JWT signing secret key (min 32 chars)",
        min_length=32,
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="Access token expiry in minutes", ge=1
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh token expiry in days", ge=1
    )

    # -------------------------------------------------------------------------
    # File Storage
    # -------------------------------------------------------------------------
    UPLOAD_DIR: str = Field(default="./uploads", description="Document upload directory")
    MAX_FILE_SIZE_MB: int = Field(default=10, description="Max file size in MB", ge=1)
    ALLOWED_FILE_TYPES: str = Field(
        default="image/jpeg,image/png,image/jpg,application/pdf",
        description="Comma-separated allowed MIME types",
    )

    # -------------------------------------------------------------------------
    # AI / LLM Settings
    # -------------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4-vision-preview", description="OpenAI model name")
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="Google API key")
    GOOGLE_MODEL: str = Field(default="gemini-pro-vision", description="Google model name")
    LLM_PROVIDER: str = Field(
        default="openai",
        description="LLM provider to use: 'openai' or 'google'",
    )
    LLM_TEMPERATURE: float = Field(
        default=0.1, description="LLM temperature (0.0-1.0)", ge=0.0, le=1.0
    )
    LLM_MAX_TOKENS: int = Field(default=2048, description="Max LLM response tokens", ge=1)

    # -------------------------------------------------------------------------
    # OCR Settings
    # -------------------------------------------------------------------------
    OCR_LANGUAGE: str = Field(default="en", description="OCR language code")
    OCR_GPU: bool = Field(default=False, description="Use GPU for OCR processing")

    # -------------------------------------------------------------------------
    # Celery Settings
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1", description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2", description="Celery result backend URL"
    )
    CELERY_TASK_TIMEOUT: int = Field(
        default=300, description="Celery task timeout in seconds", ge=10
    )

    # -------------------------------------------------------------------------
    # Email Settings
    # -------------------------------------------------------------------------
    SMTP_HOST: str = Field(default="smtp.gmail.com", description="SMTP server host")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USER: Optional[str] = Field(default=None, description="SMTP username")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP password")
    SMTP_TLS: bool = Field(default=True, description="Use TLS for SMTP")
    EMAIL_FROM: str = Field(
        default="noreply@kyc-system.com", description="Sender email address"
    )
    EMAIL_FROM_NAME: str = Field(
        default="KYC Verification System", description="Sender display name"
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: 'json' or 'text'")
    LOG_FILE: str = Field(default="./logs/kyc_app.log", description="Log file path")
    LOG_ROTATION: str = Field(default="10 MB", description="Log rotation size")
    LOG_RETENTION: str = Field(default="30 days", description="Log retention period")

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(
        default=100, description="Max requests per window", ge=1
    )
    RATE_LIMIT_WINDOW: int = Field(
        default=60, description="Rate limit window in seconds", ge=1
    )

    # -------------------------------------------------------------------------
    # KYC Business Rules
    # -------------------------------------------------------------------------
    KYC_AUTO_APPROVE_THRESHOLD: float = Field(
        default=0.95,
        description="Confidence score for auto-approval",
        ge=0.0,
        le=1.0,
    )
    KYC_AUTO_REJECT_THRESHOLD: float = Field(
        default=0.30,
        description="Confidence score for auto-rejection",
        ge=0.0,
        le=1.0,
    )
    KYC_REVIEW_REQUIRED_THRESHOLD: float = Field(
        default=0.70,
        description="Confidence score threshold requiring manual review",
        ge=0.0,
        le=1.0,
    )
    KYC_MAX_SUBMISSION_ATTEMPTS: int = Field(
        default=3, description="Max KYC submission attempts per user", ge=1
    )
    KYC_DOCUMENT_EXPIRY_DAYS: int = Field(
        default=365, description="Document validity period in days", ge=1
    )

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse allowed hosts string into a list."""
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def allowed_file_types_list(self) -> List[str]:
        """Parse allowed file types string into a list."""
        return [ft.strip() for ft in self.ALLOWED_FILE_TYPES.split(",") if ft.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate that LLM provider is supported."""
        allowed = {"openai", "google"}
        if v.lower() not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of: {allowed}")
        return v.lower()

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}")
        return v.upper()

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm."""
        allowed = {"HS256", "HS384", "HS512", "RS256"}
        if v.upper() not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of: {allowed}")
        return v.upper()

    @model_validator(mode="after")
    def validate_thresholds(self) -> "Settings":
        """Validate KYC threshold ordering."""
        if self.KYC_AUTO_REJECT_THRESHOLD >= self.KYC_REVIEW_REQUIRED_THRESHOLD:
            raise ValueError(
                "KYC_AUTO_REJECT_THRESHOLD must be less than KYC_REVIEW_REQUIRED_THRESHOLD"
            )
        if self.KYC_REVIEW_REQUIRED_THRESHOLD >= self.KYC_AUTO_APPROVE_THRESHOLD:
            raise ValueError(
                "KYC_REVIEW_REQUIRED_THRESHOLD must be less than KYC_AUTO_APPROVE_THRESHOLD"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses lru_cache to ensure settings are loaded only once
    and reused across the application lifecycle.
    """
    return Settings()


# Global settings instance
settings = get_settings()
