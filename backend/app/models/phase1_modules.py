"""Models for Phase 1 Supply Chain ERP Implementation:
1. Cycle Counting & Perpetual Inventory Audits
2. Indian Statutory e-Way Bill & GST e-Invoice IRN
3. Blanket Purchase Agreements & Rate Contracts
4. Mobile RF Barcode Terminal Scan Audits
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


# ==============================================================================
# 1. Cycle Counting & Perpetual Inventory Audits
# ==============================================================================
class CycleCountSession(Base):
    __tablename__ = "cycle_count_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    session_number: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False)
    counting_type: Mapped[str] = mapped_column(sa.String(32), default="abc_scheduled", nullable=False)  # abc_scheduled, annual_full, spot_audit
    target_abc_class: Mapped[Optional[str]] = mapped_column(sa.String(8), nullable=True)  # 'A', 'B', 'C', 'ALL'
    status: Mapped[str] = mapped_column(sa.String(32), default="draft", nullable=False)  # draft, in_progress, pending_review, completed, cancelled
    blind_count: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    audited_by_user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    approved_by_user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    total_items_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    discrepancy_items_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    net_variance_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    lines = relationship("CycleCountLine", back_populates="session", cascade="all, delete-orphan")


class CycleCountLine(Base):
    __tablename__ = "cycle_count_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("cycle_count_sessions.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    location_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    system_qty: Mapped[Decimal] = mapped_column(sa.Numeric(12, 4), default=0.00, nullable=False)
    counted_qty: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 4), nullable=True)
    variance_qty: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 4), nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(sa.Numeric(16, 4), default=0.00, nullable=False)
    variance_value: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(16, 2), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), default="pending", nullable=False)  # pending, counted, recount_requested, approved, adjusted
    recount_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    counter_user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    session = relationship("CycleCountSession", back_populates="lines")


# ==============================================================================
# 2. Indian Statutory e-Way Bill & GST e-Invoice IRN
# ==============================================================================
class EwayBill(Base):
    __tablename__ = "eway_bills"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True)
    challan_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    transfer_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    document_type: Mapped[str] = mapped_column(sa.String(32), default="INV", nullable=False)  # INV, CHL, BIL
    eway_bill_number: Mapped[Optional[str]] = mapped_column(sa.String(32), nullable=True)  # 12-digit statutory number
    eway_bill_date: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    supply_type: Mapped[str] = mapped_column(sa.String(8), default="O", nullable=False)  # O: Outward, I: Inward
    sub_supply_type: Mapped[str] = mapped_column(sa.String(32), default="Supply", nullable=False)  # Supply, Export, JobWork, Transfer, SKD_CKD
    doc_number: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    doc_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    from_gstin: Mapped[str] = mapped_column(sa.String(15), nullable=False)
    from_pincode: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    from_state_code: Mapped[str] = mapped_column(sa.String(4), default="27", nullable=False)
    to_gstin: Mapped[Optional[str]] = mapped_column(sa.String(15), nullable=True)
    to_pincode: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    to_state_code: Mapped[str] = mapped_column(sa.String(4), default="27", nullable=False)
    total_invoice_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    cgst_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    sgst_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    igst_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    cess_value: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    hsn_code: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    transporter_id: Mapped[Optional[str]] = mapped_column(sa.String(15), nullable=True)
    transporter_name: Mapped[Optional[str]] = mapped_column(sa.String(128), nullable=True)
    transport_mode: Mapped[str] = mapped_column(sa.String(16), default="1", nullable=False)  # 1: Road, 2: Rail, 3: Air, 4: Ship
    vehicle_number: Mapped[Optional[str]] = mapped_column(sa.String(32), nullable=True)
    vehicle_type: Mapped[str] = mapped_column(sa.String(16), default="R", nullable=False)  # R: Regular, O: Over Dimensional
    lr_rr_number: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    lr_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), default="generated", nullable=False)  # draft, generated, active, cancelled, expired
    cancel_reason: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    nic_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    qr_code_data: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


# ==============================================================================
# 3. Blanket Purchase Agreements & Rate Contracts
# ==============================================================================
class BlanketPurchaseOrder(Base):
    __tablename__ = "blanket_purchase_orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    bpa_number: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    vendor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False)
    warehouse_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(8), default="INR", nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), nullable=False)
    released_amount: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), default=0.00, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), default="active", nullable=False)  # draft, active, expired, closed
    payment_terms: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    lines = relationship("BlanketPoLine", back_populates="bpa", cascade="all, delete-orphan")


class BlanketPoLine(Base):
    __tablename__ = "blanket_po_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    bpa_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("blanket_purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    agreed_rate: Mapped[Decimal] = mapped_column(sa.Numeric(16, 4), nullable=False)
    committed_qty: Mapped[Decimal] = mapped_column(sa.Numeric(12, 4), nullable=False)
    released_qty: Mapped[Decimal] = mapped_column(sa.Numeric(12, 4), default=0.00, nullable=False)
    uom: Mapped[str] = mapped_column(sa.String(16), default="UNIT", nullable=False)

    bpa = relationship("BlanketPurchaseOrder", back_populates="lines")


# ==============================================================================
# 4. Mobile RF Barcode Terminal Scan Audits
# ==============================================================================
class MobileScanAudit(Base):
    __tablename__ = "mobile_scan_audits"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False)
    workflow_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # receive, putaway, pick, move, count
    scanned_barcode: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    matched_entity_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # sku, bin, batch, po, asn
    matched_entity_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(16), default="success", nullable=False)  # success, failed
    error_message: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
