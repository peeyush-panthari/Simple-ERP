"""Add Phase 3 Supply Chain Advanced Intelligence tables:
- Work Center Finite Capacity Planning & RCCP (work_centers, work_center_schedules)
- Multi-Carrier Shipping Engine & Live AWB Tracking (carrier_rate_cards, carrier_shipments)
- Supply Chain Control Tower (sc_kpi_snapshots)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # 1. Work Centers (Manufacturing Capacity Stations)
    # -------------------------------------------------------------------------
    op.create_table(
        "work_centers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("department", sa.String(64), nullable=False, server_default="Assembly"),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("daily_capacity_hours", sa.Numeric(8, 2), nullable=False, server_default="16.00"),
        sa.Column("efficiency_factor", sa.Numeric(5, 4), nullable=False, server_default="0.8500"),
        sa.Column("hourly_machine_rate", sa.Numeric(12, 2), nullable=False, server_default="750.00"),
        sa.Column("hourly_labor_rate", sa.Numeric(12, 2), nullable=False, server_default="350.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="work_centers_code_uniq"),
    )
    op.create_index("work_centers_tenant_status_idx", "work_centers", ["tenant_id", "status"])

    # -------------------------------------------------------------------------
    # 2. Work Center Daily / Shift Schedules (Finite Capacity & Overload Matrix)
    # -------------------------------------------------------------------------
    op.create_table(
        "work_center_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("work_center_id", UUID(as_uuid=True), sa.ForeignKey("work_centers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("production_run_id", UUID(as_uuid=True), sa.ForeignKey("production_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_name", sa.String(128), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(16), nullable=False, server_default="day"),
        sa.Column("required_hours", sa.Numeric(8, 2), nullable=False, server_default="4.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("wc_schedules_date_idx", "work_center_schedules", ["tenant_id", "work_center_id", "schedule_date"])

    # -------------------------------------------------------------------------
    # 3. Carrier Rate Cards (Rate Shopping Engine)
    # -------------------------------------------------------------------------
    op.create_table(
        "carrier_rate_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("carrier_code", sa.String(32), nullable=False),
        sa.Column("carrier_name", sa.String(64), nullable=False),
        sa.Column("service_type", sa.String(32), nullable=False),
        sa.Column("base_rate", sa.Numeric(12, 2), nullable=False, server_default="120.00"),
        sa.Column("per_kg_rate", sa.Numeric(12, 2), nullable=False, server_default="45.00"),
        sa.Column("cod_fee_pct", sa.Numeric(5, 4), nullable=False, server_default="0.0200"),
        sa.Column("sla_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "carrier_code", "service_type", name="carrier_rates_code_type_uniq"),
    )
    op.create_index("carrier_rates_tenant_idx", "carrier_rate_cards", ["tenant_id", "is_active"])

    # -------------------------------------------------------------------------
    # 4. Carrier Shipments & Live AWB Tracking
    # -------------------------------------------------------------------------
    op.create_table(
        "carrier_shipments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_number", sa.String(64), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("carrier_code", sa.String(32), nullable=False),
        sa.Column("service_type", sa.String(32), nullable=False, server_default="standard_surface"),
        sa.Column("awb_number", sa.String(64), nullable=False),
        sa.Column("package_weight_kg", sa.Numeric(8, 2), nullable=False, server_default="2.50"),
        sa.Column("length_cm", sa.Numeric(8, 2), nullable=True, server_default="30.00"),
        sa.Column("width_cm", sa.Numeric(8, 2), nullable=True, server_default="20.00"),
        sa.Column("height_cm", sa.Numeric(8, 2), nullable=True, server_default="15.00"),
        sa.Column("freight_charge", sa.Numeric(12, 2), nullable=False, server_default="250.00"),
        sa.Column("recipient_name", sa.String(128), nullable=False),
        sa.Column("destination_city", sa.String(64), nullable=False),
        sa.Column("destination_pincode", sa.String(12), nullable=False),
        sa.Column("current_status", sa.String(32), nullable=False, server_default="booked"),
        sa.Column("estimated_delivery_date", sa.Date(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracking_events", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "shipment_number", name="carrier_shipments_number_uniq"),
    )
    op.create_index("carrier_shipments_awb_idx", "carrier_shipments", ["tenant_id", "awb_number"])
    op.create_index("carrier_shipments_status_idx", "carrier_shipments", ["tenant_id", "current_status"])

    # -------------------------------------------------------------------------
    # 5. Supply Chain Control Tower Snapshots
    # -------------------------------------------------------------------------
    op.create_table(
        "sc_kpi_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("otif_percentage", sa.Numeric(6, 2), nullable=False, server_default="94.50"),
        sa.Column("doh_days", sa.Numeric(6, 1), nullable=False, server_default="38.5"),
        sa.Column("dso_days", sa.Numeric(6, 1), nullable=False, server_default="42.0"),
        sa.Column("dio_days", sa.Numeric(6, 1), nullable=False, server_default="38.5"),
        sa.Column("dpo_days", sa.Numeric(6, 1), nullable=False, server_default="45.0"),
        sa.Column("cash_to_cash_days", sa.Numeric(6, 1), nullable=False, server_default="35.5"),
        sa.Column("total_inventory_value", sa.Numeric(16, 2), nullable=False, server_default="12500000.00"),
        sa.Column("stockout_risk_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("sc_kpi_snapshots_date_idx", "sc_kpi_snapshots", ["tenant_id", "snapshot_date"])


def downgrade():
    op.drop_table("sc_kpi_snapshots")
    op.drop_table("carrier_shipments")
    op.drop_table("carrier_rate_cards")
    op.drop_table("work_center_schedules")
    op.drop_table("work_centers")
