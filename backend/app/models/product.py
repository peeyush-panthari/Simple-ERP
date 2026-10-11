import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="products_tenant_sku_uniq"),
        CheckConstraint("type in ('raw_material','finished_good','consumable','service')", name="products_type_check"),
        CheckConstraint("status in ('draft','active','deprecated')", name="products_status_check"),
        Index("products_tenant_status_idx", "tenant_id", "status", "type"),
        Index("products_category_idx", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    make: Mapped[str | None] = mapped_column(String, nullable=True)
    model_number: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=True)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    alternate_uoms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    hsn_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    batch_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expiry_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_conditions: Mapped[str | None] = mapped_column(String, nullable=True)
    reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    reorder_qty: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    purchasable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecated_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    first_transaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_transaction_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
