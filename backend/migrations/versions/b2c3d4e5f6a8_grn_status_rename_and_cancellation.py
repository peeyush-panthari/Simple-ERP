"""grn status: drop unused 'draft', rename 'inspection' to 'under_qc', add cancellation_reason

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a8'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.drop_constraint('grns_status_check', type_='check')
    op.execute("UPDATE grns SET status = 'under_qc' WHERE status IN ('inspection', 'draft')")
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.create_check_constraint('grns_status_check', "status in ('under_qc','posted','rejected','cancelled')")
        batch_op.alter_column('status', server_default='under_qc')
        batch_op.add_column(sa.Column('cancellation_reason', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.drop_column('cancellation_reason')
        batch_op.alter_column('status', server_default='draft')
        batch_op.drop_constraint('grns_status_check', type_='check')
    op.execute("UPDATE grns SET status = 'inspection' WHERE status = 'under_qc'")
    with op.batch_alter_table('grns', schema=None) as batch_op:
        batch_op.create_check_constraint('grns_status_check', "status in ('draft','inspection','posted','rejected','cancelled')")
