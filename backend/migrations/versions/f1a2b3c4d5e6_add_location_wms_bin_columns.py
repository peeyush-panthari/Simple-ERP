"""Add WMS bin operational columns to locations.

Revision ID: f1a2b3c4d5e6
Revises: e9d1c2b3a4f5
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e9d1c2b3a4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("locations", sa.Column("max_weight_kg", sa.Numeric(10, 2), nullable=True))
    op.add_column("locations", sa.Column("max_volume_cbm", sa.Numeric(10, 3), nullable=True))
    op.add_column("locations", sa.Column("velocity_class", sa.String(8), nullable=True))
    op.add_column("locations", sa.Column("barcode", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("locations", "barcode")
    op.drop_column("locations", "velocity_class")
    op.drop_column("locations", "max_volume_cbm")
    op.drop_column("locations", "max_weight_kg")
