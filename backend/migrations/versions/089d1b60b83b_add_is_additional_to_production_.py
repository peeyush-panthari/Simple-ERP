"""add is_additional to production_consumption

Revision ID: 089d1b60b83b
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04 22:25:25.019353

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '089d1b60b83b'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("production_consumption", sa.Column("is_additional", sa.Boolean(), nullable=False, server_default="false"))


def downgrade():
    op.drop_column("production_consumption", "is_additional")
