"""add returned_to_vendor/discarded terminal statuses for rejected InventoryItem rows

Revision ID: 5abdf7a9979a
Revises: f68cd5822a90
Create Date: 2026-09-14 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5abdf7a9979a'
down_revision = 'f68cd5822a90'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_constraint('inventory_items_status_check', type_='check')
        batch_op.create_check_constraint('inventory_items_status_check', "status in ('under_qc','accepted','rejected','partial','returned_to_vendor','discarded')")


def downgrade():
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_constraint('inventory_items_status_check', type_='check')
        batch_op.create_check_constraint('inventory_items_status_check', "status in ('under_qc','accepted','rejected','partial')")
