import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CreditNote(Base):
    """No DB-level "exactly one of ar_invoice_id/ap_invoice_id" constraint -
    only enforced at the pydantic/route layer, matching Node's Zod .refine
    being route-layer-only too (unlike payment_allocations' real DB CHECK
    for the equivalent shape). status is always inserted as 'applied' -
    'issued'/'cancelled' are dead states, no cancel-credit-note route exists."""

    __tablename__ = "credit_notes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="credit_notes_tenant_number_uniq"),
        CheckConstraint("direction in ('inbound','outbound')", name="credit_notes_direction_check"),
        CheckConstraint("amount > 0", name="credit_notes_amount_check"),
        CheckConstraint("status in ('issued','applied','cancelled')", name="credit_notes_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False, default="outbound")
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    party_name: Mapped[str] = mapped_column(String, nullable=False)
    ar_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ar_invoices.id", ondelete="RESTRICT"), nullable=True)
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ap_invoices.id", ondelete="RESTRICT"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    period: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="issued")
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
