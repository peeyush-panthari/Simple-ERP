import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Identity, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

MOVEMENT_TYPES = (
    "receipt",
    "issue",
    "adjustment",
    "transfer_out",
    "transfer_in",
    "production_consume",
    "production_output",
    "scrap",
    "reversal",
    "status_change",
    "opening_balance",
)
BUCKETS = ("available", "quarantine", "damaged", "in_transit", "expired", "reserved")

# Reused verbatim by inventory_ledger.post()'s ON CONFLICT target - the text
# must match the index definition exactly for Postgres to infer it.
IDEMPOTENCY_COALESCED_BATCH_NO = text("coalesce(batch_no, '')")
IDEMPOTENCY_COALESCED_LOCATION_ID = text("coalesce(location_id::text, '')")


class StockLedger(Base):
    """Append-only. The single source of truth for stock - balances are a
    projection of this table, corrections are reversing entries, no row is
    ever updated or deleted."""

    __tablename__ = "stock_ledger"
    __table_args__ = (
        CheckConstraint("bucket in ('available','quarantine','damaged','in_transit','expired','reserved')", name="stock_ledger_bucket_check"),
        CheckConstraint(
            "movement_type in ('receipt','issue','adjustment','transfer_out','transfer_in',"
            "'production_consume','production_output','scrap','reversal','status_change','opening_balance')",
            name="stock_ledger_movement_type_check",
        ),
        Index("stock_ledger_balance_idx", "tenant_id", "product_id", "warehouse_id", "bucket"),
        Index("stock_ledger_batch_idx", "tenant_id", "product_id", "warehouse_id", "batch_no", postgresql_where=text("batch_no is not null")),
        Index("stock_ledger_reference_idx", "tenant_id", "reference_type", "reference_id"),
        Index("stock_ledger_seq_idx", "tenant_id", text("seq desc")),
        Index(
            "stock_ledger_idempotency_idx",
            "tenant_id",
            "reference_type",
            "reference_id",
            "movement_type",
            "product_id",
            IDEMPOTENCY_COALESCED_BATCH_NO,
            IDEMPOTENCY_COALESCED_LOCATION_ID,
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    bucket: Mapped[str] = mapped_column(String, nullable=False, default="available")
    movement_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_type: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[str] = mapped_column(String, nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_ledger.id"), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
