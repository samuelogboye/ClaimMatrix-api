"""Application configuration management."""
import sys
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5433/claimmatrix"
    DATABASE_ECHO: bool = False

    # Redis settings
    REDIS_URL: str = "redis://localhost:6378/0"

    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6378/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6378/0"

    # Application settings
    APP_NAME: str = "ClaimMatrix"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development, staging, production

    # Logging settings
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_JSON_FORMAT: bool = False  # True for JSON logs (recommended for production)

    # CORS settings
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8001"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # JWT Authentication settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Validate JWT secret key is secure in production."""
        # Get environment from context
        environment = info.data.get("ENVIRONMENT", "development") if info.data else "development"

        if environment in ["production", "staging"]:
            if v == "your-secret-key-change-this-in-production" or len(v) < 32:
                print(
                    "\n" + "="*80 + "\n"
                    "CRITICAL SECURITY ERROR: Invalid JWT_SECRET_KEY configuration\n"
                    "="*80 + "\n"
                    "The JWT_SECRET_KEY must be a strong random key (minimum 32 characters).\n"
                    "Generate a secure key using: openssl rand -hex 32\n"
                    "Set it in your .env file or environment variables.\n"
                    "="*80 + "\n",
                    file=sys.stderr
                )
                sys.exit(1)
        elif v == "your-secret-key-change-this-in-production":
            # Warn in development but don't block
            print(
                "\n" + "="*80 + "\n"
                "WARNING: Using default JWT_SECRET_KEY in development mode\n"
                "="*80 + "\n"
                "For production, generate a secure key: openssl rand -hex 32\n"
                "="*80 + "\n",
                file=sys.stderr
            )

        return v

    def validate_config(self) -> None:
        """Validate critical configuration on startup."""
        errors = []

        # Validate DATABASE_URL is set
        if "user:password@localhost" in self.DATABASE_URL:
            errors.append(
                "DATABASE_URL appears to be using default credentials. "
                "Update with actual database connection string."
            )

        # Validate ENVIRONMENT
        if self.ENVIRONMENT not in ["development", "staging", "production"]:
            errors.append(
                f"ENVIRONMENT must be one of: development, staging, production. "
                f"Got: {self.ENVIRONMENT}"
            )

        # Print errors and exit if in production/staging
        if errors:
            print("\n" + "="*80, file=sys.stderr)
            print("CONFIGURATION VALIDATION ERRORS:", file=sys.stderr)
            print("="*80, file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            print("="*80 + "\n", file=sys.stderr)

            if self.ENVIRONMENT in ["production", "staging"]:
                sys.exit(1)


# Global settings instance
settings = Settings()

# Validate configuration on import
settings.validate_config()
