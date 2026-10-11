import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductionRun(Base):
    __tablename__ = "production_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="production_runs_tenant_number_uniq"),
        CheckConstraint("quantity > 0", name="production_runs_quantity_check"),
        # 'planned' is a bare Daily Production Planning row - product,
        # warehouse, pack_id, production_date only, everything else null
        # until Complete Production fills it in and flips status to
        # 'posted' (see routes/inventory_movements.py's
        # _complete_production_run).
        CheckConstraint("status in ('planned','posted','reversed')", name="production_runs_status_check"),
        Index("production_runs_product_idx", "tenant_id", "product_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    bom_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bom_versions.id", ondelete="SET NULL"), nullable=True)
    bom_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="posted")
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ---- battery-pack traceability (finished-good identity/spec sheet for
    # this run - descriptive, so kept as free text rather than forcing a
    # numeric/unit shape the business hasn't specified) ----
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pack_id: Mapped[str | None] = mapped_column(String, nullable=True)
    shift: Mapped[str | None] = mapped_column(String, nullable=True)
    bms_make_model: Mapped[str | None] = mapped_column(String, nullable=True)
    screen_type: Mapped[str | None] = mapped_column(String, nullable=True)
    bms_id: Mapped[str | None] = mapped_column(String, nullable=True)
    bluetooth_id: Mapped[str | None] = mapped_column(String, nullable=True)
    iot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cells_name: Mapped[str | None] = mapped_column(String, nullable=True)
    cells_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    series_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parallel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enclosure_name: Mapped[str | None] = mapped_column(String, nullable=True)
    charge_capacity: Mapped[str | None] = mapped_column(String, nullable=True)
    discharge_capacity: Mapped[str | None] = mapped_column(String, nullable=True)
    branding_details: Mapped[str | None] = mapped_column(String, nullable=True)
