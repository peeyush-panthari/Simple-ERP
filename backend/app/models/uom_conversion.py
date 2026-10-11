import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UomConversion(Base):
    __tablename__ = "uom_conversions"
    __table_args__ = (
        UniqueConstraint("product_id", "from_uom", "to_uom", name="uom_conversions_product_pair_uniq"),
        CheckConstraint("from_uom <> to_uom", name="uom_conversions_distinct_check"),
        CheckConstraint("factor > 0", name="uom_conversions_factor_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    from_uom: Mapped[str] = mapped_column(String, nullable=False)
    to_uom: Mapped[str] = mapped_column(String, nullable=False)
    factor: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
