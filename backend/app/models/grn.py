import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Grn(Base):
    __tablename__ = "grns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="grns_tenant_number_uniq"),
        UniqueConstraint("tenant_id", "vendor_id", "invoice_number", name="grns_tenant_vendor_invoice_uniq"),
        CheckConstraint("status in ('under_qc','posted','rejected','cancelled')", name="grns_status_check"),
        Index("grns_tenant_status_received_idx", "tenant_id", "status", "received_date"),
        Index("grns_tenant_po_idx", "tenant_id", "po_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="under_qc")
    received_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    vehicle_number: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(String, nullable=True)
    gate_entry_no: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String, nullable=True)
    # The Sticker Size template chosen at receipt (Receive Goods form) -
    # every item on this GRN prints its QR/label sized to this template.
    # sticker_size_name is a point-in-time snapshot (mirrors vendor_name/
    # warehouse_code above) so a later rename/delete of the template never
    # changes what an already-received GRN displays; sticker_size_id stays
    # the live link the QR/label renderer actually sizes against, cleared
    # (not the GRN) if the template itself is deleted.
    sticker_size_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sticker_sizes.id", ondelete="SET NULL"), nullable=True)
    sticker_size_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Checked on the Receive Goods form when the vendor's own goods already
    # carry their own QR-coded identifier - every InventoryItem this GRN
    # creates gets InventoryItem.vendor_qr_enabled stamped from this, which
    # is what unlocks attaching that vendor QR/ID on the item itself.
    has_vendor_qr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inspected_by: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String, nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
