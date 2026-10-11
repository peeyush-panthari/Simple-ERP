import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StickerSize(Base):
    """A saved label/sticker print template - Configuration > Sticker Size.
    Page size (a standard sheet or a custom one), the sticker's own
    dimensions, the column/row grid that fits on one page, and the
    margins/gaps a print job needs to lay every sticker out correctly.
    totalStickersPerPage is not stored - it's always columns*rows,
    computed at serialization time so it can never drift out of sync."""

    __tablename__ = "sticker_sizes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="sticker_sizes_tenant_name_uniq"),
        CheckConstraint("page_size in ('A4','A5','Letter','Custom')", name="sticker_sizes_page_size_check"),
        CheckConstraint("status in ('active','inactive')", name="sticker_sizes_status_check"),
        CheckConstraint("columns > 0", name="sticker_sizes_columns_check"),
        CheckConstraint("rows > 0", name="sticker_sizes_rows_check"),
        Index("sticker_sizes_tenant_idx", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    page_size: Mapped[str] = mapped_column(String, nullable=False, default="A4")
    # Always populated - for a standard page_size this is the standard mm
    # constant (see PAGE_SIZE_MM in the route), for "Custom" it's whatever
    # the caller supplied. Kept on every row (not looked up at read time)
    # so a row is a complete, self-contained print spec.
    page_width_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    page_height_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    sticker_width_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    sticker_height_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    columns: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    margin_left_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    margin_right_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    margin_top_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    margin_bottom_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    gap_horizontal_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    gap_vertical_mm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
