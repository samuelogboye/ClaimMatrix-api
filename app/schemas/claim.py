"""Pydantic schemas for Claim endpoints."""
from datetime import datetime, date
from typing import Optional
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    """Schema for creating a new claim."""

    claim_id: str = Field(..., min_length=1, max_length=255, description="Unique claim identifier")
    member_id: str = Field(..., min_length=1, max_length=255, description="Member/patient identifier")
    provider_id: str = Field(..., min_length=1, max_length=255, description="Healthcare provider identifier")
    date_of_service: date = Field(..., description="Date when service was provided")
    cpt_code: str = Field(..., min_length=1, max_length=50, description="CPT procedure code")
    charge_amount: Decimal = Field(..., gt=0, description="Charge amount for the service")

    model_config = {"from_attributes": True}


class ClaimResponse(BaseModel):
    """Schema for claim response."""

    id: UUID
    claim_id: str
    member_id: str
    provider_id: str
    date_of_service: date
    cpt_code: str
    charge_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimUpdate(BaseModel):
    """Schema for updating a claim."""

    member_id: Optional[str] = Field(None, min_length=1, max_length=255)
    provider_id: Optional[str] = Field(None, min_length=1, max_length=255)
    date_of_service: Optional[date] = None
    cpt_code: Optional[str] = Field(None, min_length=1, max_length=50)
    charge_amount: Optional[Decimal] = Field(None, gt=0)

    model_config = {"from_attributes": True}
