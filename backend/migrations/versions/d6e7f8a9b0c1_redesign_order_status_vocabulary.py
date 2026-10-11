"""orders: redesign the status vocabulary around real allocation/shipment progress

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-09 00:00:00.000001

Drops the 'picked' stage (order and order-line status) entirely - there's no
replacement for it, allocation now goes straight to shipping - and renames
'closed' to 'fulfilled'. Adds 'partially_allocated', 'partially_shipped' and
'partially_fulfilled': app/routes/orders.py::allocate_order/ship_order now
derive full vs. partial from whether every non-cancelled line reached full
allocated_qty/shipped_qty, and 'fulfilled'/'partially_fulfilled' are set
manually via the new /orders/:id/fulfill route.

No 'picked' rows exist in production data as of this migration, but the
backfill below is defensive: a 'picked' order is reclassified to 'allocated'
(the closest real equivalent - stock is reserved) and its 'picked' lines to
'allocated'. This is a one-way reclassification for the same reason the
draft-removal migration's was: a downgrade restores the constraints but
cannot tell a backfilled row apart from one that arrived at 'allocated' the
old way, so it leaves the data as-is rather than guessing.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd6e7f8a9b0c1'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None

_NEW_ORDER_STATUSES = "status in ('confirmed','allocated','partially_allocated','shipped','partially_shipped','invoiced','fulfilled','partially_fulfilled','cancelled')"
_OLD_ORDER_STATUSES = "status in ('confirmed','allocated','picked','shipped','invoiced','closed','cancelled')"
_NEW_LINE_STATUSES = "status in ('open','allocated','shipped','cancelled')"
_OLD_LINE_STATUSES = "status in ('open','allocated','picked','shipped','cancelled')"


def upgrade():
    # The backfill targets ('fulfilled', the new 'allocated' meaning for old
    # 'picked' rows) aren't legal under the *old* constraint, so it has to
    # come off before the data moves - not after, unlike a plain narrowing
    # migration.
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_status_check', type_='check')
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.drop_constraint('order_lines_status_check', type_='check')

    op.execute("UPDATE orders SET status = 'allocated' WHERE status = 'picked'")
    op.execute("UPDATE orders SET status = 'fulfilled' WHERE status = 'closed'")
    op.execute("UPDATE order_lines SET status = 'allocated' WHERE status = 'picked'")

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_check_constraint('orders_status_check', _NEW_ORDER_STATUSES)
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.create_check_constraint('order_lines_status_check', _NEW_LINE_STATUSES)


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_status_check', type_='check')
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.drop_constraint('order_lines_status_check', type_='check')

    op.execute("UPDATE orders SET status = 'allocated' WHERE status in ('partially_allocated')")
    op.execute("UPDATE orders SET status = 'shipped' WHERE status in ('partially_shipped')")
    op.execute("UPDATE orders SET status = 'closed' WHERE status in ('fulfilled','partially_fulfilled')")

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_check_constraint('orders_status_check', _OLD_ORDER_STATUSES)
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.create_check_constraint('order_lines_status_check', _OLD_LINE_STATUSES)
