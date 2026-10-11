"""drop products.standard_cost/tax_code/shelf_life_days

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('products_standard_cost_check', type_='check')
        batch_op.drop_constraint('products_expiry_shelf_life_check', type_='check')
        batch_op.drop_column('standard_cost')
        batch_op.drop_column('tax_code')
        batch_op.drop_column('shelf_life_days')


def downgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shelf_life_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('tax_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('standard_cost', sa.Numeric(20, 6), nullable=False, server_default='0'))
        batch_op.create_check_constraint('products_expiry_shelf_life_check', 'not expiry_tracked or shelf_life_days is not null')
        batch_op.create_check_constraint('products_standard_cost_check', 'standard_cost >= 0')
