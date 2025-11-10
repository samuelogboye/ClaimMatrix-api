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
from app.tasks.claim_tasks import process_claims_csv
from app.utils.logging_config import get_logger
from app.utils.rate_limit import limiter
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

    # Validate file type
    if not file.filename.endswith(".csv"):
        logger.warning(
            f"Invalid file type uploaded: {file.filename}",
            extra={"extra_fields": {"filename": file.filename, "user_id": current_user.id}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted",
        )

    # Save uploaded file to temporary location
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="wb", delete=False, suffix=".csv"
        ) as tmp_file:
            # Read and write file content
            content = await file.read()
            file_size = len(content)
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        logger.info(
            f"Claims file saved to temporary location: {tmp_file_path}",
            extra={"extra_fields": {
                "filename": file.filename,
                "file_size_bytes": file_size,
                "tmp_path": tmp_file_path,
                "user_id": current_user.id
            }}
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )


@router.get("/flagged", response_model=List[dict])
async def get_flagged_claims(
    min_suspicion_score: float = Query(
        default=0.7, ge=0.0, le=1.0, description="Minimum suspicion score threshold"
    ),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get flagged/suspicious claims based on audit results.

    Returns claims with suspicion scores above the specified threshold,
    along with their audit findings.

    Args:
        min_suspicion_score: Minimum suspicion score (0.0 to 1.0)
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of flagged claims with audit results
    """
    audit_service = AuditResultService(db)
    claim_service = ClaimService(db)

    # Get flagged audit results
    flagged_results = await audit_service.repository.get_flagged(
        min_suspicion_score=min_suspicion_score, skip=skip, limit=limit
    )

    # Build response with claim and audit information
    response = []
    for audit_result in flagged_results:
        # Get associated claim
        claim = await claim_service.repository.get_by_id(audit_result.claim_id)

        if claim:
            # Extract issues from JSONB field
            issues = audit_result.issues_found.get("issues", [])

            response.append(
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

    return response


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


@router.get("/", response_model=List[ClaimResponse])
async def get_all_claims(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims with pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of claims
    """
    claim_service = ClaimService(db)
    return await claim_service.get_all_claims(skip=skip, limit=limit)


@router.get("/member/{member_id}", response_model=List[ClaimResponse])
async def get_claims_by_member(
    member_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims for a specific member.

    Args:
        member_id: Member/patient identifier
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of claims for the member
    """
    claim_service = ClaimService(db)
    return await claim_service.get_claims_by_member(
        member_id=member_id, skip=skip, limit=limit
    )


@router.get("/provider/{provider_id}", response_model=List[ClaimResponse])
async def get_claims_by_provider(
    provider_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all claims for a specific provider.

    Args:
        provider_id: Healthcare provider identifier
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of claims for the provider
    """
    claim_service = ClaimService(db)
    return await claim_service.get_claims_by_provider(
        provider_id=provider_id, skip=skip, limit=limit
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
