"""Orders carry no warehouse of their own any more

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-10 00:00:00.000006

orders.warehouse_id used to be auto-assigned at creation (pick_fulfilling_
warehouse(), a best-guess scoring function with no UI) and was wrong in a
deeper way than just being invisible: the manual allocation endpoint
(POST /orders/:id/allocate-items) was stamping Reservation.warehouse_id from
this order-level value even when the actual FinishedGoodItem(s) picked sat
in a different warehouse entirely.

Removed: an order now carries no warehouse at all. "Which warehouse" is only
ever known once (and where) specific stock is actually allocated to a line,
via that line's own Reservation.warehouse_id - already a real, independent
column. A single line's allocation is still exactly one warehouse (enforced
in allocate_order_items), but different lines on the same order can now
legitimately end up allocated from different warehouses.

Column kept (not dropped) and made nullable rather than removed - existing
orders keep whatever warehouse they were created with; only new orders go
warehouse-less. No backfill: nothing needs to change on existing rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('warehouse_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('warehouse_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
