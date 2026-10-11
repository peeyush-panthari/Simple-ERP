"""finished_good_items + finished_good_allocations - per-unit tracking for production output

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-09 00:00:00.000004

Raw material gets individual InventoryItem tracking from GRN receiving;
finished goods had none - production posted one aggregate stock-ledger line
for a whole run's output. finished_good_items is the finished-good mirror
of InventoryItem (one row per physical unit for UOM=UNIT products, one lot
row otherwise), sourced from a production run instead of a GRN line.
finished_good_allocations is the finished-good mirror of
production_consumption_items - it records exactly which item(s) fund a
Reservation, so a manual Finished Good Allocation pick can be released
precisely later.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a9b0c1d2e3f4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('finished_good_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('inventory_id', sa.String(), nullable=False),
    sa.Column('production_run_id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('sku', sa.String(), nullable=False),
    sa.Column('warehouse_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=20, scale=6), nullable=False),
    sa.Column('uom', sa.String(), nullable=True),
    sa.Column('received_date', sa.Date(), nullable=True),
    sa.Column('batch_no', sa.String(), nullable=True),
    sa.Column('allocated_qty', sa.Numeric(precision=20, scale=6), nullable=False),
    sa.Column('allocated_order_id', sa.UUID(), nullable=True),
    sa.Column('allocated_order_number', sa.String(), nullable=True),
    sa.Column('location_id', sa.UUID(), nullable=True),
    sa.Column('location_code', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status in ('available','quarantine','damaged','expired')", name='finished_good_items_status_check'),
    sa.CheckConstraint("kind in ('piece','lot')", name='finished_good_items_kind_check'),
    sa.ForeignKeyConstraint(['production_run_id'], ['production_runs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'inventory_id', name='finished_good_items_tenant_inventory_id_uniq'),
    )
    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.create_index('finished_good_items_run_idx', ['production_run_id'], unique=False)
        batch_op.create_index('finished_good_items_tenant_status_idx', ['tenant_id', 'status'], unique=False)
        batch_op.create_index('finished_good_items_fifo_idx', ['tenant_id', 'product_id', 'warehouse_id', 'received_date'], unique=False)
        batch_op.create_index('finished_good_items_tenant_order_idx', ['tenant_id', 'allocated_order_id'], unique=False)

    op.create_table('finished_good_allocations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('reservation_id', sa.UUID(), nullable=False),
    sa.Column('finished_good_item_id', sa.UUID(), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=20, scale=6), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['finished_good_item_id'], ['finished_good_items.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('finished_good_allocations', schema=None) as batch_op:
        batch_op.create_index('finished_good_allocations_reservation_idx', ['reservation_id'], unique=False)


def downgrade():
    with op.batch_alter_table('finished_good_allocations', schema=None) as batch_op:
        batch_op.drop_index('finished_good_allocations_reservation_idx')
    op.drop_table('finished_good_allocations')

    with op.batch_alter_table('finished_good_items', schema=None) as batch_op:
        batch_op.drop_index('finished_good_items_tenant_order_idx')
        batch_op.drop_index('finished_good_items_fifo_idx')
        batch_op.drop_index('finished_good_items_tenant_status_idx')
        batch_op.drop_index('finished_good_items_run_idx')
    op.drop_table('finished_good_items')
