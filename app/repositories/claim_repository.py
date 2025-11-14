"""Claim repository for database operations."""
from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.schemas.claim import ClaimResponse


class ClaimRepository:
    """Repository for Claim model database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def create(
        self,
        claim_id: str,
        member_id: str,
        provider_id: str,
        date_of_service: date,
        cpt_code: str,
        charge_amount: Decimal,
    ) -> Claim:
        """
        Create a new claim.

        Args:
            claim_id: Unique claim identifier
            member_id: Member/patient identifier
            provider_id: Healthcare provider identifier
            date_of_service: Date when service was provided
            cpt_code: CPT procedure code
            charge_amount: Charge amount for the service

        Returns:
            Created Claim object
        """
        claim = Claim(
            claim_id=claim_id,
            member_id=member_id,
            provider_id=provider_id,
            date_of_service=date_of_service,
            cpt_code=cpt_code,
            charge_amount=charge_amount,
        )

        self.db.add(claim)
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_by_id(self, claim_uuid: UUID) -> Optional[Claim]:
        """
        Get claim by UUID.

        Args:
            claim_uuid: Claim UUID

        Returns:
            Claim object or None if not found
        """
        result = await self.db.execute(select(Claim).where(Claim.id == claim_uuid))
        return result.scalar_one_or_none()

    async def get_by_claim_id(self, claim_id: str) -> Optional[Claim]:
        """
        Get claim by claim_id string.

        Args:
            claim_id: Unique claim identifier string

        Returns:
            Claim object or None if not found
        """
        result = await self.db.execute(select(Claim).where(Claim.claim_id == claim_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Claim]:
        """
        Get all claims with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Claim objects
        """
        result = await self.db.execute(
            select(Claim).order_by(Claim.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_member_id(
        self, member_id: str, skip: int = 0, limit: int = 100
    ) -> List[Claim]:
        """
        Get claims by member ID.

        Args:
            member_id: Member/patient identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Claim objects
        """
        result = await self.db.execute(
            select(Claim)
            .where(Claim.member_id == member_id)
            .order_by(Claim.date_of_service.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_provider_id(
        self, provider_id: str, skip: int = 0, limit: int = 100
    ) -> List[Claim]:
        """
        Get claims by provider ID.

        Args:
            provider_id: Healthcare provider identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Claim objects
        """
        result = await self.db.execute(
            select(Claim)
            .where(Claim.provider_id == provider_id)
            .order_by(Claim.date_of_service.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self,
        claim_uuid: UUID,
        member_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        date_of_service: Optional[date] = None,
        cpt_code: Optional[str] = None,
        charge_amount: Optional[Decimal] = None,
    ) -> Optional[Claim]:
        """
        Update a claim.

        Args:
            claim_uuid: Claim UUID
            member_id: New member ID (optional)
            provider_id: New provider ID (optional)
            date_of_service: New date of service (optional)
            cpt_code: New CPT code (optional)
            charge_amount: New charge amount (optional)

        Returns:
            Updated Claim object or None if not found
        """
        claim = await self.get_by_id(claim_uuid)
        if not claim:
            return None

        if member_id is not None:
            claim.member_id = member_id
        if provider_id is not None:
            claim.provider_id = provider_id
        if date_of_service is not None:
            claim.date_of_service = date_of_service
        if cpt_code is not None:
            claim.cpt_code = cpt_code
        if charge_amount is not None:
            claim.charge_amount = charge_amount

        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def delete(self, claim_uuid: UUID) -> bool:
        """
        Delete a claim.

        Args:
            claim_uuid: Claim UUID

        Returns:
            True if deleted, False if not found
        """
        claim = await self.get_by_id(claim_uuid)
        if not claim:
            return False

        await self.db.delete(claim)
        await self.db.flush()
        return True

    async def count(self) -> int:
        """
        Get total count of claims.

        Returns:
            Total number of claims
        """
        result = await self.db.execute(select(func.count(Claim.id)))
        return result.scalar() or 0

    async def to_response(self, claim: Claim) -> ClaimResponse:
        """
        Convert Claim model to ClaimResponse schema.

        Args:
            claim: Claim model

        Returns:
            ClaimResponse schema
        """
        return ClaimResponse(
            id=claim.id,
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            provider_id=claim.provider_id,
            date_of_service=claim.date_of_service,
            cpt_code=claim.cpt_code,
            charge_amount=claim.charge_amount,
            created_at=claim.created_at,
        )
