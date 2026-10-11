"""production: per-item consumption tracking for additional (beyond-BOM) components

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-09 00:00:00.000002

Supports editing a posted run's "Additional raw materials (beyond BOM)":
production_consumption is a per-(run, product) aggregate with no record of
which InventoryItem rows a draw actually came from, so an existing
additional component can never be safely un-consumed (InventoryItem.
consumed_run_id is a last-write-wins tag, not a history). This table is
written only by the new add-additional-component endpoint going forward -
production_consumption rows from the original create flow have no rows
here, which is exactly how the app tells a removable component (added via
edit) from a non-removable one (added at creation).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('production_consumption_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('production_consumption_id', sa.UUID(), nullable=False),
    sa.Column('inventory_item_id', sa.UUID(), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=20, scale=6), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['production_consumption_id'], ['production_consumption.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('production_consumption_items', schema=None) as batch_op:
        batch_op.create_index('production_consumption_items_consumption_idx', ['production_consumption_id'], unique=False)


def downgrade():
    with op.batch_alter_table('production_consumption_items', schema=None) as batch_op:
        batch_op.drop_index('production_consumption_items_consumption_idx')

    op.drop_table('production_consumption_items')
