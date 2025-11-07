"""Claim model."""
import uuid
from datetime import datetime, date, timezone
from typing import TYPE_CHECKING
from decimal import Decimal

from sqlalchemy import String, DateTime, Date, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.audit_result import AuditResult


class Claim(Base):
    """Claim model for storing medical claim information."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    member_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    cpt_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    charge_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    audit_results: Mapped[list["AuditResult"]] = relationship(
        "AuditResult",
        back_populates="claim",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Claim(id={self.id}, claim_id={self.claim_id}, charge_amount={self.charge_amount})>"
