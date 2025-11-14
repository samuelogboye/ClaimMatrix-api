"""Audit Result repository for database operations."""
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_result import AuditResult
from app.schemas.audit_result import AuditResultResponse


class AuditResultRepository:
    """Repository for AuditResult model database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def create(
        self,
        claim_id: UUID,
        issues_found: Dict[str, Any],
        suspicion_score: Decimal,
        recommended_action: str,
    ) -> AuditResult:
        """
        Create a new audit result.

        Args:
            claim_id: UUID of the claim being audited
            issues_found: JSON object containing audit issues
            suspicion_score: Suspicion score between 0 and 1
            recommended_action: Recommended action for the audit finding

        Returns:
            Created AuditResult object
        """
        audit_result = AuditResult(
            claim_id=claim_id,
            issues_found=issues_found,
            suspicion_score=suspicion_score,
            recommended_action=recommended_action,
        )

        self.db.add(audit_result)
        await self.db.flush()
        await self.db.refresh(audit_result)
        return audit_result

    async def get_by_id(self, audit_result_id: UUID) -> Optional[AuditResult]:
        """
        Get audit result by ID.

        Args:
            audit_result_id: AuditResult UUID

        Returns:
            AuditResult object or None if not found
        """
        result = await self.db.execute(
            select(AuditResult).where(AuditResult.id == audit_result_id)
        )
        return result.scalar_one_or_none()

    async def get_by_claim_id(self, claim_id: UUID) -> List[AuditResult]:
        """
        Get all audit results for a specific claim.

        Args:
            claim_id: Claim UUID

        Returns:
            List of AuditResult objects
        """
        result = await self.db.execute(
            select(AuditResult)
            .where(AuditResult.claim_id == claim_id)
            .order_by(AuditResult.audit_timestamp.desc())
        )
        return list(result.scalars().all())

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[AuditResult]:
        """
        Get all audit results with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of AuditResult objects
        """
        result = await self.db.execute(
            select(AuditResult)
            .order_by(AuditResult.audit_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_flagged(
        self, min_suspicion_score: float = 0.7, skip: int = 0, limit: int = 100
    ) -> List[AuditResult]:
        """
        Get flagged audit results with suspicion score above threshold.

        Args:
            min_suspicion_score: Minimum suspicion score threshold (default: 0.7)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of AuditResult objects with high suspicion scores
        """
        result = await self.db.execute(
            select(AuditResult)
            .options(selectinload(AuditResult.claim))
            .where(AuditResult.suspicion_score >= min_suspicion_score)
            .order_by(AuditResult.suspicion_score.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self,
        audit_result_id: UUID,
        issues_found: Optional[Dict[str, Any]] = None,
        suspicion_score: Optional[Decimal] = None,
        recommended_action: Optional[str] = None,
    ) -> Optional[AuditResult]:
        """
        Update an audit result.

        Args:
            audit_result_id: AuditResult UUID
            issues_found: New issues found (optional)
            suspicion_score: New suspicion score (optional)
            recommended_action: New recommended action (optional)

        Returns:
            Updated AuditResult object or None if not found
        """
        audit_result = await self.get_by_id(audit_result_id)
        if not audit_result:
            return None

        if issues_found is not None:
            audit_result.issues_found = issues_found
        if suspicion_score is not None:
            audit_result.suspicion_score = suspicion_score
        if recommended_action is not None:
            audit_result.recommended_action = recommended_action

        await self.db.flush()
        await self.db.refresh(audit_result)
        return audit_result

    async def delete(self, audit_result_id: UUID) -> bool:
        """
        Delete an audit result.

        Args:
            audit_result_id: AuditResult UUID

        Returns:
            True if deleted, False if not found
        """
        audit_result = await self.get_by_id(audit_result_id)
        if not audit_result:
            return False

        await self.db.delete(audit_result)
        await self.db.flush()
        return True

    async def count(self) -> int:
        """
        Get total count of audit results.

        Returns:
            Total number of audit results
        """
        result = await self.db.execute(
            select(func.count(AuditResult.id))
        )
        return result.scalar() or 0

    async def count_by_score(
        self,
        min_score: float = 0.0,
        max_score: float = 1.0
    ) -> int:
        """
        Count audit results within a score range.

        Args:
            min_score: Minimum suspicion score
            max_score: Maximum suspicion score

        Returns:
            Count of audit results in the score range
        """
        result = await self.db.execute(
            select(func.count(AuditResult.id))
            .where(
                AuditResult.suspicion_score >= min_score,
                AuditResult.suspicion_score < max_score
            )
        )
        return result.scalar() or 0

    async def count_flagged(self, min_suspicion_score: float = 0.7) -> int:
        """
        Count flagged audit results with suspicion score above threshold.

        Args:
            min_suspicion_score: Minimum suspicion score threshold

        Returns:
            Count of flagged audit results
        """
        result = await self.db.execute(
            select(func.count(AuditResult.id))
            .where(AuditResult.suspicion_score >= min_suspicion_score)
        )
        return result.scalar() or 0

    async def to_response(self, audit_result: AuditResult) -> AuditResultResponse:
        """
        Convert AuditResult model to AuditResultResponse schema.

        Args:
            audit_result: AuditResult model

        Returns:
            AuditResultResponse schema
        """
        return AuditResultResponse(
            id=audit_result.id,
            claim_id=audit_result.claim_id,
            issues_found=audit_result.issues_found,
            suspicion_score=audit_result.suspicion_score,
            recommended_action=audit_result.recommended_action,
            audit_timestamp=audit_result.audit_timestamp,
        )
