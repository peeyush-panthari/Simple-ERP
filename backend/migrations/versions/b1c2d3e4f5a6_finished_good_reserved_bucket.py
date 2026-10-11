"""Real 'reserved' bucket for Finished Goods allocation

Revision ID: b1c2d3e4f5a6
Revises: a9b0c1d2e3f4
Create Date: 2026-09-09 00:00:00.000005

Allocating FG stock used to be a soft hold: a Reservation row was created but
stock never left the `available` bucket. Now allocation posts a real ledger
movement (available -> reserved), so:
  - stock_ledger.bucket gains 'reserved'.
  - finished_good_items.status gains 'reserved'/'partially_reserved' (the
    per-unit reservation state) and 'shipped' (terminal, once shipped_qty
    covers the whole item) - condition values (quarantine/damaged/expired)
    still take priority, see app/services/finished_good_status.py.
  - finished_good_items gets shipped_qty, mirroring inventory_items'
    consumed_qty - the row is kept after shipping, not deleted, preserving
    FG-ID/QR traceability.
  - reservations gets allocation_legs (JSONB), the exact per-batch/location
    breakdown a multi-batch FEFO reservation drew from, so release/issue can
    reverse each leg precisely instead of collapsing to one (possibly wrong)
    batch/location key.

No backfill needed anywhere: no existing row can hold any of these new
values, and allocation_legs is nullable (existing open reservations replay
their single batch_no/location_id/quantity as a fallback).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a9b0c1d2e3f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stock_ledger', schema=None) as batch_op:
        batch_op.drop_constraint('stock_ledger_bucket_check', type_='check')
        batch_op.create_check_constraint(
            'stock_ledger_bucket_check',
            "bucket in ('available','quarantine','damaged','in_transit','expired','reserved')",
        )

    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.drop_constraint('finished_good_items_status_check', type_='check')
        batch_op.create_check_constraint(
            'finished_good_items_status_check',
            "status in ('available','quarantine','damaged','expired','reserved','partially_reserved','shipped')",
        )
        batch_op.add_column(sa.Column('shipped_qty', sa.Numeric(precision=20, scale=6), server_default='0', nullable=False))
        batch_op.create_check_constraint('finished_good_items_shipped_qty_check', 'shipped_qty >= 0')

    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allocation_legs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.drop_column('allocation_legs')

    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.drop_constraint('finished_good_items_shipped_qty_check', type_='check')
        batch_op.drop_column('shipped_qty')
        batch_op.drop_constraint('finished_good_items_status_check', type_='check')
        batch_op.create_check_constraint(
            'finished_good_items_status_check',
            "status in ('available','quarantine','damaged','expired')",
        )

    with op.batch_alter_table('stock_ledger', schema=None) as batch_op:
        batch_op.drop_constraint('stock_ledger_bucket_check', type_='check')
        batch_op.create_check_constraint(
            'stock_ledger_bucket_check',
            "bucket in ('available','quarantine','damaged','in_transit','expired')",
        )
