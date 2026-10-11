"""Models for Long-Term Roadmap:
1. Demand Forecasting & S&OP
2. Vendor Self-Service Collaboration Portal
3. Container & Freight Consolidation TMS
4. Advanced Traceability & Genealogy / Recall Triage
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


# ==============================================================================
# 1. Demand Forecasting & S&OP
# ==============================================================================
class DemandForecastScenario(Base):
    __tablename__ = "demand_forecast_scenarios"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    planning_horizon_months: Mapped[int] = mapped_column(sa.Integer, default=6, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), default="draft", nullable=False)  # draft, under_review, locked
    locked_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    locked_by_user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    lines = relationship("ForecastPeriodLine", back_populates="scenario", cascade="all, delete-orphan")


class ForecastPeriodLine(Base):
    __tablename__ = "forecast_period_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("demand_forecast_scenarios.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    period_date: Mapped[date] = mapped_column(sa.Date, nullable=False)  # 1st day of target month
    statistical_forecast_qty: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0, nullable=False)
    sales_override_qty: Mapped[Optional[float]] = mapped_column(sa.Numeric(12, 2), nullable=True)
    marketing_uplift_qty: Mapped[Optional[float]] = mapped_column(sa.Numeric(12, 2), nullable=True)
    consensus_forecast_qty: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0, nullable=False)
    champion_algorithm: Mapped[str] = mapped_column(sa.String(64), default="Holt-Winters", nullable=False)
    mape_pct: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    scenario = relationship("DemandForecastScenario", back_populates="lines")


# ==============================================================================
# 2. Vendor Self-Service Collaboration Portal
# ==============================================================================
class VendorPortalUser(Base):
    __tablename__ = "vendor_portal_users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    vendor_party_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(32), default="order_manager", nullable=False)  # admin, order_manager, shipping_clerk, finance
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


class AdvanceShippingNotice(Base):
    __tablename__ = "advance_shipping_notices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    asn_number: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    po_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=False)
    vendor_party_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False)
    carrier_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column(sa.String(128), nullable=True)
    vehicle_number: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    dispatch_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    estimated_delivery_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), default="submitted", nullable=False)  # draft, submitted, in_transit, received_dock, cancelled
    package_count: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    total_weight_kg: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    lines = relationship("AsnLine", back_populates="asn", cascade="all, delete-orphan")


class AsnLine(Base):
    __tablename__ = "asn_lines"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    asn_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("advance_shipping_notices.id", ondelete="CASCADE"), nullable=False)
    po_line_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    shipped_qty: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    vendor_batch_number: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    mfg_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    asn = relationship("AdvanceShippingNotice", back_populates="lines")


# ==============================================================================
# 3. Container & Freight Consolidation TMS
# ==============================================================================
class ContainerShipment(Base):
    __tablename__ = "container_shipments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    container_number: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # ISO e.g. MSCU-7482910
    booking_reference: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    carrier_party_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=True)
    container_type: Mapped[str] = mapped_column(sa.String(16), default="40HC", nullable=False)  # 20GP, 40GP, 40HC, 45HC
    origin_port: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    destination_port: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    vessel_name: Mapped[Optional[str]] = mapped_column(sa.String(128), nullable=True)
    voyage_number: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    etd: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    eta: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    discharge_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    port_free_days: Mapped[int] = mapped_column(sa.Integer, default=5, nullable=False)
    detention_free_days: Mapped[int] = mapped_column(sa.Integer, default=14, nullable=False)
    gate_out_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    empty_return_date: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), default="planning", nullable=False)  # planning, stuffing, sailed, arrived_port, customs_cleared, delivered
    total_volume_cbm: Mapped[float] = mapped_column(sa.Numeric(8, 3), default=0, nullable=False)
    total_weight_kg: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=0, nullable=False)
    volume_utilization_pct: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=0, nullable=False)
    weight_utilization_pct: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=0, nullable=False)
    contracted_freight_cost: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0, nullable=False)
    audited_freight_cost: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    items = relationship("ContainerItem", back_populates="container", cascade="all, delete-orphan")
    milestones = relationship("FreightMilestone", back_populates="container", cascade="all, delete-orphan")


class ContainerItem(Base):
    __tablename__ = "container_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    container_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("container_shipments.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(sa.Numeric(10, 2), nullable=False)
    unit_cbm: Mapped[float] = mapped_column(sa.Numeric(8, 4), default=0.01, nullable=False)
    unit_weight_kg: Mapped[float] = mapped_column(sa.Numeric(8, 2), default=1.0, nullable=False)
    package_type: Mapped[str] = mapped_column(sa.String(32), default="Carton", nullable=False)
    hsn_code: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    container = relationship("ContainerShipment", back_populates="items")


class FreightMilestone(Base):
    __tablename__ = "freight_milestones"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    container_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("container_shipments.id", ondelete="CASCADE"), nullable=False)
    milestone_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    milestone_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    location: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    container = relationship("ContainerShipment", back_populates="milestones")


# ==============================================================================
# 4. Advanced Traceability & Genealogy / Recall Triage
# ==============================================================================
class LotGenealogyEdge(Base):
    __tablename__ = "lot_genealogy_edges"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    parent_lot_number: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)  # Output finished/sub-assembly lot
    child_lot_number: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)   # Consumed component lot
    parent_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    child_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    work_order_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    consumed_qty: Mapped[float] = mapped_column(sa.Numeric(12, 3), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


class RecallEvent(Base):
    __tablename__ = "recall_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    case_number: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(32), default="critical", nullable=False)  # critical, high, medium, low
    root_cause_lot_number: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    root_cause_product_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), default="investigating", nullable=False)  # investigating, quarantined, advisory_issued, resolved
    quarantined_stock_qty: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0, nullable=False)
    affected_customers_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    initiated_by_user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    affected_items = relationship("RecallAffectedItem", back_populates="recall", cascade="all, delete-orphan")


class RecallAffectedItem(Base):
    __tablename__ = "recall_affected_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    recall_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("recall_events.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # inventory_stock, shipped_order
    lot_number: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    customer_party_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_quarantined: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    disposition: Mapped[str] = mapped_column(sa.String(32), default="pending", nullable=False)  # pending, quarantined, scrapped, returned, reworked

    recall = relationship("RecallEvent", back_populates="affected_items")
