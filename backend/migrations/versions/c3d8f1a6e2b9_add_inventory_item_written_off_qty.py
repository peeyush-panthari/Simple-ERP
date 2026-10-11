"""add inventory_items.written_off_qty - tracks cumulative quantity written off a specific piece/lot via Post Adjustment, separate from consumed_qty (production) and rejected_qty (QC)

Revision ID: c3d8f1a6e2b9
Revises: a1c2e9f4b7d3
Create Date: 2026-09-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d8f1a6e2b9'
down_revision = 'a1c2e9f4b7d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('written_off_qty', sa.Numeric(20, 6), nullable=False, server_default='0'))
        batch_op.create_check_constraint('inventory_items_written_off_qty_check', 'written_off_qty >= 0')
        batch_op.create_index('inventory_items_tenant_written_off_idx', ['tenant_id', 'written_off_qty'])


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index('inventory_items_tenant_written_off_idx')
        batch_op.drop_constraint('inventory_items_written_off_qty_check', type_='check')
        batch_op.drop_column('written_off_qty')
