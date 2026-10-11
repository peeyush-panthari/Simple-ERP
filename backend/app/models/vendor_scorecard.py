import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VendorScorecard(Base):
    __tablename__ = "vendor_scorecards"
    __table_args__ = (
        UniqueConstraint("tenant_id", "vendor_id", "period", name="vendor_scorecards_vendor_period_uniq"),
        CheckConstraint("overall_score >= 0 and overall_score <= 100", name="vendor_scorecards_overall_check"),
        CheckConstraint("grade in ('A', 'B', 'C', 'D')", name="vendor_scorecards_grade_check"),
        Index("vendor_scorecards_tenant_vendor_idx", "tenant_id", "vendor_id"),
        Index("vendor_scorecards_tenant_grade_idx", "tenant_id", "grade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)  # e.g., 'all_time', 'last_90_days'
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    otif_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    price_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    grade: Mapped[str] = mapped_column(String, nullable=False)  # 'A', 'B', 'C', 'D'
    total_pos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_grns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_lead_time_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
