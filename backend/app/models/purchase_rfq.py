import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PurchaseRfq(Base):
    """Sourcing: a request for quotation sent to several vendors for what an approved requisition asks for.
    (Not the logistics RFQ, which asks carriers to quote a transport lane.)"""

    __tablename__ = "purchase_rfqs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="purchase_rfqs_tenant_number_uniq"),
        CheckConstraint("status in ('open','awarded','ordered','cancelled')", name="purchase_rfqs_status_check"),
        Index("purchase_rfqs_tenant_status_idx", "tenant_id", "status", "created_at"),
        Index("purchase_rfqs_requisition_idx", "requisition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    requisition_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="SET NULL"), nullable=True)
    requisition_number: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    terms: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    awarded_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PurchaseRfqLine(Base):
    __tablename__ = "purchase_rfq_lines"
    __table_args__ = (
        UniqueConstraint("rfq_id", "line_no", name="purchase_rfq_lines_line_no_uniq"),
        CheckConstraint("quantity > 0", name="purchase_rfq_lines_quantity_check"),
        Index("purchase_rfq_lines_rfq_idx", "rfq_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_rfqs.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    requisition_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    awarded_vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    award_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    purchase_order_number: Mapped[str | None] = mapped_column(String, nullable=True)


class PurchaseRfqVendor(Base):
    """A vendor invited to quote."""

    __tablename__ = "purchase_rfq_vendors"
    __table_args__ = (
        UniqueConstraint("rfq_id", "vendor_id", name="purchase_rfq_vendors_uniq"),
        CheckConstraint("status in ('invited','quoted','declined')", name="purchase_rfq_vendors_status_check"),
        CheckConstraint("email_state in ('not_sent','sent','failed','skipped')", name="purchase_rfq_vendors_email_state_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_rfqs.id", ondelete="CASCADE"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    vendor_email: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="invited")
    email_state: Mapped[str] = mapped_column(String, nullable=False, default="not_sent")
    email_error: Mapped[str | None] = mapped_column(String, nullable=True)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseQuotation(Base):
    """What one vendor offered, recorded by the buyer from the vendor's reply. One per vendor per RFQ."""

    __tablename__ = "purchase_quotations"
    __table_args__ = (
        UniqueConstraint("rfq_id", "vendor_id", name="purchase_quotations_rfq_vendor_uniq"),
        CheckConstraint("charges >= 0", name="purchase_quotations_charges_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_rfqs.id", ondelete="CASCADE"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    quote_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    quote_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PurchaseQuotationLine(Base):
    __tablename__ = "purchase_quotation_lines"
    __table_args__ = (
        UniqueConstraint("quotation_id", "rfq_line_id", name="purchase_quotation_lines_uniq"),
        CheckConstraint("unit_price is null or unit_price >= 0", name="purchase_quotation_lines_price_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_quotations.id", ondelete="CASCADE"), nullable=False)
    rfq_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_rfq_lines.id", ondelete="CASCADE"), nullable=False)
    # NULL = the vendor did not quote this line.
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    tax_code: Mapped[str] = mapped_column(String, nullable=False, default="GST0")
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
