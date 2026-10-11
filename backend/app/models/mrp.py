import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MrpRun(Base):
    __tablename__ = "mrp_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="mrp_runs_tenant_number_uniq"),
        CheckConstraint("status in ('draft', 'completed', 'cancelled')", name="mrp_runs_status_check"),
        Index("mrp_runs_tenant_created_idx", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    total_skus_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MrpPlannedOrder(Base):
    __tablename__ = "mrp_planned_orders"
    __table_args__ = (
        CheckConstraint("order_type in ('purchase', 'production')", name="mrp_planned_orders_type_check"),
        CheckConstraint("status in ('suggested', 'released', 'rejected')", name="mrp_planned_orders_status_check"),
        CheckConstraint("quantity > 0", name="mrp_planned_orders_quantity_check"),
        Index("mrp_planned_orders_run_idx", "mrp_run_id"),
        Index("mrp_planned_orders_tenant_status_idx", "tenant_id", "status"),
        Index("mrp_planned_orders_tenant_product_idx", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mrp_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mrp_runs.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    order_type: Mapped[str] = mapped_column(String, nullable=False)  # 'purchase' or 'production'
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    suggested_order_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_by_date: Mapped[date] = mapped_column(Date, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="suggested")
    source_demand: Mapped[str] = mapped_column(String, nullable=False)  # e.g., 'SO-001' or 'REORDER_POINT'
    released_reference_type: Mapped[str | None] = mapped_column(String, nullable=True)
    released_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    released_reference_number: Mapped[str | None] = mapped_column(String, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
