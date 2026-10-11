"""Add subcontracting and job-work tables with Indian GST Rule 55 compliance.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    # 1. subcontract_orders
    op.create_table(
        "subcontract_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_no", sa.String(32), nullable=False),
        sa.Column("vendor_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("business_entity_id", UUID(as_uuid=True), sa.ForeignKey("business_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fg_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fg_sku", sa.String(64), nullable=False),
        sa.Column("fg_name", sa.String(255), nullable=False),
        sa.Column("bom_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("received_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("service_rate", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("service_sac_code", sa.String(16), nullable=False, server_default="9988"),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_no", name="subcontract_orders_tenant_order_no_uniq"),
        sa.CheckConstraint(
            "status in ('draft','confirmed','dispatched','partially_received','completed','cancelled')",
            name="subcontract_orders_status_check",
        ),
    )
    op.create_index("subcontract_orders_tenant_status_idx", "subcontract_orders", ["tenant_id", "status"])
    op.create_index("subcontract_orders_vendor_idx", "subcontract_orders", ["tenant_id", "vendor_party_id"])

    # 2. subcontract_order_lines
    op.create_table(
        "subcontract_order_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hsn_code", sa.String(16), nullable=True),
        sa.Column("required_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("dispatched_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("consumed_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("scrap_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(16), nullable=False, server_default="unit"),
        sa.Column("estimated_unit_cost", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("subcontract_order_lines_order_idx", "subcontract_order_lines", ["order_id"])
    op.create_index("subcontract_order_lines_product_idx", "subcontract_order_lines", ["tenant_id", "product_id"])

    # 3. subcontract_challans
    op.create_table(
        "subcontract_challans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challan_no", sa.String(32), nullable=False),
        sa.Column("challan_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statutory_due_date", sa.Date(), nullable=False),
        sa.Column("source_warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consignor_name", sa.String(255), nullable=False),
        sa.Column("consignor_gstin", sa.String(32), nullable=False),
        sa.Column("consignor_address", sa.Text(), nullable=False),
        sa.Column("consignor_state", sa.String(64), nullable=False),
        sa.Column("consignor_state_code", sa.String(8), nullable=False),
        sa.Column("consignee_name", sa.String(255), nullable=False),
        sa.Column("consignee_gstin", sa.String(32), nullable=False, server_default="URP"),
        sa.Column("consignee_address", sa.Text(), nullable=False),
        sa.Column("consignee_state", sa.String(64), nullable=False),
        sa.Column("consignee_state_code", sa.String(8), nullable=False),
        sa.Column("place_of_supply", sa.String(64), nullable=False),
        sa.Column("transport_mode", sa.String(32), nullable=False, server_default="Road"),
        sa.Column("vehicle_no", sa.String(32), nullable=True),
        sa.Column("transporter_name", sa.String(255), nullable=True),
        sa.Column("eway_bill_no", sa.String(32), nullable=True),
        sa.Column("nature_of_processing", sa.String(255), nullable=False, server_default="Job-Work / Processing on inputs"),
        sa.Column("statutory_declaration", sa.Text(), nullable=False),
        sa.Column("total_taxable_value", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_cgst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_sgst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_igst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_challan_value", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="dispatched"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "challan_no", name="subcontract_challans_tenant_no_uniq"),
        sa.CheckConstraint("status in ('draft','dispatched','delivered','reconciled')", name="subcontract_challans_status_check"),
    )
    op.create_index("subcontract_challans_tenant_due_idx", "subcontract_challans", ["tenant_id", "statutory_due_date"])
    op.create_index("subcontract_challans_order_idx", "subcontract_challans", ["order_id"])

    # 4. subcontract_challan_items
    op.create_table(
        "subcontract_challan_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("challan_id", UUID(as_uuid=True), sa.ForeignKey("subcontract_challans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("hsn_code", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="unit"),
        sa.Column("taxable_rate", sa.Numeric(20, 4), nullable=False),
        sa.Column("taxable_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("gst_rate_pct", sa.Numeric(6, 2), nullable=False, server_default="18.0"),
        sa.Column("cgst_rate", sa.Numeric(6, 2), nullable=False, server_default="9.0"),
        sa.Column("cgst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("sgst_rate", sa.Numeric(6, 2), nullable=False, server_default="9.0"),
        sa.Column("sgst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("igst_rate", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("igst_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )
    op.create_index("subcontract_challan_items_challan_idx", "subcontract_challan_items", ["challan_id"])
    op.create_index("subcontract_challan_items_product_idx", "subcontract_challan_items", ["tenant_id", "product_id"])

    # 5. subcontract_receipts
    op.create_table(
        "subcontract_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_no", sa.String(32), nullable=False),
        sa.Column("receipt_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("received_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("accepted_qty", sa.Numeric(20, 4), nullable=False),
        sa.Column("rejected_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("consumed_raw_material_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("actual_scrap_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("allowable_scrap_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("scrap_variance_qty", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("scrap_variance_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("vendor_challan_ref", sa.String(64), nullable=True),
        sa.Column("vendor_invoice_no", sa.String(64), nullable=True),
        sa.Column("service_charges", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("qc_status", sa.String(32), nullable=False, server_default="approved"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "receipt_no", name="subcontract_receipts_tenant_no_uniq"),
        sa.CheckConstraint("qc_status in ('pending','approved','rejected')", name="subcontract_receipts_qc_check"),
    )
    op.create_index("subcontract_receipts_order_idx", "subcontract_receipts", ["order_id"])
    op.create_index("subcontract_receipts_tenant_idx", "subcontract_receipts", ["tenant_id", "created_at"])


def downgrade():
    op.drop_table("subcontract_receipts")
    op.drop_table("subcontract_challan_items")
    op.drop_table("subcontract_challans")
    op.drop_table("subcontract_order_lines")
    op.drop_table("subcontract_orders")
