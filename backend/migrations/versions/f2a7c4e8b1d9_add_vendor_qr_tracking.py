"""add grns.has_vendor_qr + inventory_items.vendor_qr_enabled/vendor_inventory_id - the "Vendor's QR and ID" checkbox on Receive Goods and the per-item vendor-supplied identifier it unlocks

Revision ID: f2a7c4e8b1d9
Revises: e6f3b9d1a4c7
Create Date: 2026-09-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a7c4e8b1d9'
down_revision = 'e6f3b9d1a4c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_vendor_qr', sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vendor_qr_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('vendor_inventory_id', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_column('vendor_inventory_id')
        batch_op.drop_column('vendor_qr_enabled')

    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.drop_column('has_vendor_qr')
