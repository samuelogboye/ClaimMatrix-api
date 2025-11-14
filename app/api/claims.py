"""Claims API endpoints."""
import os
import tempfile
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.claim_service import ClaimService
from app.services.audit_result_service import AuditResultService
from app.schemas.claim import ClaimCreate, ClaimResponse
from app.schemas.pagination import PaginationParams, PaginatedResponse
from app.tasks.claim_tasks import process_claims_csv
from app.utils.logging_config import get_logger
from app.utils.rate_limit import limiter
from app.utils.file_validation import save_upload_file_safely
from app.config import settings

router = APIRouter(prefix="/claims", tags=["claims"])
logger = get_logger(__name__)


@router.post("/upload")
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_claims(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload CSV file of claims for processing.

    The CSV file should have the following columns:
    - claim_id: Unique claim identifier
    - member_id: Member/patient identifier
    - provider_id: Healthcare provider identifier
    - date_of_service: Date when service was provided (YYYY-MM-DD)
    - cpt_code: CPT procedure code
    - charge_amount: Charge amount for the service

    The claims will be processed asynchronously by a Celery task.

    Args:
        file: CSV file containing claims data
        db: Database session

    Returns:
        Upload status and task information
    """
    logger.info(
        f"Claims file upload initiated by user {current_user.email}",
        extra={"extra_fields": {"filename": file.filename, "user_id": current_user.id}}
    )

    # Validate and save file with comprehensive checks
    try:
        tmp_file_path = await save_upload_file_safely(
            upload_file=file,
            validate_content=True  # Validates CSV structure
        )

        # Queue the processing task
        task = process_claims_csv.delay(tmp_file_path)

        logger.info(
            f"Claims processing task queued: {task.id}",
            extra={"extra_fields": {
                "task_id": task.id,
                "filename": file.filename,
                "user_id": current_user.id
            }}
        )

        return {
            "status": "accepted",
            "message": "File uploaded successfully and queued for processing",
            "task_id": task.id,
            "filename": file.filename,
        }

    except Exception as e:
        logger.error(
            f"Failed to upload claims file: {str(e)}",
            exc_info=True,
            extra={"extra_fields": {"filename": file.filename, "user_id": current_user.id}}
        )
        raise


@router.get("/flagged")
async def get_flagged_claims(
    min_suspicion_score: float = Query(
        default=0.7, ge=0.0, le=1.0, description="Minimum suspicion score threshold"
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get flagged/suspicious claims based on audit results.

    Returns claims with suspicion scores above the specified threshold,
    along with their audit findings.

    Args:
        min_suspicion_score: Minimum suspicion score (0.0 to 1.0)
        page: Page number (1-indexed)
        page_size: Number of items per page (default: 20, max: 100)
        db: Database session

    Returns:
        Paginated list of flagged claims with audit results
    """
    audit_service = AuditResultService(db)
    claim_service = ClaimService(db)

    # Calculate pagination
    pagination = PaginationParams(page=page, page_size=page_size)

    # Get total count
    total_count = await audit_service.repository.count_flagged(min_suspicion_score)

    # Get flagged audit results
    flagged_results = await audit_service.repository.get_flagged(
        min_suspicion_score=min_suspicion_score, skip=pagination.skip, limit=pagination.limit
    )

    # Build response with claim and audit information
    items = []
    for audit_result in flagged_results:
        # Get associated claim
        claim = await claim_service.repository.get_by_id(audit_result.claim_id)

        if claim:
            # Extract issues from JSONB field
            issues = audit_result.issues_found.get("issues", [])

            items.append(
                {
                    "claim_id": claim.claim_id,
                    "member_id": claim.member_id,
                    "provider_id": claim.provider_id,
                    "date_of_service": claim.date_of_service.isoformat(),
                    "cpt_code": claim.cpt_code,
                    "charge_amount": float(claim.charge_amount),
                    "issues": issues,
                    "suspicion_score": float(audit_result.suspicion_score),
                    "recommended_action": audit_result.recommended_action,
                    "audit_timestamp": audit_result.audit_timestamp.isoformat(),
                }
            )

    return PaginatedResponse.create(
        items=items,
        total_items=total_count,
        page=page,
        page_size=page_size
    )


@router.post("/", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    claim_data: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a single claim manually.

    Args:
        claim_data: Claim creation data
        db: Database session

    Returns:
        Created claim
    """
    claim_service = ClaimService(db)
    return await claim_service.create_claim(claim_data)


@router.get("/")
async def get_all_claims(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (default: 20, max: 100)
        db: Database session

    Returns:
        Paginated list of claims
    """
    claim_service = ClaimService(db)

    # Calculate pagination
    pagination = PaginationParams(page=page, page_size=page_size)

    # Get total count
    total_count = await claim_service.repository.count()

    # Get claims
    claims = await claim_service.get_all_claims(skip=pagination.skip, limit=pagination.limit)

    return PaginatedResponse.create(
        items=claims,
        total_items=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/member/{member_id}")
async def get_claims_by_member(
    member_id: str,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims for a specific member.

    Args:
        member_id: Member/patient identifier
        page: Page number (1-indexed)
        page_size: Number of items per page (default: 20, max: 100)
        db: Database session

    Returns:
        Paginated list of claims for the member
    """
    claim_service = ClaimService(db)

    # Calculate pagination
    pagination = PaginationParams(page=page, page_size=page_size)

    # Get total count
    total_count = await claim_service.repository.count_by_member_id(member_id)

    # Get claims
    claims = await claim_service.get_claims_by_member(
        member_id=member_id, skip=pagination.skip, limit=pagination.limit
    )

    return PaginatedResponse.create(
        items=claims,
        total_items=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/provider/{provider_id}")
async def get_claims_by_provider(
    provider_id: str,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims for a specific provider.

    Args:
        provider_id: Healthcare provider identifier
        page: Page number (1-indexed)
        page_size: Number of items per page (default: 20, max: 100)
        db: Database session

    Returns:
        Paginated list of claims for the provider
    """
    claim_service = ClaimService(db)

    # Calculate pagination
    pagination = PaginationParams(page=page, page_size=page_size)

    # Get total count
    total_count = await claim_service.repository.count_by_provider_id(provider_id)

    # Get claims
    claims = await claim_service.get_claims_by_provider(
        provider_id=provider_id, skip=pagination.skip, limit=pagination.limit
    )

    return PaginatedResponse.create(
        items=claims,
        total_items=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim_by_claim_id(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific claim by claim_id.

    Args:
        claim_id: Unique claim identifier
        db: Database session

    Returns:
        Claim details

    Raises:
        HTTPException: If claim not found
    """
    claim_service = ClaimService(db)
    claim = await claim_service.get_claim_by_claim_id(claim_id)

    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with claim_id '{claim_id}' not found",
        )

    return claim
