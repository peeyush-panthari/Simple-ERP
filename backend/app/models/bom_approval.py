import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BomApproval(Base):
    __tablename__ = "bom_approvals"
    __table_args__ = (
        CheckConstraint("decision in ('submitted','approved','rejected')", name="bom_approvals_decision_check"),
        Index("bom_approvals_version_at_idx", "version_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bom_versions.id", ondelete="CASCADE"), nullable=False)
    actor: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_email: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
