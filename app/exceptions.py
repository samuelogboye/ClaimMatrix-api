"""Custom exception classes for the application."""
from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class ClaimMatrixException(Exception):
    """Base exception class for ClaimMatrix application."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception.

        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DuplicateResourceException(ClaimMatrixException):
    """Exception raised when trying to create a duplicate resource."""

    def __init__(self, resource_type: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize duplicate resource exception.

        Args:
            resource_type: Type of resource (e.g., "Claim", "User")
            identifier: Unique identifier that already exists
            details: Additional error details
        """
        message = f"{resource_type} with identifier '{identifier}' already exists"
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details or {"resource_type": resource_type, "identifier": identifier},
        )


class ResourceNotFoundException(ClaimMatrixException):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_type: str, identifier: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize resource not found exception.

        Args:
            resource_type: Type of resource (e.g., "Claim", "User")
            identifier: Identifier that was not found
            details: Additional error details
        """
        message = f"{resource_type} with identifier '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details or {"resource_type": resource_type, "identifier": identifier},
        )


class ValidationException(ClaimMatrixException):
    """Exception raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize validation exception.

        Args:
            message: Validation error message
            field: Field that failed validation
            details: Additional error details
        """
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


class AuthenticationException(ClaimMatrixException):
    """Exception raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        """
        Initialize authentication exception.

        Args:
            message: Authentication error message
            details: Additional error details
        """
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationException(ClaimMatrixException):
    """Exception raised when user is not authorized to perform an action."""

    def __init__(self, message: str = "Not authorized to perform this action", details: Optional[Dict[str, Any]] = None):
        """
        Initialize authorization exception.

        Args:
            message: Authorization error message
            details: Additional error details
        """
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class DatabaseException(ClaimMatrixException):
    """Exception raised when a database operation fails."""

    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize database exception.

        Args:
            message: Database error message
            operation: Database operation that failed (e.g., "create", "update", "delete")
            details: Additional error details
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details,
        )


class FileProcessingException(ClaimMatrixException):
    """Exception raised when file processing fails."""

    def __init__(
        self,
        message: str,
        filename: Optional[str] = None,
        file_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize file processing exception.

        Args:
            message: File processing error message
            filename: Name of file that failed processing
            file_type: Type of file (e.g., "CSV", "JSON")
            details: Additional error details
        """
        error_details = details or {}
        if filename:
            error_details["filename"] = filename
        if file_type:
            error_details["file_type"] = file_type

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


class ExternalServiceException(ClaimMatrixException):
    """Exception raised when an external service call fails."""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize external service exception.

        Args:
            message: External service error message
            service_name: Name of external service
            details: Additional error details
        """
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name

        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=error_details,
        )


class RateLimitException(ClaimMatrixException):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize rate limit exception.

        Args:
            message: Rate limit error message
            retry_after: Seconds until rate limit resets
            details: Additional error details
        """
        error_details = details or {}
        if retry_after:
            error_details["retry_after"] = retry_after

        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=error_details,
        )
