import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="locations_warehouse_code_uniq"),
        CheckConstraint("type in ('zone','aisle','rack','bin','staging','quarantine')", name="locations_type_check"),
        CheckConstraint("status in ('active','blocked','inactive')", name="locations_status_check"),
        Index("locations_warehouse_type_status_idx", "warehouse_id", "type", "status"),
        Index("locations_parent_idx", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    allowed_product_types: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    capacity_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_volume_cbm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    velocity_class: Mapped[str | None] = mapped_column(String(8), nullable=True)  # 'A', 'B', 'C'
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    temperature_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
