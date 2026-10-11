import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BomComponent(Base):
    __tablename__ = "bom_components"
    __table_args__ = (
        UniqueConstraint("bom_version_id", "line_no", name="bom_components_version_line_uniq"),
        CheckConstraint("quantity > 0", name="bom_components_quantity_check"),
        CheckConstraint("scrap_percent >= 0 and scrap_percent < 100", name="bom_components_scrap_check"),
        Index("bom_components_version_line_idx", "bom_version_id", "line_no"),
        Index("bom_components_tenant_product_idx", "tenant_id", "component_product_id"),
        Index(
            "bom_components_primary_uniq",
            "bom_version_id",
            "component_product_id",
            "uom",
            unique=True,
            postgresql_where=text("is_alternate = false"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bom_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bom_versions.id", ondelete="CASCADE"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    component_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    component_sku: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    scrap_percent: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, default=0)
    is_alternate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alternate_for_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
