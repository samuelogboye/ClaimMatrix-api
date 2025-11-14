"""Audit Results API endpoints."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit_result_service import AuditResultService
from app.services.audit_engine_service import AuditEngineService
from app.services.claim_service import ClaimService
from app.schemas.pagination import PaginationParams, PaginatedResponse
from app.tasks.claim_tasks import run_ml_audit
from app.utils.logging_config import get_logger
from app.utils.rate_limit import limiter
from app.config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/audit-results", tags=["audit-results"])


@router.get("/claim/{claim_id}")
async def get_audit_results_for_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all audit results for a specific claim.

    Args:
        claim_id: Claim ID (not UUID, but the claim_id field)
        db: Database session
        current_user: Authenticated user

    Returns:
        List of audit results for the claim
    """
    claim_service = ClaimService(db)
    audit_service = AuditResultService(db)

    # Get claim by claim_id
    claim = await claim_service.get_claim_by_claim_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim not found: {claim_id}"
        )

    # Get audit results for this claim
    audit_results = await audit_service.repository.get_by_claim_id(claim.id)

    response = []
    for result in audit_results:
        issues = result.issues_found.get("issues", [])
        response.append({
            "id": str(result.id),
            "claim_id": claim.claim_id,
            "issues": issues,
            "issue_count": len(issues),
            "suspicion_score": float(result.suspicion_score),
            "recommended_action": result.recommended_action,
            "audit_timestamp": result.audit_timestamp.isoformat(),
        })

    return response


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
        current_user: Authenticated user

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

    logger.info(
        f"Retrieved {len(flagged_results)} flagged claims (page {page} of {(total_count + page_size - 1) // page_size})",
        extra={"extra_fields": {
            "min_suspicion_score": min_suspicion_score,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "user_id": current_user.id
        }}
    )

    # Build response with claim and audit information
    items = []
    for audit_result in flagged_results:
        # Get associated claim
        claim = await claim_service.repository.get_by_id(audit_result.claim_id)

        if claim:
            # Extract issues from JSONB field
            issues = audit_result.issues_found.get("issues", [])

            items.append({
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
            })

    return PaginatedResponse.create(
        items=items,
        total_items=total_count,
        page=page,
        page_size=page_size
    )


@router.post("/ml-audit/trigger")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def trigger_ml_audit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger ML anomaly detection on all claims.

    This runs the Isolation Forest ML model to detect anomalous claims
    that don't match normal patterns. The process runs asynchronously
    as a Celery background task.

    Args:
        request: FastAPI request
        db: Database session
        current_user: Authenticated user

    Returns:
        Task information
    """
    logger.info(
        f"ML audit triggered by user {current_user.email}",
        extra={"extra_fields": {"user_id": current_user.id}}
    )

    # Queue the ML audit task
    task = run_ml_audit.delay()

    return {
        "status": "accepted",
        "message": "ML anomaly detection task queued successfully",
        "task_id": task.id,
        "description": "The Isolation Forest model will analyze all claims for anomalies",
    }


@router.get("/stats")
async def get_audit_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get audit statistics and summary.

    Returns:
        Audit statistics including total audited, flagged, etc.
    """
    audit_service = AuditResultService(db)
    claim_service = ClaimService(db)

    # Get total claims and audited claims
    total_claims = await claim_service.repository.count()
    total_audited = await audit_service.repository.count()

    # Get flagged counts by severity
    high_risk = await audit_service.repository.count_by_score(min_score=0.8)
    medium_risk = await audit_service.repository.count_by_score(min_score=0.6, max_score=0.8)
    low_risk = await audit_service.repository.count_by_score(min_score=0.4, max_score=0.6)

    return {
        "total_claims": total_claims,
        "total_audited": total_audited,
        "audit_coverage": round((total_audited / total_claims * 100) if total_claims > 0 else 0, 2),
        "flagged_counts": {
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk,
            "total_flagged": high_risk + medium_risk + low_risk,
        },
    }
