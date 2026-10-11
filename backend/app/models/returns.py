import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Rma(Base):
    """Customer Return / Return Material Authorization (RMA)."""

    __tablename__ = "rmas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="rmas_tenant_number_uniq"),
        CheckConstraint(
            "status in ('draft', 'authorized', 'goods_received', 'inspected', 'completed', 'cancelled')",
            name="rmas_status_check",
        ),
        Index("rmas_tenant_status_idx", "tenant_id", "status"),
        Index("rmas_tenant_customer_idx", "tenant_id", "customer_id"),
        Index("rmas_tenant_order_idx", "tenant_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    return_reason: Mapped[str] = mapped_column(String, nullable=False)
    carrier: Mapped[str | None] = mapped_column(String, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String, nullable=True)
    credit_note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("credit_notes.id", ondelete="SET NULL"), nullable=True)
    credit_note_number: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    authorized_by: Mapped[str | None] = mapped_column(String, nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_by: Mapped[str | None] = mapped_column(String, nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RmaLine(Base):
    __tablename__ = "rma_lines"
    __table_args__ = (
        UniqueConstraint("rma_id", "line_no", name="rma_lines_rma_line_no_uniq"),
        CheckConstraint("authorized_qty > 0", name="rma_lines_authorized_qty_check"),
        CheckConstraint("received_qty >= 0", name="rma_lines_received_qty_check"),
        CheckConstraint("restocked_qty >= 0", name="rma_lines_restocked_qty_check"),
        CheckConstraint("scrapped_qty >= 0", name="rma_lines_scrapped_qty_check"),
        CheckConstraint("repaired_qty >= 0", name="rma_lines_repaired_qty_check"),
        Index("rma_lines_rma_idx", "rma_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rma_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rmas.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    order_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("order_lines.id", ondelete="SET NULL"), nullable=True)
    authorized_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    restocked_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    scrapped_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    repaired_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    inspection_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    disposition_notes: Mapped[str | None] = mapped_column(String, nullable=True)


class Rtv(Base):
    """Return to Vendor (RTV)."""

    __tablename__ = "rtvs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="rtvs_tenant_number_uniq"),
        CheckConstraint(
            "status in ('draft', 'approved', 'dispatched', 'completed', 'cancelled')",
            name="rtvs_status_check",
        ),
        Index("rtvs_tenant_status_idx", "tenant_id", "status"),
        Index("rtvs_tenant_vendor_idx", "tenant_id", "vendor_id"),
        Index("rtvs_tenant_po_idx", "tenant_id", "po_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True)
    grn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="SET NULL"), nullable=True)
    grn_number: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    return_reason: Mapped[str] = mapped_column(String, nullable=False)
    transporter: Mapped[str | None] = mapped_column(String, nullable=True)
    vehicle_no: Mapped[str | None] = mapped_column(String, nullable=True)
    lr_no: Mapped[str | None] = mapped_column(String, nullable=True)
    debit_note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("credit_notes.id", ondelete="SET NULL"), nullable=True)
    debit_note_number: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RtvLine(Base):
    __tablename__ = "rtv_lines"
    __table_args__ = (
        UniqueConstraint("rtv_id", "line_no", name="rtv_lines_rtv_line_no_uniq"),
        CheckConstraint("quantity > 0", name="rtv_lines_quantity_check"),
        Index("rtv_lines_rtv_idx", "rtv_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rtv_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rtvs.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
