import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FinishedGoodItem(Base):
    """Piece/lot-level tracking for finished-good stock, sourced either from a
    production run's OUTPUT (`production_run_id` set) or converted from a
    GRN-received InventoryItem at QC-pass time (`source_inventory_item_id`
    set - see grn_post.py::_convert_finished_good_receipts) - exactly one of
    the two is ever set (finished_good_items_origin_check). Either way: one
    row per physical unit for a UOM=UNIT product (kind='piece'), one row for
    the whole quantity otherwise (kind='lot') - same split _create_inventory_
    for_line makes for GRN receiving (grns.py). `status` doubles as a condition value
    (quarantine/damaged/expired) AND a reservation/shipping lifecycle value
    (available/reserved/partially_reserved/shipped) - condition always wins
    (an item can't be simultaneously quarantined and reserved), and
    allocation/shipping never overwrite a condition status; see
    app/services/finished_good_status.py::recompute_status. `allocated_qty`/
    `allocated_order_id` track the live claim, `shipped_qty` the permanent
    shipped total, mirroring how InventoryItem separates its own QC `status`
    from `consumed_qty`/`consumed_run_id`."""

    __tablename__ = "finished_good_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "inventory_id", name="finished_good_items_tenant_inventory_id_uniq"),
        CheckConstraint("status in ('available','quarantine','damaged','expired','reserved','partially_reserved','shipped')", name="finished_good_items_status_check"),
        CheckConstraint("kind in ('piece','lot')", name="finished_good_items_kind_check"),
        CheckConstraint("shipped_qty >= 0", name="finished_good_items_shipped_qty_check"),
        CheckConstraint(
            "(production_run_id is not null) != (source_inventory_item_id is not null)",
            name="finished_good_items_origin_check",
        ),
        Index("finished_good_items_run_idx", "production_run_id"),
        Index("finished_good_items_source_item_idx", "source_inventory_item_id"),
        Index("finished_good_items_tenant_status_idx", "tenant_id", "status"),
        Index("finished_good_items_fifo_idx", "tenant_id", "product_id", "warehouse_id", "received_date"),
        Index("finished_good_items_tenant_order_idx", "tenant_id", "allocated_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inventory_id: Mapped[str] = mapped_column(String, nullable=False)
    production_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=True)
    source_inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    kind: Mapped[str] = mapped_column(String, nullable=False, default="piece")
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    uom: Mapped[str | None] = mapped_column(String, nullable=True)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    allocated_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    shipped_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    allocated_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    allocated_order_number: Mapped[str | None] = mapped_column(String, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
