"""After the PO: vendor acknowledgement, vendor documents and dispatch documentation.

Revision ID: b5d9f2a6c8e1
Revises: a4c8e1f2b7d3
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b5d9f2a6c8e1"
down_revision = "a4c8e1f2b7d3"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column("purchase_orders", sa.Column("ack_status", sa.String(), nullable=False, server_default="pending"))
    for name, typ in (("ack_date", sa.Date()), ("ack_ref", sa.String()), ("ack_confirmed_date", sa.Date()), ("ack_notes", sa.String()), ("ack_recorded_by", sa.String()), ("ack_recorded_at", sa.DateTime(timezone=True))):
        op.add_column("purchase_orders", sa.Column(name, typ, nullable=True))
    op.create_check_constraint("purchase_orders_ack_status_check", "purchase_orders", "ack_status in ('pending','acknowledged','acknowledged_with_changes','declined')")

    op.create_table(
        "po_dispatches",
        sa.Column("id", UUID, nullable=False), sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("po_id", UUID, nullable=False),
        sa.Column("number", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("dispatch_date", sa.Date(), nullable=False), sa.Column("expected_arrival", sa.Date(), nullable=True),
        sa.Column("transporter", sa.String(), nullable=True), sa.Column("vehicle_no", sa.String(), nullable=True), sa.Column("lr_no", sa.String(), nullable=True),
        sa.Column("driver_name", sa.String(), nullable=True), sa.Column("driver_phone", sa.String(), nullable=True),
        sa.Column("packages", sa.Integer(), nullable=True), sa.Column("gross_weight_kg", sa.Numeric(20, 6), nullable=True),
        sa.Column("invoice_no", sa.String(), nullable=True), sa.Column("invoice_date", sa.Date(), nullable=True), sa.Column("invoice_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("packing_list_no", sa.String(), nullable=True),
        sa.Column("delivery_challan_no", sa.String(), nullable=True), sa.Column("delivery_challan_date", sa.Date(), nullable=True),
        sa.Column("eway_bill_no", sa.String(), nullable=True), sa.Column("eway_bill_valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancelled_reason", sa.String(), nullable=True), sa.Column("recorded_by_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('in_transit','delivered','cancelled')", name="po_dispatches_status_check"),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "number", name="po_dispatches_tenant_number_uniq"),
    )
    op.create_index("po_dispatches_po_idx", "po_dispatches", ["po_id"])

    op.create_table(
        "po_dispatch_lines",
        sa.Column("id", UUID, nullable=False), sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dispatch_id", UUID, nullable=False), sa.Column("po_line_id", UUID, nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.CheckConstraint("quantity > 0", name="po_dispatch_lines_quantity_check"),
        sa.ForeignKeyConstraint(["dispatch_id"], ["po_dispatches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_line_id"], ["po_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispatch_id", "po_line_id", name="po_dispatch_lines_uniq"),
    )

    op.create_table(
        "po_documents",
        sa.Column("id", UUID, nullable=False), sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("po_id", UUID, nullable=False), sa.Column("dispatch_id", UUID, nullable=True), sa.Column("document_id", UUID, nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False), sa.Column("reference_no", sa.String(), nullable=True), sa.Column("description", sa.String(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False), sa.Column("content_type", sa.String(), nullable=False), sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", UUID, nullable=True), sa.Column("uploaded_by_name", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dispatch_id"], ["po_dispatches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("po_documents_po_idx", "po_documents", ["po_id"])


def downgrade():
    op.drop_table("po_documents")
    op.drop_table("po_dispatch_lines")
    op.drop_table("po_dispatches")
    op.drop_constraint("purchase_orders_ack_status_check", "purchase_orders", type_="check")
    for c in ("ack_recorded_at", "ack_recorded_by", "ack_notes", "ack_confirmed_date", "ack_ref", "ack_date", "ack_status"):
        op.drop_column("purchase_orders", c)
