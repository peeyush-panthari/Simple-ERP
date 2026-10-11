import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PaymentAllocation(Base):
    """amount has no sign check - negative for the mirrored rows a payment
    reversal inserts under the reversal payment's id. Exactly one of
    ap_invoice_id/ar_invoice_id is enforced at the DB level here (unlike
    credit_notes, where the equivalent shape is only checked at the route
    layer - a real, intentional asymmetry, not an oversight)."""

    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("(ap_invoice_id is not null) != (ar_invoice_id is not null)", name="payment_allocations_exactly_one_check"),
        Index("payment_allocations_payment_idx", "payment_id"),
        Index("payment_allocations_ap_invoice_idx", "ap_invoice_id"),
        Index("payment_allocations_ar_invoice_idx", "ar_invoice_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ap_invoices.id", ondelete="RESTRICT"), nullable=True)
    ar_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ar_invoices.id", ondelete="RESTRICT"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
