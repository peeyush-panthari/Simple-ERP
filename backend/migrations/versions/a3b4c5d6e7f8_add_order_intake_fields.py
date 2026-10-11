"""add order intake fields: inverter details, accessories, branding, logistics cost split

Revision ID: a3b4c5d6e7f8
Revises: 42c112101b36
Create Date: 2026-09-08 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = '42c112101b36'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('inverter_details', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('accessories_required', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('branding', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('logistics_cost_borne_by', sa.String(), nullable=True))
        batch_op.create_check_constraint(
            'orders_logistics_cost_borne_by_check',
            "logistics_cost_borne_by is null or logistics_cost_borne_by in ('Simple','Client','Equally shared')",
        )


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_logistics_cost_borne_by_check', type_='check')
        batch_op.drop_column('logistics_cost_borne_by')
        batch_op.drop_column('branding')
        batch_op.drop_column('accessories_required')
        batch_op.drop_column('inverter_details')
