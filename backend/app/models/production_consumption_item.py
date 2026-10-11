import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductionConsumptionItem(Base):
    """Which InventoryItem(s) a production_consumption row actually drew
    from, and how much of each - written only by the add-additional-
    component endpoint (see inventory_movements.py), never by the original
    _post_production create flow. A consumption row with no rows here can't
    be safely un-consumed later (no way to know which pieces to credit
    back), which is exactly how the app distinguishes a removable additional
    component (added via edit) from one added at creation."""

    __tablename__ = "production_consumption_items"
    __table_args__ = (Index("production_consumption_items_consumption_idx", "production_consumption_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    production_consumption_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_consumption.id", ondelete="CASCADE"), nullable=False)
    # Null for a draw with no specific Inventory ID behind it (untracked /
    # opening-balance residue) - the ledger side still reverses cleanly,
    # there is just no InventoryItem.consumed_qty to credit back.
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
