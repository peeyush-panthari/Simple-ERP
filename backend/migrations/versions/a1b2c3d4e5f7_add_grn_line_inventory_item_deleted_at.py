"""add deleted_at to grn_lines and inventory_items (soft-delete for pre-post GRN edits)

Revision ID: a1b2c3d4e5f7
Revises: 324bea26ee4b
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '324bea26ee4b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grn_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
    with op.batch_alter_table('grn_lines', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
