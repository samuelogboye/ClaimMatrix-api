"""Audit Result model."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.claim import Claim


class AuditResult(Base):
    """Audit Result model for storing claim audit findings."""

    __tablename__ = "audit_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issues_found: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    suspicion_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2), nullable=False
    )
    recommended_action: Mapped[str] = mapped_column(String(500), nullable=False)
    audit_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    claim: Mapped["Claim"] = relationship(
        "Claim",
        back_populates="audit_results",
    )

    def __repr__(self) -> str:
        return f"<AuditResult(id={self.id}, claim_id={self.claim_id}, suspicion_score={self.suspicion_score})>"
