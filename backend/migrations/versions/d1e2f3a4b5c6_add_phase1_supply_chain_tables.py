"""Add Phase 1 Supply Chain ERP tables:
- Cycle count sessions & item count lines
- Statutory e-way bills with NIC payload
- Blanket purchase orders & rate contract lines
- Mobile RF barcode terminal scan audits

Revision ID: d1e2f3a4b5c6
Revises: c1b2c3d4e5f6
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "d1e2f3a4b5c6"
down_revision = "c1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # 1. Cycle Counting & Perpetual Inventory Audits
    # -------------------------------------------------------------------------
    op.create_table(
        "cycle_count_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_number", sa.String(32), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("counting_type", sa.String(32), nullable=False, server_default="abc_scheduled"),
        sa.Column("target_abc_class", sa.String(8), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("blind_count", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audited_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("total_items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discrepancy_items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_variance_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("cycle_count_sessions_tenant_idx", "cycle_count_sessions", ["tenant_id", "status"])

    op.create_table(
        "cycle_count_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("cycle_count_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("batch_no", sa.String(64), nullable=True),
        sa.Column("system_qty", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("counted_qty", sa.Numeric(12, 4), nullable=True),
        sa.Column("variance_qty", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit_cost", sa.Numeric(16, 4), nullable=False, server_default="0.00"),
        sa.Column("variance_value", sa.Numeric(16, 2), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("recount_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("counter_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("cycle_count_lines_session_idx", "cycle_count_lines", ["session_id", "status"])

    # -------------------------------------------------------------------------
    # 2. Indian Statutory e-Way Bill & GST e-Invoice
    # -------------------------------------------------------------------------
    op.create_table(
        "eway_bills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("challan_id", UUID(as_uuid=True), nullable=True),
        sa.Column("transfer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("document_type", sa.String(32), nullable=False, server_default="INV"),
        sa.Column("eway_bill_number", sa.String(32), nullable=True),
        sa.Column("eway_bill_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supply_type", sa.String(8), nullable=False, server_default="O"),
        sa.Column("sub_supply_type", sa.String(32), nullable=False, server_default="Supply"),
        sa.Column("doc_number", sa.String(64), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("from_gstin", sa.String(15), nullable=False),
        sa.Column("from_pincode", sa.String(6), nullable=False),
        sa.Column("from_state_code", sa.String(4), nullable=False, server_default="27"),
        sa.Column("to_gstin", sa.String(15), nullable=True),
        sa.Column("to_pincode", sa.String(6), nullable=False),
        sa.Column("to_state_code", sa.String(4), nullable=False, server_default="27"),
        sa.Column("total_invoice_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("cgst_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("sgst_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("igst_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("cess_value", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("hsn_code", sa.String(16), nullable=False),
        sa.Column("transporter_id", sa.String(15), nullable=True),
        sa.Column("transporter_name", sa.String(128), nullable=True),
        sa.Column("transport_mode", sa.String(16), nullable=False, server_default="1"),
        sa.Column("vehicle_number", sa.String(32), nullable=True),
        sa.Column("vehicle_type", sa.String(16), nullable=False, server_default="R"),
        sa.Column("lr_rr_number", sa.String(64), nullable=True),
        sa.Column("lr_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="generated"),
        sa.Column("cancel_reason", sa.String(64), nullable=True),
        sa.Column("nic_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("qr_code_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("eway_bills_tenant_idx", "eway_bills", ["tenant_id", "status"])

    # -------------------------------------------------------------------------
    # 3. Blanket Purchase Agreements & Rate Contracts
    # -------------------------------------------------------------------------
    op.create_table(
        "blanket_purchase_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bpa_number", sa.String(32), nullable=False),
        sa.Column("vendor_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
        sa.Column("target_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("released_amount", sa.Numeric(16, 2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("payment_terms", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("blanket_pos_tenant_idx", "blanket_purchase_orders", ["tenant_id", "status"])

    op.create_table(
        "blanket_po_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bpa_id", UUID(as_uuid=True), sa.ForeignKey("blanket_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("agreed_rate", sa.Numeric(16, 4), nullable=False),
        sa.Column("committed_qty", sa.Numeric(12, 4), nullable=False),
        sa.Column("released_qty", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("uom", sa.String(16), nullable=False, server_default="UNIT"),
    )
    op.create_index("blanket_po_lines_bpa_idx", "blanket_po_lines", ["bpa_id"])

    # -------------------------------------------------------------------------
    # 4. Mobile RF Barcode Terminal Scan Audits
    # -------------------------------------------------------------------------
    op.create_table(
        "mobile_scan_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("workflow_type", sa.String(32), nullable=False),
        sa.Column("scanned_barcode", sa.String(128), nullable=False),
        sa.Column("matched_entity_type", sa.String(32), nullable=False),
        sa.Column("matched_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("error_message", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("mobile_scan_audits_tenant_idx", "mobile_scan_audits", ["tenant_id", "workflow_type"])


def downgrade():
    op.drop_table("mobile_scan_audits")
    op.drop_table("blanket_po_lines")
    op.drop_table("blanket_purchase_orders")
    op.drop_table("eway_bills")
    op.drop_table("cycle_count_lines")
    op.drop_table("cycle_count_sessions")
