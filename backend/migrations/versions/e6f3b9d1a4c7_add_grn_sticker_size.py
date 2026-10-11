"""add grns.sticker_size_id/sticker_size_name - the Sticker Size template chosen at receipt, used to size the printed QR/label for this GRN's items

Revision ID: e6f3b9d1a4c7
Revises: d4e9a2c7f1b5
Create Date: 2026-09-16 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f3b9d1a4c7'
down_revision = 'd4e9a2c7f1b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sticker_size_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('sticker_size_name', sa.String(), nullable=True))
        batch_op.create_foreign_key('grns_sticker_size_id_fkey', 'sticker_sizes', ['sticker_size_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.drop_constraint('grns_sticker_size_id_fkey', type_='foreignkey')
        batch_op.drop_column('sticker_size_name')
        batch_op.drop_column('sticker_size_id')
