"""Add multi-echelon DRP tables.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    # 1. distribution_lanes
    op.create_table(
        "distribution_lanes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dest_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transit_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("shipping_mode", sa.String(32), nullable=False, server_default="Road"),
        sa.Column("carrier_name", sa.String(128), nullable=True),
        sa.Column("cost_per_kg", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_warehouse_id", "dest_warehouse_id", name="distribution_lanes_pair_uniq"),
        sa.CheckConstraint("source_warehouse_id <> dest_warehouse_id", name="distribution_lanes_distinct_wh"),
        sa.CheckConstraint("transit_days >= 0", name="distribution_lanes_transit_days_ck"),
    )
    op.create_index("distribution_lanes_tenant_idx", "distribution_lanes", ["tenant_id", "is_active"])

    # 2. drp_replenishment_policies
    op.create_table(
        "drp_replenishment_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dest_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("policy_type", sa.String(32), nullable=False, server_default="min_max"),
        sa.Column("safety_stock_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("reorder_point_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("min_order_qty", sa.Numeric(20, 4), nullable=False, server_default="1"),
        sa.Column("order_multiple", sa.Numeric(20, 4), nullable=False, server_default="1"),
        sa.Column("target_stock_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "dest_warehouse_id", "product_id", name="drp_policies_wh_prod_uniq"),
        sa.CheckConstraint(
            "policy_type in ('min_max','lot_for_lot','order_up_to','fixed_order_qty')",
            name="drp_policies_type_ck",
        ),
    )
    op.create_index("drp_policies_wh_idx", "drp_replenishment_policies", ["tenant_id", "dest_warehouse_id"])

    # 3. planned_transfer_orders
    op.create_table(
        "planned_transfer_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pto_no", sa.String(32), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("source_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dest_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="unit"),
        sa.Column("suggested_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("firm_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("required_delivery_date", sa.Date(), nullable=False),
        sa.Column("planned_dispatch_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="suggested"),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("released_transfer_id", UUID(as_uuid=True), sa.ForeignKey("transfers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("released_transfer_number", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "pto_no", name="planned_transfers_tenant_no_uniq"),
        sa.CheckConstraint(
            "status in ('suggested','approved','released','cancelled')",
            name="planned_transfers_status_ck",
        ),
    )
    op.create_index("planned_transfers_tenant_status_idx", "planned_transfer_orders", ["tenant_id", "status"])
    op.create_index("planned_transfers_dest_wh_idx", "planned_transfer_orders", ["tenant_id", "dest_warehouse_id"])
    op.create_index("planned_transfers_run_idx", "planned_transfer_orders", ["tenant_id", "run_id"])


def downgrade():
    op.drop_table("planned_transfer_orders")
    op.drop_table("drp_replenishment_policies")
    op.drop_table("distribution_lanes")
