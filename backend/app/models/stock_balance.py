import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StockBalance(Base):
    """Materialised balance per (product, warehouse, batch, location, bucket).
    Strictly derivable from stock_ledger; kept as a table so availability
    checks are one indexed read. Written ONLY by inventory_ledger.post()."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "warehouse_id", "location_key", "batch_no", "bucket", name="stock_balances_key_uniq"),
        Index("stock_balances_product_idx", "tenant_id", "product_id", "warehouse_id", "bucket"),
        Index("stock_balances_expiry_idx", "tenant_id", "product_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    # Empty-string sentinel rather than NULL: a NULL in the unique key would let
    # the same bin be inserted twice.
    location_key: Mapped[str] = mapped_column(String, nullable=False, default="")
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String, nullable=False, default="")
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    bucket: Mapped[str] = mapped_column(String, nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
