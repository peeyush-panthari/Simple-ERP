"""orders: drop the 'draft' status - an order is confirmed on creation

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-09 00:00:00.000000

app/routes/orders.py::_create_order now sets status='confirmed' directly
(and applies the same credit-limit check confirm_order used to run on its
own) instead of leaving new orders at 'draft' for a separate manual confirm
step. Existing 'draft' rows are backfilled to 'confirmed' so they still pass
the tightened CHECK constraint; this is a one-way reclassification - a
downgrade restores the constraint but cannot tell a backfilled row apart
from one that was genuinely confirmed the old way, so it leaves the data as
'confirmed' rather than guessing.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE orders SET status = 'confirmed' WHERE status = 'draft'")
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_status_check', type_='check')
        batch_op.create_check_constraint(
            'orders_status_check',
            "status in ('confirmed','allocated','picked','shipped','invoiced','closed','cancelled')",
        )


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_status_check', type_='check')
        batch_op.create_check_constraint(
            'orders_status_check',
            "status in ('draft','confirmed','allocated','picked','shipped','invoiced','closed','cancelled')",
        )
