"""Pydantic schemas for AuditResult endpoints."""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field


class AuditResultCreate(BaseModel):
    """Schema for creating a new audit result."""

    claim_id: UUID = Field(..., description="UUID of the claim being audited")
    issues_found: Dict[str, Any] = Field(default_factory=dict, description="JSON object containing audit issues")
    suspicion_score: Decimal = Field(..., ge=0, le=1, description="Suspicion score between 0 and 1")
    recommended_action: str = Field(..., min_length=1, max_length=500, description="Recommended action for the audit finding")

    model_config = {"from_attributes": True}


class AuditResultResponse(BaseModel):
    """Schema for audit result response."""

    id: UUID
    claim_id: UUID
    issues_found: Dict[str, Any]
    suspicion_score: Decimal
    recommended_action: str
    audit_timestamp: datetime

    model_config = {"from_attributes": True}


class AuditResultUpdate(BaseModel):
    """Schema for updating an audit result."""

    issues_found: Optional[Dict[str, Any]] = None
    suspicion_score: Optional[Decimal] = Field(None, ge=0, le=1)
    recommended_action: Optional[str] = Field(None, min_length=1, max_length=500)

    model_config = {"from_attributes": True}
