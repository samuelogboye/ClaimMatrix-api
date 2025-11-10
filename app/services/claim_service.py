"""Claim service layer for business logic."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.repositories.claim_repository import ClaimRepository
from app.schemas.claim import ClaimCreate, ClaimResponse, ClaimUpdate
from app.models.claim import Claim
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class ClaimService:
    """Service layer for claim business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.repository = ClaimRepository(db)

    async def create_claim(self, claim_data: ClaimCreate) -> ClaimResponse:
        """
        Create a new claim.

        Args:
            claim_data: Claim creation data

        Returns:
            Created claim response

        Raises:
            HTTPException: If claim_id already exists
        """
        logger.info(
            f"Creating claim: {claim_data.claim_id}",
            extra={"extra_fields": {
                "claim_id": claim_data.claim_id,
                "member_id": claim_data.member_id,
                "provider_id": claim_data.provider_id
            }}
        )

        # Check if claim_id already exists
        existing_claim = await self.repository.get_by_claim_id(claim_data.claim_id)
        if existing_claim:
            logger.warning(
                f"Duplicate claim_id detected: {claim_data.claim_id}",
                extra={"extra_fields": {"claim_id": claim_data.claim_id}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Claim with claim_id '{claim_data.claim_id}' already exists",
            )

        try:
            claim = await self.repository.create(
                claim_id=claim_data.claim_id,
                member_id=claim_data.member_id,
                provider_id=claim_data.provider_id,
                date_of_service=claim_data.date_of_service,
                cpt_code=claim_data.cpt_code,
                charge_amount=claim_data.charge_amount,
            )

            await self.db.commit()

            logger.info(
                f"Claim created successfully: {claim_data.claim_id}",
                extra={"extra_fields": {"claim_id": claim_data.claim_id, "db_id": claim.id}}
            )
        except Exception as e:
            logger.error(
                f"Failed to create claim: {claim_data.claim_id} - {str(e)}",
                exc_info=True,
                extra={"extra_fields": {"claim_id": claim_data.claim_id}}
            )
            await self.db.rollback()
            raise
        return await self.repository.to_response(claim)

    async def get_claim_by_id(self, claim_id: UUID) -> Optional[ClaimResponse]:
        """
        Get claim by UUID.

        Args:
            claim_id: Claim UUID

        Returns:
            Claim response or None if not found
        """
        claim = await self.repository.get_by_id(claim_id)
        if not claim:
            return None

        return await self.repository.to_response(claim)

    async def get_claim_by_claim_id(self, claim_id: str) -> Optional[ClaimResponse]:
        """
        Get claim by claim_id string.

        Args:
            claim_id: Unique claim identifier string

        Returns:
            Claim response or None if not found
        """
        claim = await self.repository.get_by_claim_id(claim_id)
        if not claim:
            return None

        return await self.repository.to_response(claim)

    async def get_all_claims(
        self, skip: int = 0, limit: int = 100
    ) -> List[ClaimResponse]:
        """
        Get all claims with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of claim responses
        """
        claims = await self.repository.get_all(skip=skip, limit=limit)
        return [await self.repository.to_response(claim) for claim in claims]

    async def get_claims_by_member(
        self, member_id: str, skip: int = 0, limit: int = 100
    ) -> List[ClaimResponse]:
        """
        Get claims by member ID.

        Args:
            member_id: Member/patient identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of claim responses
        """
        claims = await self.repository.get_by_member_id(
            member_id=member_id, skip=skip, limit=limit
        )
        return [await self.repository.to_response(claim) for claim in claims]

    async def get_claims_by_provider(
        self, provider_id: str, skip: int = 0, limit: int = 100
    ) -> List[ClaimResponse]:
        """
        Get claims by provider ID.

        Args:
            provider_id: Healthcare provider identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of claim responses
        """
        claims = await self.repository.get_by_provider_id(
            provider_id=provider_id, skip=skip, limit=limit
        )
        return [await self.repository.to_response(claim) for claim in claims]

    async def update_claim(
        self, claim_id: UUID, claim_data: ClaimUpdate
    ) -> Optional[ClaimResponse]:
        """
        Update a claim.

        Args:
            claim_id: Claim UUID
            claim_data: Claim update data

        Returns:
            Updated claim response or None if not found
        """
        claim = await self.repository.update(
            claim_uuid=claim_id,
            member_id=claim_data.member_id,
            provider_id=claim_data.provider_id,
            date_of_service=claim_data.date_of_service,
            cpt_code=claim_data.cpt_code,
            charge_amount=claim_data.charge_amount,
        )

        if not claim:
            return None

        await self.db.commit()
        return await self.repository.to_response(claim)

    async def delete_claim(self, claim_id: UUID) -> bool:
        """
        Delete a claim.

        Args:
            claim_id: Claim UUID

        Returns:
            True if deleted, False if not found
        """
        deleted = await self.repository.delete(claim_id)
        if deleted:
            await self.db.commit()
        return deleted
