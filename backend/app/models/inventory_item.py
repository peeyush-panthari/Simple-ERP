import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class InventoryItem(Base):
    """Piece/lot-level QC and putaway tracking, owned by warehouse. Complements
    (does not replace) inventory's aggregate stock_ledger/stock_balances - this
    is the receiving/QC/serial-tracking detail, the ledger is the master
    quantity-by-bucket record used for valuation, ATP and reservations."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "inventory_id", name="inventory_items_tenant_inventory_id_uniq"),
        CheckConstraint("status in ('under_qc','accepted','rejected','partial','returned_to_vendor','discarded')", name="inventory_items_status_check"),
        CheckConstraint("kind in ('piece','lot')", name="inventory_items_kind_check"),
        CheckConstraint("bucket in ('available','quarantine','damaged','expired')", name="inventory_items_bucket_check"),
        Index("inventory_items_grn_idx", "grn_id"),
        Index("inventory_items_grn_line_idx", "grn_line_id"),
        Index("inventory_items_tenant_status_idx", "tenant_id", "status"),
        Index("inventory_items_fifo_idx", "tenant_id", "product_id", "warehouse_id", "received_date"),
        Index("inventory_items_tenant_accepted_idx", "tenant_id", "accepted_qty"),
        Index("inventory_items_tenant_rejected_idx", "tenant_id", "rejected_qty"),
        Index("inventory_items_tenant_run_idx", "tenant_id", "consumed_run_id"),
        Index("inventory_items_transfer_idx", "transfer_id"),
        Index("inventory_items_bucket_idx", "bucket"),
        Index("inventory_items_tenant_written_off_idx", "tenant_id", "written_off_qty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inventory_id: Mapped[str] = mapped_column(String, nullable=False)
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="CASCADE"), nullable=False)
    grn_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grn_lines.id", ondelete="CASCADE"), nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String, nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # under_qc -> accepted/rejected/partial at QC time; a rejected (or the
    # rejected portion of a partial) item can then be disposed of via
    # POST /inventory-items/<id>/dispose into one of the two further
    # terminal states, returned_to_vendor or discarded - see grns.py.
    status: Mapped[str] = mapped_column(String, nullable=False, default="under_qc")
    kind: Mapped[str] = mapped_column(String, nullable=False, default="piece")
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    uom: Mapped[str | None] = mapped_column(String, nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    consumed_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    consumed_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    consumed_run_number: Mapped[str | None] = mapped_column(String, nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    qc_by: Mapped[str | None] = mapped_column(String, nullable=True)
    qc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(String, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String, nullable=True)
    # Set while this exact piece/lot is the subject of an in-flight Transfer
    # (picked by Inventory ID rather than FIFO-drawn) - warehouse_id already
    # points at the destination by then (see _create_transfer), so this is
    # what makes it read "In Transit" instead of "Available" and keeps it
    # out of any other pick (FIFO consumption, another transfer) until the
    # transfer is completed or the item is otherwise released. Cleared (not
    # the item's own status) on completion - status still reflects QC
    # outcome, this is a separate, physical-location concern.
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transfers.id", ondelete="SET NULL"), nullable=True)
    # Which condition bucket this exact piece/lot currently sits in -
    # available/quarantine/damaged/expired, the same vocabulary the
    # aggregate stock_ledger already used at product+warehouse level, now
    # also tracked per-item so a status-change picked by Inventory ID
    # (see _create_status_change) actually moves that unit's own displayed
    # status/availability, not just the aggregate bucket totals. Only
    # meaningful once status=="accepted" (an under_qc/rejected item has no
    # condition bucket yet); defaults to "available" like every newly
    # accepted item is.
    bucket: Mapped[str] = mapped_column(String, nullable=False, default="available")
    # Cumulative quantity written off this exact piece/lot via Post
    # Adjustment picked by Inventory ID (see _create_adjustment) - kept
    # separate from consumed_qty (drawn by production) and rejected_qty
    # (failed QC) so a manual write-off never disturbs those, or the
    # GRN-accepted accepted_qty figure other code (PO tolerance, costing)
    # already treats as historical fact. A positive adjustment against an
    # already-written-off item reverses this first, before ever touching
    # accepted_qty.
    written_off_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    # Stamped from Grn.has_vendor_qr at receipt (see _create_inventory_for_line)
    # - "Vendor's QR and ID" was checked on the Receive Goods form, so this
    # specific piece/lot may have the vendor's own QR-coded identifier
    # attached via POST /inventory-items/<id>/vendor-qr. vendor_inventory_id
    # is that vendor-supplied text - decoded from an uploaded photo of the
    # vendor's own QR sticker, or typed in directly if the photo doesn't
    # decode - kept as a separate, purely informational field (never used
    # to look this item up the way inventory_id is).
    vendor_qr_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vendor_inventory_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # removed by a pre-post GRN edit
