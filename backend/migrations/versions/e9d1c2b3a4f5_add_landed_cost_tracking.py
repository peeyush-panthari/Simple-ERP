"""Add Landed Cost Vouchers, Receipts, Charges, and Items.

Revision ID: e9d1c2b3a4f5
Revises: c8d1e2f3a4b5
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e9d1c2b3a4f5"
down_revision = "c8d1e2f3a4b5"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    # 1. landed_cost_vouchers
    op.create_table(
        "landed_cost_vouchers",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("voucher_no", sa.String(64), nullable=False),
        sa.Column("posting_date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("currency", sa.String(8), server_default="INR", nullable=False),
        sa.Column("total_charges", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("posted_by", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "voucher_no", name="lcv_tenant_voucher_no_uniq"),
        sa.CheckConstraint("status in ('draft', 'posted', 'cancelled')", name="lcv_status_check"),
    )
    op.create_index("lcv_tenant_status_date_idx", "landed_cost_vouchers", ["tenant_id", "status", "posting_date"])

    # 2. landed_cost_receipts
    op.create_table(
        "landed_cost_receipts",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("voucher_id", UUID, nullable=False),
        sa.Column("grn_id", UUID, nullable=False),
        sa.Column("grn_number", sa.String(64), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=True),
        sa.Column("grand_total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["voucher_id"], ["landed_cost_vouchers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grn_id"], ["grns.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("voucher_id", "grn_id", name="lcv_receipts_voucher_grn_uniq"),
    )
    op.create_index("lcv_receipts_voucher_idx", "landed_cost_receipts", ["voucher_id"])
    op.create_index("lcv_receipts_grn_idx", "landed_cost_receipts", ["grn_id"])

    # 3. landed_cost_charges
    op.create_table(
        "landed_cost_charges",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("voucher_id", UUID, nullable=False),
        sa.Column("charge_type", sa.String(32), server_default="freight", nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("vendor_id", UUID, nullable=True),
        sa.Column("vendor_name", sa.String(), nullable=True),
        sa.Column("invoice_ref", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("apportion_by", sa.String(32), server_default="value", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["voucher_id"], ["landed_cost_vouchers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["parties.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "charge_type in ('freight', 'customs', 'insurance', 'handling', 'demurrage', 'other')",
            name="lcv_charge_type_check",
        ),
        sa.CheckConstraint(
            "apportion_by in ('value', 'weight', 'volume', 'quantity')",
            name="lcv_apportion_by_check",
        ),
        sa.CheckConstraint("amount > 0", name="lcv_charge_amount_pos_check"),
    )
    op.create_index("lcv_charges_voucher_idx", "landed_cost_charges", ["voucher_id"])

    # 4. landed_cost_items
    op.create_table(
        "landed_cost_items",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("voucher_id", UUID, nullable=False),
        sa.Column("grn_id", UUID, nullable=False),
        sa.Column("grn_number", sa.String(64), nullable=False),
        sa.Column("grn_line_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("uom", sa.String(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(10, 3), server_default="1.0", nullable=False),
        sa.Column("volume_cbm", sa.Numeric(10, 4), server_default="0.01", nullable=False),
        sa.Column("base_unit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("base_total_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("allocated_charges", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column("final_unit_cost", sa.Numeric(20, 6), nullable=False),
        sa.Column("cost_variance_pct", sa.Numeric(8, 2), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["voucher_id"], ["landed_cost_vouchers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
    )
    op.create_index("lcv_items_voucher_idx", "landed_cost_items", ["voucher_id"])
    op.create_index("lcv_items_grn_line_idx", "landed_cost_items", ["grn_line_id"])
    op.create_index("lcv_items_product_idx", "landed_cost_items", ["product_id"])


def downgrade():
    op.drop_table("landed_cost_items")
    op.drop_table("landed_cost_charges")
    op.drop_table("landed_cost_receipts")
    op.drop_table("landed_cost_vouchers")
