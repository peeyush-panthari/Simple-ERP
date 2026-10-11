import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductionConsumption(Base):
    __tablename__ = "production_consumption"
    __table_args__ = (Index("production_consumption_run_idx", "production_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    production_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    is_additional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
