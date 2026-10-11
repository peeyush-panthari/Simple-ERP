"""add party_addresses.label

Revision ID: d2e3f4a5b6c7
Revises: 5535c38cf582
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = '5535c38cf582'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('party_addresses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('label', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('party_addresses', schema=None) as batch_op:
        batch_op.drop_column('label')
