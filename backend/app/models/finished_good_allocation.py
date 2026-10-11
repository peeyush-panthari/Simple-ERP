import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FinishedGoodAllocation(Base):
    """Which FinishedGoodItem(s) fund one Reservation, and how much of each -
    the finished-good mirror of production_consumption_items. A Reservation
    stays the aggregate soft hold (product+warehouse+qty, what ATP math
    already reads); this table is what makes releasing one specific picked
    unit precise and safe instead of guessing."""

    __tablename__ = "finished_good_allocations"
    __table_args__ = (Index("finished_good_allocations_reservation_idx", "reservation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    finished_good_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("finished_good_items.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
