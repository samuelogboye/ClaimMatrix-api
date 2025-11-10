"""Application configuration management."""
from typing import List
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

    # CORS settings
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8001"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # JWT Authentication settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


# Global settings instance
settings = Settings()
