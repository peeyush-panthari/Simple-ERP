"""add inventory_items.transfer_id - links a specific piece/lot to the in-flight transfer moving it

Revision ID: fd8b28b3e22a
Revises: 5abdf7a9979a
Create Date: 2026-09-14 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'fd8b28b3e22a'
down_revision = '5abdf7a9979a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transfer_id', postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.create_foreign_key('inventory_items_transfer_id_fkey', 'transfers', ['transfer_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index('inventory_items_transfer_idx', ['transfer_id'])


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index('inventory_items_transfer_idx')
        batch_op.drop_constraint('inventory_items_transfer_id_fkey', type_='foreignkey')
        batch_op.drop_column('transfer_id')
