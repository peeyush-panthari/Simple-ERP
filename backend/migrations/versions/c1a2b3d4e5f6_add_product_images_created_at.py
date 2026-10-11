"""add product_images.created_at

Revision ID: c1a2b3d4e5f6
Revises: ba87b5b1c639
Create Date: 2026-09-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c1a2b3d4e5f6'
down_revision = 'ba87b5b1c639'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_images', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))


def downgrade():
    with op.batch_alter_table('product_images', schema=None) as batch_op:
        batch_op.drop_column('created_at')
