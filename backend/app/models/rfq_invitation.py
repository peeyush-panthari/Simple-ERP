import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RfqInvitation(Base):
    __tablename__ = "rfq_invitations"
    __table_args__ = (
        UniqueConstraint("rfq_id", "carrier_id", name="rfq_invitations_rfq_carrier_uniq"),
        CheckConstraint("email_state in ('queued','sent','failed')", name="rfq_invitations_email_state_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    carrier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String, nullable=False)
    carrier_email: Mapped[str | None] = mapped_column(String, nullable=True)
    email_state: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    email_error: Mapped[str | None] = mapped_column(String, nullable=True)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
