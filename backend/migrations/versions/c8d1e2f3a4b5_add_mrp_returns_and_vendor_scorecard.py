"""Add MRP runs, MRP planned orders, RMAs, RTVs, and Vendor Scorecards.

Revision ID: c8d1e2f3a4b5
Revises: b5d9f2a6c8e1
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c8d1e2f3a4b5"
down_revision = "b5d9f2a6c8e1"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    # 1. mrp_runs
    op.create_table(
        "mrp_runs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("warehouse_id", UUID, nullable=True),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="completed"),
        sa.Column("total_skus_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_orders_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "number", name="mrp_runs_tenant_number_uniq"),
        sa.CheckConstraint("status in ('draft', 'completed', 'cancelled')", name="mrp_runs_status_check"),
    )
    op.create_index("mrp_runs_tenant_created_idx", "mrp_runs", ["tenant_id", "created_at"])

    # 2. mrp_planned_orders
    op.create_table(
        "mrp_planned_orders",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("mrp_run_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("warehouse_id", UUID, nullable=False),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("uom", sa.String(), nullable=False),
        sa.Column("suggested_order_date", sa.Date(), nullable=False),
        sa.Column("required_by_date", sa.Date(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_unit_cost", sa.Numeric(20, 6), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="suggested"),
        sa.Column("source_demand", sa.String(), nullable=False),
        sa.Column("released_reference_type", sa.String(), nullable=True),
        sa.Column("released_reference_id", UUID, nullable=True),
        sa.Column("released_reference_number", sa.String(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["mrp_run_id"], ["mrp_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("order_type in ('purchase', 'production')", name="mrp_planned_orders_type_check"),
        sa.CheckConstraint("status in ('suggested', 'released', 'rejected')", name="mrp_planned_orders_status_check"),
        sa.CheckConstraint("quantity > 0", name="mrp_planned_orders_quantity_check"),
    )
    op.create_index("mrp_planned_orders_run_idx", "mrp_planned_orders", ["mrp_run_id"])
    op.create_index("mrp_planned_orders_tenant_status_idx", "mrp_planned_orders", ["tenant_id", "status"])
    op.create_index("mrp_planned_orders_tenant_product_idx", "mrp_planned_orders", ["tenant_id", "product_id"])

    # 3. rmas
    op.create_table(
        "rmas",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("order_id", UUID, nullable=True),
        sa.Column("order_number", sa.String(), nullable=True),
        sa.Column("warehouse_id", UUID, nullable=False),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("return_reason", sa.String(), nullable=False),
        sa.Column("carrier", sa.String(), nullable=True),
        sa.Column("tracking_number", sa.String(), nullable=True),
        sa.Column("credit_note_id", UUID, nullable=True),
        sa.Column("credit_note_number", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("authorized_by", sa.String(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inspected_by", sa.String(), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["customer_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["credit_note_id"], ["credit_notes.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "number", name="rmas_tenant_number_uniq"),
        sa.CheckConstraint(
            "status in ('draft', 'authorized', 'goods_received', 'inspected', 'completed', 'cancelled')",
            name="rmas_status_check",
        ),
    )
    op.create_index("rmas_tenant_status_idx", "rmas", ["tenant_id", "status"])
    op.create_index("rmas_tenant_customer_idx", "rmas", ["tenant_id", "customer_id"])
    op.create_index("rmas_tenant_order_idx", "rmas", ["tenant_id", "order_id"])

    # 4. rma_lines
    op.create_table(
        "rma_lines",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("rma_id", UUID, nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("order_line_id", UUID, nullable=True),
        sa.Column("authorized_qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("received_qty", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("restocked_qty", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("scrapped_qty", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("repaired_qty", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(), nullable=True),
        sa.Column("inspection_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("disposition_notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["rma_id"], ["rmas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_line_id"], ["order_lines.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("rma_id", "line_no", name="rma_lines_rma_line_no_uniq"),
        sa.CheckConstraint("authorized_qty > 0", name="rma_lines_authorized_qty_check"),
        sa.CheckConstraint("received_qty >= 0", name="rma_lines_received_qty_check"),
        sa.CheckConstraint("restocked_qty >= 0", name="rma_lines_restocked_qty_check"),
        sa.CheckConstraint("scrapped_qty >= 0", name="rma_lines_scrapped_qty_check"),
        sa.CheckConstraint("repaired_qty >= 0", name="rma_lines_repaired_qty_check"),
    )
    op.create_index("rma_lines_rma_idx", "rma_lines", ["rma_id"])

    # 5. rtvs
    op.create_table(
        "rtvs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("vendor_id", UUID, nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("po_id", UUID, nullable=True),
        sa.Column("po_number", sa.String(), nullable=True),
        sa.Column("grn_id", UUID, nullable=True),
        sa.Column("grn_number", sa.String(), nullable=True),
        sa.Column("warehouse_id", UUID, nullable=False),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("return_reason", sa.String(), nullable=False),
        sa.Column("transporter", sa.String(), nullable=True),
        sa.Column("vehicle_no", sa.String(), nullable=True),
        sa.Column("lr_no", sa.String(), nullable=True),
        sa.Column("debit_note_id", UUID, nullable=True),
        sa.Column("debit_note_number", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vendor_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["grn_id"], ["grns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["debit_note_id"], ["credit_notes.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "number", name="rtvs_tenant_number_uniq"),
        sa.CheckConstraint(
            "status in ('draft', 'approved', 'dispatched', 'completed', 'cancelled')",
            name="rtvs_status_check",
        ),
    )
    op.create_index("rtvs_tenant_status_idx", "rtvs", ["tenant_id", "status"])
    op.create_index("rtvs_tenant_vendor_idx", "rtvs", ["tenant_id", "vendor_id"])
    op.create_index("rtvs_tenant_po_idx", "rtvs", ["tenant_id", "po_id"])

    # 6. rtv_lines
    op.create_table(
        "rtv_lines",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("rtv_id", UUID, nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("uom", sa.String(), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("batch_no", sa.String(), nullable=True),
        sa.Column("rejection_code", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["rtv_id"], ["rtvs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("rtv_id", "line_no", name="rtv_lines_rtv_line_no_uniq"),
        sa.CheckConstraint("quantity > 0", name="rtv_lines_quantity_check"),
    )
    op.create_index("rtv_lines_rtv_idx", "rtv_lines", ["rtv_id"])

    # 7. vendor_scorecards
    op.create_table(
        "vendor_scorecards",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("vendor_id", UUID, nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("otif_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("price_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("grade", sa.String(), nullable=False),
        sa.Column("total_pos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_grns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lines_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lines_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lines_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_lead_time_days", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vendor_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "vendor_id", "period", name="vendor_scorecards_vendor_period_uniq"),
        sa.CheckConstraint("overall_score >= 0 and overall_score <= 100", name="vendor_scorecards_overall_check"),
        sa.CheckConstraint("grade in ('A', 'B', 'C', 'D')", name="vendor_scorecards_grade_check"),
    )
    op.create_index("vendor_scorecards_tenant_vendor_idx", "vendor_scorecards", ["tenant_id", "vendor_id"])
    op.create_index("vendor_scorecards_tenant_grade_idx", "vendor_scorecards", ["tenant_id", "grade"])


def downgrade():
    op.drop_table("vendor_scorecards")
    op.drop_table("rtv_lines")
    op.drop_table("rtvs")
    op.drop_table("rma_lines")
    op.drop_table("rmas")
    op.drop_table("mrp_planned_orders")
    op.drop_table("mrp_runs")
