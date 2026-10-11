"""rename product_categories.name/allowed_product_types

Revision ID: e5f6a7b8c9d0
Revises: d2e3f4a5b6c7
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.alter_column('name', new_column_name='product_category')
        batch_op.alter_column('allowed_product_types', new_column_name='product_types')


def downgrade():
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.alter_column('product_category', new_column_name='name')
        batch_op.alter_column('product_types', new_column_name='allowed_product_types')
