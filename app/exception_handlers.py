"""Global exception handlers for the application."""
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

from app.exceptions import ClaimMatrixException
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def claimmatrix_exception_handler(
    request: Request, exc: ClaimMatrixException
) -> JSONResponse:
    """
    Handle custom ClaimMatrix exceptions.

    Args:
        request: FastAPI request object
        exc: ClaimMatrix exception

    Returns:
        JSON response with error details
    """
    # Log the exception
    logger.warning(
        f"ClaimMatrix exception: {exc.message}",
        extra={
            "extra_fields": {
                "exception_type": exc.__class__.__name__,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )

    # Return structured error response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle standard HTTP exceptions.

    Args:
        request: FastAPI request object
        exc: HTTP exception

    Returns:
        JSON response with error details
    """
    # Log based on status code
    if exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={
                "extra_fields": {
                    "status_code": exc.status_code,
                    "path": request.url.path,
                    "method": request.method,
                }
            },
        )
    elif exc.status_code >= 400:
        logger.warning(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={
                "extra_fields": {
                    "status_code": exc.status_code,
                    "path": request.url.path,
                    "method": request.method,
                }
            },
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "HTTPException",
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handle request validation errors from Pydantic.

    Args:
        request: FastAPI request object
        exc: Validation error

    Returns:
        JSON response with validation error details
    """
    errors = []

    if isinstance(exc, RequestValidationError):
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
    else:
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })

    logger.warning(
        f"Validation error: {len(errors)} field(s) failed validation",
        extra={
            "extra_fields": {
                "validation_errors": errors,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "ValidationError",
                "message": "Request validation failed",
                "details": {
                    "validation_errors": errors,
                },
            }
        },
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.

    Args:
        request: FastAPI request object
        exc: SQLAlchemy exception

    Returns:
        JSON response with error details
    """
    # Log full exception with stack trace
    logger.error(
        f"Database error: {str(exc)}",
        exc_info=True,
        extra={
            "extra_fields": {
                "exception_type": exc.__class__.__name__,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )

    # Check if it's an integrity error (constraint violation)
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "type": "DatabaseIntegrityError",
                    "message": "Database constraint violation. Resource may already exist.",
                    "details": {},
                }
            },
        )

    # Generic database error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "DatabaseError",
                "message": "A database error occurred. Please try again later.",
                "details": {},
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle any unhandled exceptions.

    This is the fallback handler for unexpected errors.

    Args:
        request: FastAPI request object
        exc: Any exception

    Returns:
        JSON response with generic error message
    """
    # Log full exception with stack trace
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={
            "extra_fields": {
                "exception_type": exc.__class__.__name__,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )

    # Return generic error response (don't expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
                "details": {},
            }
        },
    )
