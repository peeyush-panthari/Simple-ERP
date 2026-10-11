"""production_runs: drop unit_cost/currency - dead columns, never populated

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-09 00:00:00.000003

ProductionRun.unit_cost was meant to be consumed-cost / quantity, but every
draw's own unit_cost has always been hardcoded to None (no per-product cost
source since standard_cost was removed from Product), so the accumulator
feeding it was always zero and unit_cost was always None. currency existed
only to accompany it. Both were exposed as the Production list's "Unit
Cost"/"Value" columns, which showed Rs.0 for every run - removed at the UI,
then the API (_to_run_api), and now here at the schema.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('production_runs', schema=None) as batch_op:
        batch_op.drop_column('unit_cost')
        batch_op.drop_column('currency')


def downgrade():
    with op.batch_alter_table('production_runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unit_cost', sa.Numeric(precision=20, scale=6), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(), nullable=True))
