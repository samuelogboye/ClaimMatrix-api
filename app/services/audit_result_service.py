"""Audit Result service layer for business logic."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.repositories.audit_result_repository import AuditResultRepository
from app.repositories.claim_repository import ClaimRepository
from app.schemas.audit_result import (
    AuditResultCreate,
    AuditResultResponse,
    AuditResultUpdate,
)
from app.models.audit_result import AuditResult


class AuditResultService:
    """Service layer for audit result business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.repository = AuditResultRepository(db)
        self.claim_repository = ClaimRepository(db)

    async def create_audit_result(
        self, audit_data: AuditResultCreate
    ) -> AuditResultResponse:
        """
        Create a new audit result.

        Args:
            audit_data: Audit result creation data

        Returns:
            Created audit result response

        Raises:
            HTTPException: If claim does not exist
        """
        # Verify that the claim exists
        claim = await self.claim_repository.get_by_id(audit_data.claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim with id '{audit_data.claim_id}' not found",
            )

        audit_result = await self.repository.create(
            claim_id=audit_data.claim_id,
            issues_found=audit_data.issues_found,
            suspicion_score=audit_data.suspicion_score,
            recommended_action=audit_data.recommended_action,
        )

        await self.db.commit()
        return await self.repository.to_response(audit_result)

    async def get_audit_result_by_id(
        self, audit_result_id: UUID
    ) -> Optional[AuditResultResponse]:
        """
        Get audit result by ID.

        Args:
            audit_result_id: AuditResult UUID

        Returns:
            Audit result response or None if not found
        """
        audit_result = await self.repository.get_by_id(audit_result_id)
        if not audit_result:
            return None

        return await self.repository.to_response(audit_result)

    async def get_audit_results_by_claim(
        self, claim_id: UUID
    ) -> List[AuditResultResponse]:
        """
        Get all audit results for a specific claim.

        Args:
            claim_id: Claim UUID

        Returns:
            List of audit result responses
        """
        audit_results = await self.repository.get_by_claim_id(claim_id)
        return [
            await self.repository.to_response(audit_result)
            for audit_result in audit_results
        ]

    async def get_all_audit_results(
        self, skip: int = 0, limit: int = 100
    ) -> List[AuditResultResponse]:
        """
        Get all audit results with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit result responses
        """
        audit_results = await self.repository.get_all(skip=skip, limit=limit)
        return [
            await self.repository.to_response(audit_result)
            for audit_result in audit_results
        ]

    async def get_flagged_audit_results(
        self, min_suspicion_score: float = 0.7, skip: int = 0, limit: int = 100
    ) -> List[AuditResultResponse]:
        """
        Get flagged audit results with suspicion score above threshold.

        Args:
            min_suspicion_score: Minimum suspicion score threshold (default: 0.7)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit result responses with high suspicion scores
        """
        audit_results = await self.repository.get_flagged(
            min_suspicion_score=min_suspicion_score, skip=skip, limit=limit
        )
        return [
            await self.repository.to_response(audit_result)
            for audit_result in audit_results
        ]

    async def update_audit_result(
        self, audit_result_id: UUID, audit_data: AuditResultUpdate
    ) -> Optional[AuditResultResponse]:
        """
        Update an audit result.

        Args:
            audit_result_id: AuditResult UUID
            audit_data: Audit result update data

        Returns:
            Updated audit result response or None if not found
        """
        audit_result = await self.repository.update(
            audit_result_id=audit_result_id,
            issues_found=audit_data.issues_found,
            suspicion_score=audit_data.suspicion_score,
            recommended_action=audit_data.recommended_action,
        )

        if not audit_result:
            return None

        await self.db.commit()
        return await self.repository.to_response(audit_result)

    async def delete_audit_result(self, audit_result_id: UUID) -> bool:
        """
        Delete an audit result.

        Args:
            audit_result_id: AuditResult UUID

        Returns:
            True if deleted, False if not found
        """
        deleted = await self.repository.delete(audit_result_id)
        if deleted:
            await self.db.commit()
        return deleted
