"""add planned production status and order packing_status

Revision ID: 96781e073e68
Revises: d51f5ca3098d
Create Date: 2026-09-13 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96781e073e68'
down_revision = 'd51f5ca3098d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('production_runs', schema=None) as batch_op:
        batch_op.drop_constraint('production_runs_status_check', type_='check')
        batch_op.create_check_constraint('production_runs_status_check', "status in ('planned','posted','reversed')")

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('packing_status', sa.String(), server_default='pending_packing', nullable=False))
        batch_op.create_check_constraint('orders_packing_status_check', "packing_status in ('pending_packing','packed')")


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('orders_packing_status_check', type_='check')
        batch_op.drop_column('packing_status')

    with op.batch_alter_table('production_runs', schema=None) as batch_op:
        batch_op.drop_constraint('production_runs_status_check', type_='check')
        batch_op.create_check_constraint('production_runs_status_check', "status in ('posted','reversed')")
