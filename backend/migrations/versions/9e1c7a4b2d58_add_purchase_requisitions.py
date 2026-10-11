"""Add purchase_requisitions + lines (Procurement > Purchase requisitions: employee requests to the Purchase department).

Revision ID: 9e1c7a4b2d58
Revises: c1d2e3f4a5b6
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9e1c7a4b2d58"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchase_requisitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_name", sa.String(), nullable=False),
        sa.Column("requester_email", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("warehouse_code", sa.String(), nullable=True),
        sa.Column("required_by", sa.Date(), nullable=True),
        sa.Column("justification", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_name", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(), nullable=True),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purchase_order_number", sa.String(), nullable=True),
        sa.Column("cancelled_reason", sa.String(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('draft','submitted','approved','rejected','ordered','cancelled')", name="purchase_requisitions_status_check"),
        sa.CheckConstraint("priority in ('low','normal','high','urgent')", name="purchase_requisitions_priority_check"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="purchase_requisitions_tenant_number_uniq"),
    )
    op.create_index("purchase_requisitions_tenant_status_idx", "purchase_requisitions", ["tenant_id", "status", "created_at"])
    op.create_index("purchase_requisitions_requester_idx", "purchase_requisitions", ["tenant_id", "requester_id"])
    op.create_table(
        "purchase_requisition_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requisition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("item_name", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("uom", sa.String(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="purchase_requisition_lines_quantity_check"),
        sa.ForeignKeyConstraint(["requisition_id"], ["purchase_requisitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requisition_id", "line_no", name="purchase_requisition_lines_line_no_uniq"),
    )
    op.create_index("purchase_requisition_lines_req_idx", "purchase_requisition_lines", ["requisition_id"])


def downgrade():
    op.drop_table("purchase_requisition_lines")
    op.drop_table("purchase_requisitions")
