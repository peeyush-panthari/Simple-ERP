import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PoDispatch(Base):
    """One shipment of a purchase order, as the vendor reports it: transport, e-way bill, packing list, delivery challan."""

    __tablename__ = "po_dispatches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="po_dispatches_tenant_number_uniq"),
        CheckConstraint("status in ('in_transit','delivered','cancelled')", name="po_dispatches_status_check"),
        Index("po_dispatches_po_idx", "po_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_transit")
    dispatch_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_arrival: Mapped[date | None] = mapped_column(Date, nullable=True)
    transporter: Mapped[str | None] = mapped_column(String, nullable=True)
    vehicle_no: Mapped[str | None] = mapped_column(String, nullable=True)
    lr_no: Mapped[str | None] = mapped_column(String, nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    packages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    invoice_no: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    packing_list_no: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_challan_no: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_challan_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    eway_bill_no: Mapped[str | None] = mapped_column(String, nullable=True)
    eway_bill_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PoDispatchLine(Base):
    __tablename__ = "po_dispatch_lines"
    __table_args__ = (
        UniqueConstraint("dispatch_id", "po_line_id", name="po_dispatch_lines_uniq"),
        CheckConstraint("quantity > 0", name="po_dispatch_lines_quantity_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("po_dispatches.id", ondelete="CASCADE"), nullable=False)
    po_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("po_lines.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)


class PoDocument(Base):
    """A file the vendor supplied for a purchase order (acknowledgement, proforma invoice, technical papers...) or for one of
    its shipments (packing list, delivery challan, e-way bill...). The bytes live in `documents`; this row says what it is."""

    __tablename__ = "po_documents"
    __table_args__ = (Index("po_documents_po_idx", "po_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    dispatch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("po_dispatches.id", ondelete="CASCADE"), nullable=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    bytes_: Mapped[int] = mapped_column("bytes", Integer, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    uploaded_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
