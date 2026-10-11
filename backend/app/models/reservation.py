import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Reservation(Base):
    """A hold that moves stock from the `available` bucket into `reserved` -
    a real ledger posting, not just a read-time subtraction. `batch_no`/
    `location_id` above are only the single-batch case; a FEFO reservation
    that drew from multiple batches keeps its exact per-leg breakdown in
    `allocation_legs` (list of {batchNo, locationId, quantity}) so
    release/issue can reverse each leg precisely instead of guessing."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="reservations_quantity_check"),
        CheckConstraint("issued_qty >= 0 and issued_qty <= quantity", name="reservations_issued_qty_check"),
        CheckConstraint("status in ('open','issued','released','expired')", name="reservations_status_check"),
        Index("reservations_open_idx", "tenant_id", "product_id", "warehouse_id", postgresql_where=text("status = 'open'")),
        Index("reservations_order_line_uniq", "order_line_id", unique=True, postgresql_where=text("status = 'open' and order_line_id is not null")),
        Index("reservations_order_idx", "tenant_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    allocation_legs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Cumulative quantity issued so far - lets issue_reservation_partial draw
    # this reservation down across more than one shipment instead of only
    # supporting one all-or-nothing issue. `status` only flips to 'issued'
    # once issued_qty reaches `quantity`; allocation_legs is mutated in
    # lockstep (each partial issue shrinks/drops the legs it drew from) so
    # `_reservation_legs` always reflects what's left to issue, not what the
    # reservation started with.
    issued_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    order_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reference_type: Mapped[str] = mapped_column(String, nullable=False, default="order")
    reference_no: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
