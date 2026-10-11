import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PurchaseRequisition(Base):
    """An employee's request to the Purchase department for something they need. A requisition is not a commitment to
    a vendor: Purchase reviews it, then raises a purchase order (linked back here) or rejects it."""

    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="purchase_requisitions_tenant_number_uniq"),
        CheckConstraint("status in ('draft','pending_manager','submitted','approved','sourcing','ordered','rejected','cancelled')", name="purchase_requisitions_status_check"),
        CheckConstraint("rejected_stage is null or rejected_stage in ('manager','purchase')", name="purchase_requisitions_rejected_stage_check"),
        CheckConstraint("priority in ('low','normal','high','urgent')", name="purchase_requisitions_priority_check"),
        Index("purchase_requisitions_tenant_status_idx", "tenant_id", "status", "created_at"),
        Index("purchase_requisitions_requester_idx", "tenant_id", "requester_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requester_name: Mapped[str] = mapped_column(String, nullable=False)
    requester_email: Mapped[str | None] = mapped_column(String, nullable=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    justification: Mapped[str | None] = mapped_column(String, nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String, nullable=True)
    manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manager_note: Mapped[str | None] = mapped_column(String, nullable=True)
    rejected_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String, nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    purchase_order_number: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PurchaseRequisitionLine(Base):
    """One thing being asked for: a catalogue product, or free text when the item is not in the product master yet."""

    __tablename__ = "purchase_requisition_lines"
    __table_args__ = (
        UniqueConstraint("requisition_id", "line_no", name="purchase_requisition_lines_line_no_uniq"),
        CheckConstraint("quantity > 0", name="purchase_requisition_lines_quantity_check"),
        Index("purchase_requisition_lines_req_idx", "requisition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    item_name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
