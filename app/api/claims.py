"""Claims API endpoints."""
import os
import tempfile
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.claim_service import ClaimService
from app.services.audit_result_service import AuditResultService
from app.schemas.claim import ClaimCreate, ClaimResponse
from app.tasks.claim_tasks import process_claims_csv

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/upload")
async def upload_claims(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
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
    # Validate file type
    if not file.filename.endswith(".csv"):
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
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Queue the processing task
        task = process_claims_csv.delay(tmp_file_path)

        return {
            "status": "accepted",
            "message": "File uploaded successfully and queued for processing",
            "task_id": task.id,
            "filename": file.filename,
        }

    except Exception as e:
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
