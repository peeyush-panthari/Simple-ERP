"""drop exchange_rates table

Revision ID: f9a0b1c2d3e4
Revises: e4f5a6b7c8d9
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9a0b1c2d3e4'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('exchange_rates')


def downgrade():
    op.create_table('exchange_rates',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('from_currency', sa.String(), nullable=False),
    sa.Column('to_currency', sa.String(), nullable=False),
    sa.Column('rate_date', sa.Date(), nullable=False),
    sa.Column('rate', sa.Numeric(precision=20, scale=6), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('rate > 0', name='exchange_rates_rate_check'),
    sa.PrimaryKeyConstraint('tenant_id', 'from_currency', 'to_currency', 'rate_date')
    )
