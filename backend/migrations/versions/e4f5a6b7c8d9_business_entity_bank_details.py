"""Business entities carry their own bank details, for printing on POs/invoices

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-10 00:00:00.000008
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('business_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bank_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('bank_branch', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('bank_account_number', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('bank_ifsc', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('business_entities', schema=None) as batch_op:
        batch_op.drop_column('bank_ifsc')
        batch_op.drop_column('bank_account_number')
        batch_op.drop_column('bank_branch')
        batch_op.drop_column('bank_name')
