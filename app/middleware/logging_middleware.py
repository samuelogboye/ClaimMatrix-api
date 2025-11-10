"""Middleware for logging HTTP requests and responses."""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logging_config import get_logger, request_id_context, log_with_context

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses.

    Logs include:
    - Request method, path, query parameters
    - Response status code
    - Request duration
    - Unique request ID for tracing
    - Client IP address
    - User agent
    """

    def __init__(self, app: ASGIApp):
        """
        Initialize the middleware.

        Args:
            app: ASGI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response from the application
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request_id_context.set(request_id)

        # Attach request ID to request state for use in route handlers
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Extract request details
        method = request.method
        url = str(request.url)
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Log incoming request
        log_with_context(
            logger,
            20,  # INFO level
            f"Incoming request: {method} {path}",
            request_id=request_id,
            method=method,
            path=path,
            query_params=query_params,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Process request and handle exceptions
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {method} {path} - {str(e)}",
                exc_info=True,
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "duration_ms": round(duration * 1000, 2),
                        "client_ip": client_ip,
                    }
                }
            )
            raise

        # Calculate request duration
        duration = time.time() - start_time
        status_code = response.status_code

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Determine log level based on status code
        if status_code >= 500:
            log_level = 40  # ERROR
        elif status_code >= 400:
            log_level = 30  # WARNING
        else:
            log_level = 20  # INFO

        # Log response
        log_with_context(
            logger,
            log_level,
            f"Request completed: {method} {path} - {status_code}",
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration * 1000, 2),
            client_ip=client_ip,
        )

        return response
