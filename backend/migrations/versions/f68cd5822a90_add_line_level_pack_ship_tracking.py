"""add line-level pack/ship tracking (order_lines.packed_qty, reservations.issued_qty)

Revision ID: f68cd5822a90
Revises: 96781e073e68
Create Date: 2026-09-15 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f68cd5822a90'
down_revision = '96781e073e68'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('packed_qty', sa.Numeric(20, 6), server_default='0', nullable=False))
        batch_op.create_check_constraint('order_lines_packed_check', 'packed_qty >= 0 and packed_qty <= allocated_qty')

    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('issued_qty', sa.Numeric(20, 6), server_default='0', nullable=False))
        batch_op.create_check_constraint('reservations_issued_qty_check', 'issued_qty >= 0 and issued_qty <= quantity')


def downgrade():
    with op.batch_alter_table('reservations', schema=None) as batch_op:
        batch_op.drop_constraint('reservations_issued_qty_check', type_='check')
        batch_op.drop_column('issued_qty')

    with op.batch_alter_table('order_lines', schema=None) as batch_op:
        batch_op.drop_constraint('order_lines_packed_check', type_='check')
        batch_op.drop_column('packed_qty')
