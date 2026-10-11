"""Manager approval for purchase requisitions (users.manager_id) + sourcing: RFQs, vendor quotations and awards.

Revision ID: a4c8e1f2b7d3
Revises: 9e1c7a4b2d58
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4c8e1f2b7d3"
down_revision = "9e1c7a4b2d58"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _id_tenant():
    return [sa.Column("id", UUID, nullable=False), sa.Column("tenant_id", UUID, nullable=False)]


def upgrade():
    # ---- who reports to whom
    op.add_column("users", sa.Column("manager_id", UUID, nullable=True))
    op.create_foreign_key("users_manager_id_fkey", "users", "users", ["manager_id"], ["id"], ondelete="SET NULL")
    op.create_index("users_manager_idx", "users", ["tenant_id", "manager_id"])

    # ---- requisition: manager stage, sourcing status
    for col in (("manager_id", UUID), ("manager_name", sa.String()), ("manager_decided_at", sa.DateTime(timezone=True)), ("manager_note", sa.String()), ("rejected_stage", sa.String())):
        op.add_column("purchase_requisitions", sa.Column(col[0], col[1], nullable=True))
    op.drop_constraint("purchase_requisitions_status_check", "purchase_requisitions", type_="check")
    op.create_check_constraint(
        "purchase_requisitions_status_check", "purchase_requisitions",
        "status in ('draft','pending_manager','submitted','approved','sourcing','ordered','rejected','cancelled')",
    )
    op.create_check_constraint("purchase_requisitions_rejected_stage_check", "purchase_requisitions", "rejected_stage is null or rejected_stage in ('manager','purchase')")

    # ---- sourcing
    op.create_table(
        "purchase_rfqs", *_id_tenant(),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requisition_id", UUID, nullable=True),
        sa.Column("requisition_number", sa.String(), nullable=True),
        sa.Column("warehouse_id", UUID, nullable=True),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("terms", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", UUID, nullable=True),
        sa.Column("created_by_name", sa.String(), nullable=True),
        sa.Column("awarded_by_name", sa.String(), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.String(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('open','awarded','ordered','cancelled')", name="purchase_rfqs_status_check"),
        sa.ForeignKeyConstraint(["requisition_id"], ["purchase_requisitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="purchase_rfqs_tenant_number_uniq"),
    )
    op.create_index("purchase_rfqs_tenant_status_idx", "purchase_rfqs", ["tenant_id", "status", "created_at"])
    op.create_index("purchase_rfqs_requisition_idx", "purchase_rfqs", ["requisition_id"])

    op.create_table(
        "purchase_rfq_lines", *_id_tenant(),
        sa.Column("rfq_id", UUID, nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("requisition_line_id", UUID, nullable=True),
        sa.Column("product_id", UUID, nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("item_name", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("uom", sa.String(), nullable=False),
        sa.Column("awarded_vendor_id", UUID, nullable=True),
        sa.Column("award_reason", sa.String(), nullable=True),
        sa.Column("purchase_order_id", UUID, nullable=True),
        sa.Column("purchase_order_number", sa.String(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="purchase_rfq_lines_quantity_check"),
        sa.ForeignKeyConstraint(["rfq_id"], ["purchase_rfqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rfq_id", "line_no", name="purchase_rfq_lines_line_no_uniq"),
    )
    op.create_index("purchase_rfq_lines_rfq_idx", "purchase_rfq_lines", ["rfq_id"])

    op.create_table(
        "purchase_rfq_vendors", *_id_tenant(),
        sa.Column("rfq_id", UUID, nullable=False),
        sa.Column("vendor_id", UUID, nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("vendor_email", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("email_state", sa.String(), nullable=False),
        sa.Column("email_error", sa.String(), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('invited','quoted','declined')", name="purchase_rfq_vendors_status_check"),
        sa.CheckConstraint("email_state in ('not_sent','sent','failed','skipped')", name="purchase_rfq_vendors_email_state_check"),
        sa.ForeignKeyConstraint(["rfq_id"], ["purchase_rfqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="purchase_rfq_vendors_uniq"),
    )

    op.create_table(
        "purchase_quotations", *_id_tenant(),
        sa.Column("rfq_id", UUID, nullable=False),
        sa.Column("vendor_id", UUID, nullable=False),
        sa.Column("vendor_name", sa.String(), nullable=False),
        sa.Column("quote_ref", sa.String(), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("payment_terms", sa.String(), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("charges", sa.Numeric(20, 6), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("recorded_by_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("charges >= 0", name="purchase_quotations_charges_check"),
        sa.ForeignKeyConstraint(["rfq_id"], ["purchase_rfqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="purchase_quotations_rfq_vendor_uniq"),
    )

    op.create_table(
        "purchase_quotation_lines", *_id_tenant(),
        sa.Column("quotation_id", UUID, nullable=False),
        sa.Column("rfq_line_id", UUID, nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("tax_code", sa.String(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.CheckConstraint("unit_price is null or unit_price >= 0", name="purchase_quotation_lines_price_check"),
        sa.ForeignKeyConstraint(["quotation_id"], ["purchase_quotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_line_id"], ["purchase_rfq_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quotation_id", "rfq_line_id", name="purchase_quotation_lines_uniq"),
    )


def downgrade():
    for t in ("purchase_quotation_lines", "purchase_quotations", "purchase_rfq_vendors", "purchase_rfq_lines", "purchase_rfqs"):
        op.drop_table(t)
    op.drop_constraint("purchase_requisitions_rejected_stage_check", "purchase_requisitions", type_="check")
    op.drop_constraint("purchase_requisitions_status_check", "purchase_requisitions", type_="check")
    op.create_check_constraint("purchase_requisitions_status_check", "purchase_requisitions", "status in ('draft','submitted','approved','rejected','ordered','cancelled')")
    for c in ("rejected_stage", "manager_note", "manager_decided_at", "manager_name", "manager_id"):
        op.drop_column("purchase_requisitions", c)
    op.drop_index("users_manager_idx", table_name="users")
    op.drop_constraint("users_manager_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "manager_id")
