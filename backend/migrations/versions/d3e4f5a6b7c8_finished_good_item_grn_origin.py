"""FinishedGoodItem can now be sourced from a GRN, not just Production

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-10 00:00:00.000007

A Finished Good can be bought in (PO -> GRN -> QC pass) instead of
manufactured (Production run). Order Allocation only ever picks from
FinishedGoodItem, so GRN-received finished-good stock is now converted into
a real FinishedGoodItem row the moment QC passes (see grn_post.py::
_convert_finished_good_receipts), draining the source InventoryItem the same
way raw-material consumption already does.

production_run_id becomes nullable (a converted item has none) and a new
source_inventory_item_id traces a converted item back to the InventoryItem
it came from. Exactly one of the two is ever set, enforced by a check
constraint. No data migration here - the one-time backfill for already-
existing GRN-received FG stock is application logic (scripts/backfill_fg_grn_
conversion.py), not a schema change.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.alter_column('production_run_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)
        batch_op.add_column(sa.Column('source_inventory_item_id', postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.create_foreign_key(
            'finished_good_items_source_inventory_item_id_fkey',
            'inventory_items', ['source_inventory_item_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_index('finished_good_items_source_item_idx', ['source_inventory_item_id'])
        batch_op.create_check_constraint(
            'finished_good_items_origin_check',
            '(production_run_id is not null) != (source_inventory_item_id is not null)',
        )


def downgrade():
    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.drop_constraint('finished_good_items_origin_check', type_='check')
        batch_op.drop_index('finished_good_items_source_item_idx')
        batch_op.drop_constraint('finished_good_items_source_inventory_item_id_fkey', type_='foreignkey')
        batch_op.drop_column('source_inventory_item_id')
        batch_op.alter_column('production_run_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
