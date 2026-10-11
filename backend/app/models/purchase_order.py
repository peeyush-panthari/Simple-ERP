import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", "revision", name="purchase_orders_tenant_number_uniq"),
        CheckConstraint(
            "status in ('draft','pending_approval','approved','issued','partially_received','received','closed','cancelled')",
            name="purchase_orders_status_check",
        ),
        CheckConstraint("exchange_rate > 0", name="purchase_orders_exchange_rate_check"),
        CheckConstraint("email_state in ('not_sent','queued','sent','failed')", name="purchase_orders_email_state_check"),
        CheckConstraint("ack_status in ('pending','acknowledged','acknowledged_with_changes','declined')", name="purchase_orders_ack_status_check"),
        CheckConstraint("receipt_status in ('none','partial','full')", name="purchase_orders_receipt_status_check"),
        CheckConstraint("expected_date >= po_date", name="purchase_orders_dates_ck"),
        Index("purchase_orders_tenant_status_idx", "tenant_id", "status", "po_date"),
        Index("purchase_orders_vendor_idx", "tenant_id", "vendor_id"),
        Index("purchase_orders_warehouse_idx", "tenant_id", "warehouse_id"),
        Index("purchase_orders_supersedes_idx", "tenant_id", "supersedes_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String, nullable=False)
    business_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("business_entities.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    po_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    cgst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    incoterms: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_state: Mapped[str] = mapped_column(String, nullable=False, default="not_sent")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_error: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Vendor acknowledgement: the vendor's reply to the issued order, recorded by the buyer.
    ack_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    ack_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ack_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    ack_confirmed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ack_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    ack_recorded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    ack_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_status: Mapped[str] = mapped_column(String, nullable=False, default="none")
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
