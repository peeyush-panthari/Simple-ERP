"""Add long term roadmap tables:
- Demand forecasting scenarios & period lines
- Vendor portal users & advance shipping notices (ASNs)
- Container shipments, items & freight milestones
- Lot genealogy edges & recall events / affected items

Revision ID: c1b2c3d4e5f6
Revises: b3c4d5e6f7a8
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c1b2c3d4e5f6"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # 1. Demand Forecasting & S&OP
    # -------------------------------------------------------------------------
    op.create_table(
        "demand_forecast_scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planning_horizon_months", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("demand_forecast_scenarios_tenant_idx", "demand_forecast_scenarios", ["tenant_id", "status"])

    op.create_table(
        "forecast_period_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", UUID(as_uuid=True), sa.ForeignKey("demand_forecast_scenarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("statistical_forecast_qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sales_override_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("marketing_uplift_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("consensus_forecast_qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("champion_algorithm", sa.String(64), nullable=False, server_default="Holt-Winters"),
        sa.Column("mape_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scenario_id", "product_id", "period_date", name="forecast_period_lines_scen_prod_date_uniq"),
    )
    op.create_index("forecast_period_lines_tenant_idx", "forecast_period_lines", ["tenant_id", "scenario_id"])

    # -------------------------------------------------------------------------
    # 2. Vendor Portal & ASNs
    # -------------------------------------------------------------------------
    op.create_table(
        "vendor_portal_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="order_manager"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="vendor_portal_users_email_uniq"),
    )
    op.create_index("vendor_portal_users_tenant_party_idx", "vendor_portal_users", ["tenant_id", "vendor_party_id"])

    op.create_table(
        "advance_shipping_notices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("asn_number", sa.String(64), nullable=False),
        sa.Column("po_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("vendor_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("carrier_name", sa.String(128), nullable=False),
        sa.Column("tracking_number", sa.String(128), nullable=True),
        sa.Column("vehicle_number", sa.String(64), nullable=True),
        sa.Column("dispatch_date", sa.Date(), nullable=False),
        sa.Column("estimated_delivery_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("package_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_weight_kg", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "asn_number", name="asns_tenant_number_uniq"),
    )
    op.create_index("advance_shipping_notices_tenant_idx", "advance_shipping_notices", ["tenant_id", "status"])

    op.create_table(
        "asn_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("asn_id", UUID(as_uuid=True), sa.ForeignKey("advance_shipping_notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("po_line_id", UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("shipped_qty", sa.Numeric(12, 2), nullable=False),
        sa.Column("vendor_batch_number", sa.String(64), nullable=False),
        sa.Column("mfg_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("asn_lines_tenant_asn_idx", "asn_lines", ["tenant_id", "asn_id"])

    # -------------------------------------------------------------------------
    # 3. Container & Freight Consolidation TMS
    # -------------------------------------------------------------------------
    op.create_table(
        "container_shipments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("container_number", sa.String(32), nullable=False),
        sa.Column("booking_reference", sa.String(64), nullable=False),
        sa.Column("carrier_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("container_type", sa.String(16), nullable=False, server_default="40HC"),
        sa.Column("origin_port", sa.String(64), nullable=False),
        sa.Column("destination_port", sa.String(64), nullable=False),
        sa.Column("vessel_name", sa.String(128), nullable=True),
        sa.Column("voyage_number", sa.String(64), nullable=True),
        sa.Column("etd", sa.Date(), nullable=True),
        sa.Column("eta", sa.Date(), nullable=True),
        sa.Column("discharge_date", sa.Date(), nullable=True),
        sa.Column("port_free_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("detention_free_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("gate_out_date", sa.Date(), nullable=True),
        sa.Column("empty_return_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="planning"),
        sa.Column("total_volume_cbm", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("total_weight_kg", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("volume_utilization_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("weight_utilization_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("contracted_freight_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("audited_freight_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "container_number", name="container_shipments_tenant_number_uniq"),
    )
    op.create_index("container_shipments_tenant_idx", "container_shipments", ["tenant_id", "status"])

    op.create_table(
        "container_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", UUID(as_uuid=True), sa.ForeignKey("container_shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_cbm", sa.Numeric(8, 4), nullable=False, server_default="0.01"),
        sa.Column("unit_weight_kg", sa.Numeric(8, 2), nullable=False, server_default="1.0"),
        sa.Column("package_type", sa.String(32), nullable=False, server_default="Carton"),
        sa.Column("hsn_code", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("container_items_tenant_idx", "container_items", ["tenant_id", "container_id"])

    op.create_table(
        "freight_milestones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", UUID(as_uuid=True), sa.ForeignKey("container_shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_name", sa.String(64), nullable=False),
        sa.Column("milestone_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("location", sa.String(128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("freight_milestones_tenant_idx", "freight_milestones", ["tenant_id", "container_id"])

    # -------------------------------------------------------------------------
    # 4. Advanced Traceability & Genealogy / Recall Triage
    # -------------------------------------------------------------------------
    op.create_table(
        "lot_genealogy_edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("parent_lot_number", sa.String(64), nullable=False),
        sa.Column("child_lot_number", sa.String(64), nullable=False),
        sa.Column("parent_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("child_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("work_order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("consumed_qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("lot_genealogy_edges_tenant_parent_idx", "lot_genealogy_edges", ["tenant_id", "parent_lot_number"])
    op.create_index("lot_genealogy_edges_tenant_child_idx", "lot_genealogy_edges", ["tenant_id", "child_lot_number"])

    op.create_table(
        "recall_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(64), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="critical"),
        sa.Column("root_cause_lot_number", sa.String(64), nullable=False),
        sa.Column("root_cause_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="investigating"),
        sa.Column("quarantined_stock_qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("affected_customers_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("initiated_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "case_number", name="recall_events_tenant_case_uniq"),
    )
    op.create_index("recall_events_tenant_idx", "recall_events", ["tenant_id", "status"])

    op.create_table(
        "recall_affected_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recall_id", UUID(as_uuid=True), sa.ForeignKey("recall_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("lot_number", sa.String(64), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("customer_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_quarantined", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("disposition", sa.String(32), nullable=False, server_default="pending"),
    )
    op.create_index("recall_affected_items_tenant_recall_idx", "recall_affected_items", ["tenant_id", "recall_id"])


def downgrade():
    op.drop_table("recall_affected_items")
    op.drop_table("recall_events")
    op.drop_table("lot_genealogy_edges")
    op.drop_table("freight_milestones")
    op.drop_table("container_items")
    op.drop_table("container_shipments")
    op.drop_table("asn_lines")
    op.drop_table("advance_shipping_notices")
    op.drop_table("vendor_portal_users")
    op.drop_table("forecast_period_lines")
    op.drop_table("demand_forecast_scenarios")
