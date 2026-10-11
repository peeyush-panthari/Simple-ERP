"""SQLAlchemy models for Phase 3 Supply Chain Advanced Intelligence modules:
1. Work Center Finite Capacity Planning & RCCP (WorkCenter, WorkCenterSchedule)
2. Multi-Carrier Shipping Engine & Live AWB Tracking (CarrierRateCard, CarrierShipment)
3. Supply Chain Control Tower Dashboard (ScKpiSnapshot)
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class WorkCenter(Base):
    """Manufacturing Work Center representing machines, cells, or assembly stations."""
    __tablename__ = "work_centers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="work_centers_code_uniq"),
        Index("work_centers_tenant_status_idx", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False, default="Assembly")
    warehouse_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    daily_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("16.00"))
    efficiency_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.8500"))
    hourly_machine_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("750.00"))
    hourly_labor_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("350.00"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # active, maintenance, inactive
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    schedules = relationship("WorkCenterSchedule", back_populates="work_center", cascade="all, delete-orphan")


class WorkCenterSchedule(Base):
    """Daily/shift job assignments for rough-cut finite capacity planning."""
    __tablename__ = "work_center_schedules"
    __table_args__ = (
        Index("wc_schedules_date_idx", "tenant_id", "work_center_id", "schedule_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    work_center_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_centers.id", ondelete="CASCADE"), nullable=False)
    production_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id", ondelete="SET NULL"), nullable=True)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False, default="day")  # day, evening, night
    required_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("4.00"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")  # scheduled, in_progress, completed, overloaded
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    work_center = relationship("WorkCenter", back_populates="schedules")


class CarrierRateCard(Base):
    """Multi-carrier shipping rates for algorithmic rate shopping."""
    __tablename__ = "carrier_rate_cards"
    __table_args__ = (
        UniqueConstraint("tenant_id", "carrier_code", "service_type", name="carrier_rates_code_type_uniq"),
        Index("carrier_rates_tenant_idx", "tenant_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    carrier_code: Mapped[str] = mapped_column(String(32), nullable=False)  # DELHIVERY, BLUEDART, FEDEX, SHIPROCKET, DTDC
    carrier_name: Mapped[str] = mapped_column(String(64), nullable=False)
    service_type: Mapped[str] = mapped_column(String(32), nullable=False)  # standard_surface, express_air, priority
    base_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("120.00"))
    per_kg_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("45.00"))
    cod_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.0200"))
    sla_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CarrierShipment(Base):
    """Outbound parcel shipment with live Airway Bill (AWB) and tracking milestones."""
    __tablename__ = "carrier_shipments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "shipment_number", name="carrier_shipments_number_uniq"),
        Index("carrier_shipments_awb_idx", "tenant_id", "awb_number"),
        Index("carrier_shipments_status_idx", "tenant_id", "current_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shipment_number: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    carrier_code: Mapped[str] = mapped_column(String(32), nullable=False)
    service_type: Mapped[str] = mapped_column(String(32), nullable=False, default="standard_surface")
    awb_number: Mapped[str] = mapped_column(String(64), nullable=False)
    package_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("2.50"))
    length_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True, default=Decimal("30.00"))
    width_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True, default=Decimal("20.00"))
    height_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True, default=Decimal("15.00"))
    freight_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("250.00"))
    recipient_name: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_pincode: Mapped[str] = mapped_column(String(12), nullable=False)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False, default="booked")
    # booked, pickup_scheduled, in_transit, out_for_delivery, delivered, rto
    estimated_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tracking_events: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ScKpiSnapshot(Base):
    """Historical and live daily snapshots for the Supply Chain Control Tower."""
    __tablename__ = "sc_kpi_snapshots"
    __table_args__ = (
        Index("sc_kpi_snapshots_date_idx", "tenant_id", "snapshot_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    otif_percentage: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("94.50"))
    doh_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("38.5"))
    dso_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("42.0"))
    dio_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("38.5"))
    dpo_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("45.0"))
    cash_to_cash_days: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=Decimal("35.5"))
    total_inventory_value: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("12500000.00"))
    stockout_risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
