import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Rfq(Base):
    __tablename__ = "rfqs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="rfqs_tenant_number_uniq"),
        CheckConstraint("status in ('open','awarded','cancelled','expired')", name="rfqs_status_check"),
        Index("rfqs_transport_request_idx", "transport_request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    transport_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transport_requests.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Bare uuid, no FK - matches Node: quotations.rfq_id already FKs back to this
    # table, so FK-ing this one too would create an rfqs<->quotations cycle.
    awarded_quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)  # dead column - no cancel route, matches Node
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
