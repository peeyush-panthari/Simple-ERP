import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LogisticsInvoice(Base):
    __tablename__ = "logistics_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="logistics_invoices_tenant_number_uniq"),
        CheckConstraint("amount >= 0", name="logistics_invoices_amount_check"),
        # pending/rejected/posted are schema-valid but unreachable - every route
        # inserts status='approved' directly, matching Node.
        CheckConstraint("status in ('pending','approved','rejected','posted')", name="logistics_invoices_status_check"),
        Index("logistics_invoices_dispatch_idx", "dispatch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dispatches.id", ondelete="RESTRICT"), nullable=False)
    carrier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String, nullable=False)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    variance_approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    variance_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
