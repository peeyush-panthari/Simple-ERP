import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ArInvoice(Base):
    """Customer receivable, created only via finance_repo.post_receivable()
    (Order's direct call after raising its own tax invoice) - there is no
    human-facing "post AR invoice" route, matching Node exactly.

    No ar_invoice_lines table at all - a real, permanent asymmetry with AP
    (which does have line-level detail). The e-invoice columns (irn, ack_no,
    ack_date, signed_qr, einvoice_status, einvoice_error) are dead: nothing
    in this rewrite (or Node) ever populates them beyond their defaults."""

    __tablename__ = "ar_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="ar_invoices_tenant_number_uniq"),
        CheckConstraint("status in ('open','partially_paid','settled','written_off','cancelled')", name="ar_invoices_status_check"),
        CheckConstraint("exchange_rate > 0", name="ar_invoices_exchange_rate_check"),
        CheckConstraint("amount >= 0", name="ar_invoices_amount_check"),
        CheckConstraint("paid_amount >= 0", name="ar_invoices_paid_amount_check"),
        CheckConstraint("credit_amount >= 0", name="ar_invoices_credit_amount_check"),
        CheckConstraint("einvoice_status in ('not_required','pending','registered','cancelled','failed')", name="ar_invoices_einvoice_status_check"),
        Index("ar_invoices_tenant_status_due_idx", "tenant_id", "status", "due_date"),
        Index("ar_invoices_tenant_customer_idx", "tenant_id", "customer_id"),
        Index("ar_invoices_tenant_order_idx", "tenant_id", "order_id"),
        Index("ar_invoices_irn_uniq", "irn", unique=True, postgresql_where=text("irn is not null")),
        # Node's own migration filters this partial index on `status`, not `einvoice_status` -
        # looks like a typo in the original, ported verbatim rather than "fixed".
        Index("ar_invoices_einvoice_idx", "tenant_id", "einvoice_status", postgresql_where=text("status in ('pending','failed')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    written_off_by: Mapped[str | None] = mapped_column(String, nullable=True)
    written_off_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    irn: Mapped[str | None] = mapped_column(String, nullable=True)
    ack_no: Mapped[str | None] = mapped_column(String, nullable=True)
    ack_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_qr: Mapped[str | None] = mapped_column(String, nullable=True)
    einvoice_status: Mapped[str] = mapped_column(String, nullable=False, default="not_required")
    einvoice_error: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
