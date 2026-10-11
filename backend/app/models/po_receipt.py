import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PoReceipt(Base):
    """Which GRNs have already been applied to which PO line - the idempotency
    guard for procurement_repo.apply_grn_receipt() (a redelivered/retried call
    cannot double-count a receipt)."""

    __tablename__ = "po_receipts"
    __table_args__ = (
        UniqueConstraint("grn_id", "po_line_id", name="po_receipts_grn_line_uniq"),
        Index("po_receipts_po_idx", "po_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    po_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("po_lines.id", ondelete="CASCADE"), nullable=False)
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="CASCADE"), nullable=False)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
