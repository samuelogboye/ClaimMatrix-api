"""Rate limiting utilities for the application."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """
    Get the key for rate limiting.

    Uses client IP address as the key. Can be enhanced to use
    authenticated user ID for authenticated endpoints.

    Args:
        request: FastAPI request object

    Returns:
        Rate limit key (client IP)
    """
    # Try to get authenticated user ID if available
    if hasattr(request.state, "user") and request.state.user:
        user_id = getattr(request.state.user, "id", None)
        if user_id:
            return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT] if settings.RATE_LIMIT_ENABLED else [],
    storage_uri=settings.RATE_LIMIT_STORAGE_URL,
    strategy="fixed-window",  # or "moving-window" for more accurate limiting
    enabled=settings.RATE_LIMIT_ENABLED,
)


def get_limiter() -> Limiter:
    """
    Get the rate limiter instance.

    Returns:
        Configured Limiter instance
    """
    return limiter
