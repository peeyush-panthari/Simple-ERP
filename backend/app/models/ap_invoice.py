import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ApInvoice(Base):
    """Vendor invoice (payable). No credit_amount column at all - unlike
    ar_invoices, an AP credit note reduces `amount` directly (see
    routes/finance.py's credit-note handler). paid_amount has no upper-bound
    check against amount - deliberate, load-bearing for the
    OVERPAYMENT_POLICY=credit phantom-credit quirk."""

    __tablename__ = "ap_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="ap_invoices_tenant_number_uniq"),
        UniqueConstraint("tenant_id", "vendor_id", "vendor_invoice_no", name="ap_invoices_vendor_invoice_uniq"),
        CheckConstraint("source_type in ('purchase','logistics','manual')", name="ap_invoices_source_type_check"),
        CheckConstraint("status in ('draft','open','partially_paid','settled','cancelled','disputed')", name="ap_invoices_status_check"),
        CheckConstraint("match_status in ('unmatched','matched','variance','not_applicable')", name="ap_invoices_match_status_check"),
        CheckConstraint("exchange_rate > 0", name="ap_invoices_exchange_rate_check"),
        CheckConstraint("amount >= 0", name="ap_invoices_amount_check"),
        CheckConstraint("paid_amount >= 0", name="ap_invoices_paid_amount_check"),
        Index("ap_invoices_tenant_status_due_idx", "tenant_id", "status", "due_date"),
        Index("ap_invoices_tenant_vendor_idx", "tenant_id", "vendor_id"),
        Index("ap_invoices_tenant_po_idx", "tenant_id", "po_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="purchase")
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_invoice_no: Mapped[str | None] = mapped_column(String, nullable=True)
    po_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True)
    grn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="SET NULL"), nullable=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    match_status: Mapped[str] = mapped_column(String, nullable=False, default="unmatched")
    match_variance: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    match_note: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispute_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
