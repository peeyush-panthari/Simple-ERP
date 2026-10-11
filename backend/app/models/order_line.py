import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "line_no", name="order_lines_line_no_uniq"),
        CheckConstraint("quantity > 0", name="order_lines_quantity_check"),
        CheckConstraint("unit_price >= 0", name="order_lines_unit_price_check"),
        CheckConstraint("discount >= 0", name="order_lines_discount_check"),
        CheckConstraint("allocated_qty >= 0", name="order_lines_allocated_check"),
        CheckConstraint("shipped_qty >= 0", name="order_lines_shipped_check"),
        CheckConstraint("packed_qty >= 0 and packed_qty <= allocated_qty", name="order_lines_packed_check"),
        CheckConstraint("status in ('open','allocated','shipped','cancelled')", name="order_lines_status_check"),
        Index("order_lines_order_idx", "order_id"),
        Index("order_lines_tenant_product_idx", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    tax_code: Mapped[str] = mapped_column(String, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)
    allocated_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    # Independent of `status` (open/allocated/shipped/cancelled) the same way
    # Order.packing_status is independent of Order.status - a warehouse
    # checkpoint, not a state-machine step. Grows only via POST
    # /orders/lines/:id/pack (Order Shipping tab), bounded above by
    # allocated_qty: you can't pack more than what's actually been reserved
    # for this line.
    packed_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    shipped_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
