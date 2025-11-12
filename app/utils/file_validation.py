"""File validation utilities for secure file uploads."""
import os
import csv
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile

from app.config import settings
from app.exceptions import FileProcessingException
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension against allowed extensions.

    Args:
        filename: Name of the file to validate

    Returns:
        True if extension is allowed, False otherwise
    """
    allowed_extensions = [
        ext.strip() for ext in settings.ALLOWED_UPLOAD_EXTENSIONS.split(",")
    ]

    file_ext = Path(filename).suffix.lower()
    return file_ext in allowed_extensions


def validate_file_size(file_size: int) -> bool:
    """
    Validate file size against maximum allowed size.

    Args:
        file_size: Size of file in bytes

    Returns:
        True if size is within limit, False otherwise
    """
    max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    return file_size <= max_size_bytes


async def validate_csv_content(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate CSV file content structure.

    Checks:
    - File can be parsed as CSV
    - File has required columns
    - File is not empty

    Args:
        file_path: Path to the CSV file

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_columns = [
        "claim_id",
        "member_id",
        "provider_id",
        "date_of_service",
        "cpt_code",
        "charge_amount",
    ]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Try to detect CSV dialect
            sample = f.read(1024)
            f.seek(0)

            try:
                csv.Sniffer().sniff(sample)
            except csv.Error:
                return False, "File does not appear to be a valid CSV"

            # Read CSV headers
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            if not headers:
                return False, "CSV file has no headers"

            # Check for required columns
            missing_columns = [col for col in required_columns if col not in headers]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"

            # Check if file has data rows
            try:
                first_row = next(reader, None)
                if first_row is None:
                    return False, "CSV file contains no data rows"
            except Exception as e:
                return False, f"Error reading CSV data: {str(e)}"

        return True, None

    except UnicodeDecodeError:
        return False, "File encoding is not UTF-8"
    except Exception as e:
        logger.error(f"CSV validation error: {str(e)}", exc_info=True)
        return False, f"CSV validation failed: {str(e)}"


async def save_upload_file_safely(
    upload_file: UploadFile,
    validate_content: bool = True
) -> str:
    """
    Safely save an uploaded file with validation.

    Args:
        upload_file: FastAPI UploadFile object
        validate_content: Whether to validate file content

    Returns:
        Path to saved temporary file

    Raises:
        FileProcessingException: If validation fails
    """
    filename = upload_file.filename or "unknown"

    # Validate extension
    if not validate_file_extension(filename):
        raise FileProcessingException(
            message=f"File type not allowed. Allowed types: {settings.ALLOWED_UPLOAD_EXTENSIONS}",
            filename=filename,
            file_type=Path(filename).suffix,
        )

    # Read file content
    content = await upload_file.read()
    file_size = len(content)

    logger.info(
        f"Processing file upload: {filename}",
        extra={"extra_fields": {"filename": filename, "size_bytes": file_size}}
    )

    # Validate size
    if not validate_file_size(file_size):
        raise FileProcessingException(
            message=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
            filename=filename,
            details={"size_mb": file_size / (1024 * 1024), "max_size_mb": settings.MAX_UPLOAD_SIZE_MB}
        )

    # Save to temporary file in shared directory
    try:
        # Create shared temp directory if it doesn't exist
        shared_temp_dir = Path(settings.SHARED_TEMP_DIR)
        shared_temp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            suffix=Path(filename).suffix,
            prefix="upload_",
            dir=str(shared_temp_dir)  # Use shared directory
        ) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        logger.info(
            f"File saved to temporary location: {tmp_file_path}",
            extra={"extra_fields": {"filename": filename, "tmp_path": tmp_file_path}}
        )

        # Validate CSV content if requested
        if validate_content and filename.endswith('.csv'):
            is_valid, error_message = await validate_csv_content(tmp_file_path)
            if not is_valid:
                # Clean up invalid file
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass

                raise FileProcessingException(
                    message=error_message or "CSV validation failed",
                    filename=filename,
                    file_type="CSV"
                )

        return tmp_file_path

    except FileProcessingException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to save uploaded file: {str(e)}",
            exc_info=True,
            extra={"extra_fields": {"filename": filename}}
        )
        raise FileProcessingException(
            message=f"Failed to process uploaded file: {str(e)}",
            filename=filename
        )


def cleanup_temp_file(file_path: str) -> bool:
    """
    Safely delete a temporary file.

    Args:
        file_path: Path to file to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.warning(
            f"Failed to cleanup temporary file: {file_path} - {str(e)}",
            extra={"extra_fields": {"file_path": file_path}}
        )
        return False
