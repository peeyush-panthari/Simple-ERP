"""add inventory_items.bucket - tracks which condition bucket (available/quarantine/damaged/expired) a specific piece/lot currently sits in

Revision ID: a1c2e9f4b7d3
Revises: fd8b28b3e22a
Create Date: 2026-09-14 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2e9f4b7d3'
down_revision = 'fd8b28b3e22a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bucket', sa.String(), nullable=False, server_default='available'))
        batch_op.create_check_constraint('inventory_items_bucket_check', "bucket in ('available','quarantine','damaged','expired')")
        batch_op.create_index('inventory_items_bucket_idx', ['bucket'])


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index('inventory_items_bucket_idx')
        batch_op.drop_constraint('inventory_items_bucket_check', type_='check')
        batch_op.drop_column('bucket')
