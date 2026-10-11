"""Phase 2 Supply Chain ERP Models.

Modules:
1. Wave & Batch Picking Engine (pick_waves, pick_wave_orders, pick_wave_lines)
2. Customer B2B Self-Service Portal (customer_portal_users, customer_rma_tickets)
3. In-Process Quality Control (IPQC) & CoA (ipqc_inspections, certificates_of_analysis)
4. Approved Vendor List (AVL) Governance (approved_vendors, vendor_compliance_certs)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


# ==============================================================================
# 1. WAVE & BATCH PICKING OPTIMIZATION ENGINE
# ==============================================================================

class PickWave(Base):
    """Batched group of orders released together for consolidated warehouse picking."""
    __tablename__ = "pick_waves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    wave_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)

    wave_type: Mapped[str] = mapped_column(String(32), default="carrier_cutoff")  # carrier_cutoff, zone_batch, single_line_multi_order
    status: Mapped[str] = mapped_column(String(32), default="planning")  # planning, released, in_progress, picked, sorted, completed, cancelled
    carrier_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cutoff_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    picked_units: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))

    picker_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[List["PickWaveOrder"]] = relationship("PickWaveOrder", back_populates="wave", cascade="all, delete-orphan")
    lines: Mapped[List["PickWaveLine"]] = relationship("PickWaveLine", back_populates="wave", cascade="all, delete-orphan")


class PickWaveOrder(Base):
    """Link table associating customer sales orders to a specific pick wave."""
    __tablename__ = "pick_wave_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    wave_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pick_waves.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)

    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="assigned")  # assigned, picking, picked, sorted, packed
    tote_barcode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # Put-wall consolidation tote

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    wave: Mapped["PickWave"] = relationship("PickWave", back_populates="orders")


class PickWaveLine(Base):
    """Consolidated SKU pick lines with serpentine warehouse routing sequence."""
    __tablename__ = "pick_wave_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    wave_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pick_waves.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), default="UNIT")
    location_code: Mapped[str] = mapped_column(String(64), nullable=False)  # Aisle-Bay-Shelf e.g. A-01-02
    pick_sequence: Mapped[int] = mapped_column(Integer, default=1)  # Serpentine routing order
    batch_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    required_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    picked_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, picking, picked, short

    wave: Mapped["PickWave"] = relationship("PickWave", back_populates="lines")


# ==============================================================================
# 2. CUSTOMER B2B SELF-SERVICE PORTAL
# ==============================================================================

class CustomerPortalUser(Base):
    """Client account granting external B2B access linked to a Party (Customer)."""
    __tablename__ = "customer_portal_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_rma: Mapped[bool] = mapped_column(Boolean, default=True)
    can_download_invoices: Mapped[bool] = mapped_column(Boolean, default=True)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CustomerRmaTicket(Base):
    """B2B Customer self-service Return Material Authorization request."""
    __tablename__ = "customer_rma_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ticket_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # RMA-2026-001
    customer_party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    return_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), default="UNIT")

    reason_category: Mapped[str] = mapped_column(String(64), nullable=False)  # damaged_in_transit, defective_workmanship, wrong_item, excess_delivery
    customer_notes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="submitted")  # submitted, under_review, approved, rejected, goods_received, credited

    carrier_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    return_tracking_awb: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ==============================================================================
# 3. IN-PROCESS QUALITY CONTROL (IPQC) & CERTIFICATE OF ANALYSIS (CoA)
# ==============================================================================

class IpqcInspection(Base):
    """In-Process Quality inspection gating production stages mid-assembly."""
    __tablename__ = "ipqc_inspections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    inspection_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # IPQC-2026-001
    production_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)  # SMT Solder, High-Voltage Torque, Potting, Calibration
    sample_size: Mapped[int] = mapped_column(Integer, default=5)
    inspected_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1.0000"))
    passed_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1.0000"))
    failed_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"))

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, passed, failed, conditionally_approved
    parameters_checked: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    # e.g.: [{"parameter": "Torque", "spec": "12.5 Nm +/- 0.5", "measured": 12.4, "status": "PASS", "uom": "Nm"}]

    non_conformance_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrective_action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    inspector_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CertificateOfAnalysis(Base):
    """Certified chemical / physical test report for finished goods lot release."""
    __tablename__ = "certificates_of_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    coa_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # COA-2026-001
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    production_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id"), nullable=True)

    mfg_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lot_size_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), default="UNIT")

    test_standards: Mapped[str] = mapped_column(String(128), default="ISO 9001 / IEC 62133")
    specifications_grid: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    # e.g.: [{"test_name": "Tensile Strength", "method": "ASTM D638", "specification": ">= 45 MPa", "result": "48.2 MPa", "decision": "PASS"}]

    tested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    authorized_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ==============================================================================
# 4. APPROVED VENDOR LIST (AVL) GOVERNANCE
# ==============================================================================

class ApprovedVendor(Base):
    """Vendor qualification & category-specific approval whitelist for purchasing."""
    __tablename__ = "approved_vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True)

    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # electronics, hardware, chemicals, packaging
    status: Mapped[str] = mapped_column(String(32), default="approved")  # approved, conditional_trial, disqualified
    audit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0 to 100 audit score
    qualification_date: Mapped[date] = mapped_column(Date, default=date.today)
    re_evaluation_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    max_po_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)  # Rate ceiling per order
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auditor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_avl_vendor_product", "tenant_id", "vendor_party_id", "product_id"),
    )


class VendorComplianceCert(Base):
    """Quality and statutory accreditation certificates (ISO 9001, IATF 16949, RoHS)."""
    __tablename__ = "vendor_compliance_certs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id"), nullable=False, index=True)

    cert_type: Mapped[str] = mapped_column(String(32), nullable=False)  # ISO_9001, IATF_16949, ISO_14001, ROHS, REACH, GMP, CUSTOM
    certificate_number: Mapped[str] = mapped_column(String(64), nullable=False)
    issuing_body: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. TUV SUD, Bureau Veritas, SGS
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), default="valid")  # valid, expired, pending_audit
    document_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
