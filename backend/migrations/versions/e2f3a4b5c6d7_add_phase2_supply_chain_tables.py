"""Add Phase 2 Supply Chain ERP tables:
- Wave & batch picking optimization (pick_waves, pick_wave_orders, pick_wave_lines)
- Customer B2B self-service portal (customer_portal_users, customer_rma_tickets)
- In-process quality control & CoA (ipqc_inspections, certificates_of_analysis)
- Approved vendor list governance (approved_vendors, vendor_compliance_certs)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # 1. Wave & Batch Picking Engine
    # -------------------------------------------------------------------------
    op.create_table(
        "pick_waves",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("wave_number", sa.String(32), unique=True, nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("wave_type", sa.String(32), nullable=False, server_default="carrier_cutoff"),
        sa.Column("status", sa.String(32), nullable=False, server_default="planning"),
        sa.Column("carrier_name", sa.String(64), nullable=True),
        sa.Column("cutoff_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_units", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("picked_units", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("picker_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("pick_waves_tenant_status_idx", "pick_waves", ["tenant_id", "status"])

    op.create_table(
        "pick_wave_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("wave_id", UUID(as_uuid=True), sa.ForeignKey("pick_waves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column("customer_name", sa.String(128), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="assigned"),
        sa.Column("tote_barcode", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("pick_wave_orders_wave_idx", "pick_wave_orders", ["wave_id"])

    op.create_table(
        "pick_wave_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("wave_id", UUID(as_uuid=True), sa.ForeignKey("pick_waves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="UNIT"),
        sa.Column("location_code", sa.String(64), nullable=False),
        sa.Column("pick_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("batch_no", sa.String(64), nullable=True),
        sa.Column("required_qty", sa.Numeric(12, 4), nullable=False),
        sa.Column("picked_qty", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.create_index("pick_wave_lines_wave_seq_idx", "pick_wave_lines", ["wave_id", "pick_sequence"])

    # -------------------------------------------------------------------------
    # 2. Customer B2B Self-Service Portal
    # -------------------------------------------------------------------------
    op.create_table(
        "customer_portal_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("email", sa.String(128), unique=True, nullable=False),
        sa.Column("full_name", sa.String(128), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("can_create_rma", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("can_download_invoices", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("customer_portal_users_party_idx", "customer_portal_users", ["tenant_id", "customer_party_id"])

    op.create_table(
        "customer_rma_tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.String(32), unique=True, nullable=False),
        sa.Column("customer_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("order_number", sa.String(64), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("return_qty", sa.Numeric(12, 4), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="UNIT"),
        sa.Column("reason_category", sa.String(64), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("carrier_name", sa.String(64), nullable=True),
        sa.Column("return_tracking_awb", sa.String(64), nullable=True),
        sa.Column("reviewed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("customer_rma_tickets_party_status_idx", "customer_rma_tickets", ["tenant_id", "customer_party_id", "status"])

    # -------------------------------------------------------------------------
    # 3. In-Process Quality Control (IPQC) & Certificate of Analysis (CoA)
    # -------------------------------------------------------------------------
    op.create_table(
        "ipqc_inspections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_number", sa.String(32), unique=True, nullable=False),
        sa.Column("production_run_id", UUID(as_uuid=True), sa.ForeignKey("production_runs.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("stage_name", sa.String(64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("inspected_qty", sa.Numeric(12, 4), nullable=False, server_default="1.00"),
        sa.Column("passed_qty", sa.Numeric(12, 4), nullable=False, server_default="1.00"),
        sa.Column("failed_qty", sa.Numeric(12, 4), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("parameters_checked", JSONB, nullable=False, server_default="[]"),
        sa.Column("non_conformance_reason", sa.Text(), nullable=True),
        sa.Column("corrective_action_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("inspector_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ipqc_inspections_run_status_idx", "ipqc_inspections", ["tenant_id", "production_run_id", "status"])

    op.create_table(
        "certificates_of_analysis",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("coa_number", sa.String(32), unique=True, nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("batch_no", sa.String(64), nullable=False),
        sa.Column("production_run_id", UUID(as_uuid=True), sa.ForeignKey("production_runs.id"), nullable=True),
        sa.Column("mfg_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("lot_size_qty", sa.Numeric(12, 4), nullable=False),
        sa.Column("uom", sa.String(16), nullable=False, server_default="UNIT"),
        sa.Column("test_standards", sa.String(128), nullable=False, server_default="ISO 9001 / IEC 62133"),
        sa.Column("specifications_grid", JSONB, nullable=False, server_default="[]"),
        sa.Column("tested_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("authorized_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("coa_batch_idx", "certificates_of_analysis", ["tenant_id", "batch_no"])

    # -------------------------------------------------------------------------
    # 4. Approved Vendor List (AVL) Governance
    # -------------------------------------------------------------------------
    op.create_table(
        "approved_vendors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="approved"),
        sa.Column("audit_score", sa.Integer(), nullable=True),
        sa.Column("qualification_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("re_evaluation_due_date", sa.Date(), nullable=True),
        sa.Column("max_po_limit", sa.Numeric(16, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("auditor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_avl_vendor_product", "approved_vendors", ["tenant_id", "vendor_party_id", "product_id"])

    op.create_table(
        "vendor_compliance_certs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("cert_type", sa.String(32), nullable=False),
        sa.Column("certificate_number", sa.String(64), nullable=False),
        sa.Column("issuing_body", sa.String(128), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="valid"),
        sa.Column("document_url", sa.String(255), nullable=True),
        sa.Column("verified_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vendor_certs_expiry", "vendor_compliance_certs", ["tenant_id", "expiry_date"])


def downgrade():
    op.drop_table("vendor_compliance_certs")
    op.drop_table("approved_vendors")
    op.drop_table("certificates_of_analysis")
    op.drop_table("ipqc_inspections")
    op.drop_table("customer_rma_tickets")
    op.drop_table("customer_portal_users")
    op.drop_table("pick_wave_lines")
    op.drop_table("pick_wave_orders")
    op.drop_table("pick_waves")
