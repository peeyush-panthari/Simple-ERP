import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PoLine(Base):
    __tablename__ = "po_lines"
    __table_args__ = (
        UniqueConstraint("po_id", "line_no", name="po_lines_line_no_uniq"),
        CheckConstraint("quantity > 0", name="po_lines_quantity_check"),
        CheckConstraint("unit_price >= 0", name="po_lines_unit_price_check"),
        CheckConstraint("discount >= 0", name="po_lines_discount_check"),
        CheckConstraint("received_qty >= 0", name="po_lines_received_check"),
        CheckConstraint("rejected_qty >= 0", name="po_lines_rejected_check"),
        CheckConstraint("status in ('open','partial','closed','cancelled')", name="po_lines_status_check"),
        Index("po_lines_po_idx", "po_id"),
        Index("po_lines_product_idx", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
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
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
