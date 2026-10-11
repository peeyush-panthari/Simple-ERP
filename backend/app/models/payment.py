import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Payment(Base):
    """AP (outbound) and AR (inbound) payments AND reversals all share this
    one table and one "PAY" document-number sequence - a reversal is itself
    a Payment row with a negative amount and reverses_id set. amount has no
    >=0 check (deliberate - negative rows are valid reversal amounts).
    bank_account_last4/gateway_provider/gateway_payment_id are dead columns:
    no payment-gateway integration exists anywhere in this rewrite (or Node)."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="payments_tenant_number_uniq"),
        UniqueConstraint("tenant_id", "gateway_provider", "gateway_payment_id", name="payments_gateway_uniq"),
        CheckConstraint("direction in ('inbound','outbound')", name="payments_direction_check"),
        CheckConstraint("method in ('bank_transfer','cheque','cash','card','upi','gateway','adjustment')", name="payments_method_check"),
        CheckConstraint("status in ('pending_approval','posted','reversed','failed')", name="payments_status_check"),
        CheckConstraint("exchange_rate > 0", name="payments_exchange_rate_check"),
        Index("payments_tenant_party_date_idx", "tenant_id", "party_id", "payment_date"),
        Index("payments_tenant_direction_status_idx", "tenant_id", "direction", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    party_name: Mapped[str] = mapped_column(String, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    period: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False, default="bank_transfer")
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    unallocated: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="posted")
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String, nullable=True)
    gateway_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
