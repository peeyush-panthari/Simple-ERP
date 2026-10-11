import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        # One live quote per carrier per RFQ - a revision supersedes rather
        # than adds (enforced via ON CONFLICT DO UPDATE upsert), matching Node.
        UniqueConstraint("rfq_id", "carrier_id", name="quotations_rfq_carrier_uniq"),
        CheckConstraint("amount >= 0", name="quotations_amount_check"),
        CheckConstraint("status in ('received','approved','rejected','expired')", name="quotations_status_check"),
        Index("quotations_rfq_amount_idx", "rfq_id", "amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=False)
    carrier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    transit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_level: Mapped[str | None] = mapped_column(String, nullable=True)
    inclusions: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received")
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
