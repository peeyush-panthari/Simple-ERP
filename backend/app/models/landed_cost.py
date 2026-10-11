import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LandedCostVoucher(Base):
    """Header entity for a Landed Cost Voucher (LCV).

    Aggregates indirect inbound charges (freight, customs, insurance, handling)
    and apportions them across received goods receipt items to update unit valuation.
    """

    __tablename__ = "landed_cost_vouchers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "voucher_no", name="lcv_tenant_voucher_no_uniq"),
        CheckConstraint("status in ('draft', 'posted', 'cancelled')", name="lcv_status_check"),
        Index("lcv_tenant_status_date_idx", "tenant_id", "status", "posting_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_no: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    total_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LandedCostReceipt(Base):
    """One or more Goods Receipt Notes (GRNs) included in a Landed Cost Voucher."""

    __tablename__ = "landed_cost_receipts"
    __table_args__ = (
        UniqueConstraint("voucher_id", "grn_id", name="lcv_receipts_voucher_grn_uniq"),
        Index("lcv_receipts_voucher_idx", "voucher_id"),
        Index("lcv_receipts_grn_idx", "grn_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("landed_cost_vouchers.id", ondelete="CASCADE"), nullable=False)
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grns.id", ondelete="RESTRICT"), nullable=False)
    grn_number: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)


class LandedCostCharge(Base):
    """An indirect expense line (freight, customs, insurance, handling) to be apportioned."""

    __tablename__ = "landed_cost_charges"
    __table_args__ = (
        CheckConstraint(
            "charge_type in ('freight', 'customs', 'insurance', 'handling', 'demurrage', 'other')",
            name="lcv_charge_type_check",
        ),
        CheckConstraint(
            "apportion_by in ('value', 'weight', 'volume', 'quantity')",
            name="lcv_apportion_by_check",
        ),
        CheckConstraint("amount > 0", name="lcv_charge_amount_pos_check"),
        Index("lcv_charges_voucher_idx", "voucher_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("landed_cost_vouchers.id", ondelete="CASCADE"), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="freight")
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="SET NULL"), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    apportion_by: Mapped[str] = mapped_column(String(32), nullable=False, default="value")


class LandedCostItem(Base):
    """GRN line item receiving allocated cost share and its recalculated landed cost."""

    __tablename__ = "landed_cost_items"
    __table_args__ = (
        Index("lcv_items_voucher_idx", "voucher_id"),
        Index("lcv_items_grn_line_idx", "grn_line_id"),
        Index("lcv_items_product_idx", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("landed_cost_vouchers.id", ondelete="CASCADE"), nullable=False)
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    grn_number: Mapped[str] = mapped_column(String(64), nullable=False)
    grn_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    uom: Mapped[str] = mapped_column(String, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=1.0)
    volume_cbm: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0.01)
    base_unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    base_total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    allocated_charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    final_unit_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cost_variance_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
