import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GrnLine(Base):
    __tablename__ = "grn_lines"
    __table_args__ = (
        UniqueConstraint("grn_id", "line_no", name="grn_lines_grn_line_no_uniq"),
        CheckConstraint("received_qty >= 0", name="grn_lines_received_check"),
        CheckConstraint("accepted_qty >= 0", name="grn_lines_accepted_check"),
        CheckConstraint("rejected_qty >= 0", name="grn_lines_rejected_check"),
        CheckConstraint("accepted_qty + rejected_qty <= received_qty", name="grn_lines_accept_reject_le_received_check"),
        CheckConstraint("quality_status in ('pending','passed','failed','partial')", name="grn_lines_quality_status_check"),
        Index("grn_lines_grn_idx", "grn_id"),
        Index("grn_lines_tenant_po_line_idx", "tenant_id", "po_line_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    po_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("po_lines.id", ondelete="RESTRICT"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    ordered_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # removed by a pre-post GRN edit
