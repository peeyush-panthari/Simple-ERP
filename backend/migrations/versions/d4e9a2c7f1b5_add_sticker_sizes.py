"""add sticker_sizes - saved label/sticker print templates (page size, sticker dimensions, grid layout, margins, gaps) for Configuration > Sticker Size

Revision ID: d4e9a2c7f1b5
Revises: c3d8f1a6e2b9
Create Date: 2026-09-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e9a2c7f1b5'
down_revision = 'c3d8f1a6e2b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sticker_sizes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('page_size', sa.String(), nullable=False),
    sa.Column('page_width_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('page_height_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('sticker_width_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('sticker_height_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('columns', sa.Integer(), nullable=False),
    sa.Column('rows', sa.Integer(), nullable=False),
    sa.Column('margin_left_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('margin_right_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('margin_top_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('margin_bottom_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('gap_horizontal_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('gap_vertical_mm', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('status', sa.String(), nullable=False, server_default='active'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("page_size in ('A4','A5','Letter','Custom')", name='sticker_sizes_page_size_check'),
    sa.CheckConstraint("status in ('active','inactive')", name='sticker_sizes_status_check'),
    sa.CheckConstraint("columns > 0", name='sticker_sizes_columns_check'),
    sa.CheckConstraint("rows > 0", name='sticker_sizes_rows_check'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sticker_sizes', schema=None) as batch_op:
        batch_op.create_index('sticker_sizes_tenant_idx', ['tenant_id'], unique=False)
        batch_op.create_unique_constraint('sticker_sizes_tenant_name_uniq', ['tenant_id', 'name'])


def downgrade():
    with op.batch_alter_table('sticker_sizes', schema=None) as batch_op:
        batch_op.drop_constraint('sticker_sizes_tenant_name_uniq', type_='unique')
        batch_op.drop_index('sticker_sizes_tenant_idx')

    op.drop_table('sticker_sizes')
